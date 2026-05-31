"""A mock Moonraker (Klipper) server for offline testing of the Moonraker connector.

Implements just the REST subset KimCad's :class:`~kimcad.moonraker_connector.MoonrakerConnector`
uses — `GET /printer/objects/query`, `POST /server/files/upload` — with optional API-key auth.
No real hardware. Run it with ``python -m kimcad.mock_moonraker`` or use the
:func:`serve_mock_moonraker` context manager in tests.
"""

from __future__ import annotations

import contextlib
import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qsl, urlsplit

DEFAULT_API_KEY = "mock-moonraker-key"
MAX_BODY_BYTES = 64 * 1024 * 1024


def _parse_upload(body: bytes, content_type: str) -> tuple[str | None, bool]:
    """Pull the uploaded filename and whether ``print=true`` from a multipart body. Returns
    ``(filename, do_print)`` — ``filename`` is None if no file part is present."""
    marker = "boundary="
    idx = content_type.find(marker)
    if idx < 0:
        return None, False
    boundary = ("--" + content_type[idx + len(marker):].strip()).encode()
    filename: str | None = None
    do_print = False
    for part in body.split(boundary):
        head, _, _ = part.partition(b"\r\n\r\n")
        head_l = head.lower()
        if b'filename="' in head:
            s = head.split(b'filename="', 1)[1]
            filename = s.split(b'"', 1)[0].decode("utf-8", "replace") or None
        elif b'name="print"' in head_l:
            value = part.split(b"\r\n\r\n", 1)[-1].strip().lower()
            if value.startswith(b"true"):
                do_print = True
    return filename, do_print


def _status_for(objects: list[str], state: dict[str, Any]) -> dict[str, Any]:
    """Build the `result.status` payload for the requested query objects, advancing a live
    print's progress by ``step`` each time print_stats/virtual_sdcard is polled."""
    if ("print_stats" in objects or "virtual_sdcard" in objects) and state["printing"]:
        state["progress"] = min(1.0, state["progress"] + state["step"])
        if state["progress"] >= 1.0:
            state["printing"] = False
            state["klip_state"] = "complete"
    out: dict[str, Any] = {}
    if "toolhead" in objects:
        out["toolhead"] = {
            "axis_minimum": state["axis_minimum"],
            "axis_maximum": state["axis_maximum"],
        }
    if "configfile" in objects:
        out["configfile"] = {"settings": {"extruder": {"nozzle_diameter": 0.4}}}
    if "print_stats" in objects:
        out["print_stats"] = {"state": state["klip_state"], "filename": state.get("filename", "")}
    if "extruder" in objects:
        out["extruder"] = {"temperature": 210.0 if state["printing"] else 25.0}
    if "heater_bed" in objects:
        out["heater_bed"] = {"temperature": 60.0 if state["printing"] else 25.0}
    if "virtual_sdcard" in objects:
        out["virtual_sdcard"] = {"progress": state["progress"], "is_active": state["printing"]}
    return out


def _make_handler(state: dict[str, Any], api_key: str | None) -> type[BaseHTTPRequestHandler]:
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args: Any) -> None:  # silence the default stderr logging
            pass

        def _json(self, code: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _auth(self) -> bool:
            if api_key and self.headers.get("X-Api-Key") != api_key:
                self._json(401, {"error": {"code": 401, "message": "unauthorized"}})
                return False
            return True

        def do_GET(self) -> None:
            if not self._auth():
                return
            parts = urlsplit(self.path)
            if parts.path == "/printer/objects/query":
                objects = [k for k, _v in parse_qsl(parts.query, keep_blank_values=True)]
                with lock:
                    status = _status_for(objects, state)
                self._json(200, {"result": {"status": status}})
                return
            self._json(404, {"error": {"message": "not found"}})

        def do_POST(self) -> None:
            if not self._auth():
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except (ValueError, TypeError):
                self._json(400, {"error": {"message": "bad content-length"}})
                return
            if length > MAX_BODY_BYTES:
                self._json(413, {"error": {"message": "request body too large"}})
                return
            body = self.rfile.read(length) if length else b""
            if urlsplit(self.path).path == "/server/files/upload":
                fname, do_print = _parse_upload(body, self.headers.get("Content-Type", ""))
                if fname is None:
                    self._json(400, {"error": {"message": "no file part"}})
                    return
                with lock:
                    state["files"].append(fname)
                    if do_print:
                        state["printing"] = True
                        state["progress"] = 0.0
                        state["klip_state"] = "printing"
                        state["filename"] = fname
                self._json(
                    201,
                    {"item": {"path": fname, "root": "gcodes"}, "print_started": do_print},
                )
                return
            self._json(404, {"error": {"message": "not found"}})

    return Handler


def _initial_state(
    step: float,
    axis_minimum: list[float] | None = None,
    axis_maximum: list[float] | None = None,
) -> dict[str, Any]:
    return {
        "files": [],
        "printing": False,
        "progress": 0.0,
        "klip_state": "standby",
        "filename": "",
        "step": step,
        "axis_minimum": axis_minimum or [0.0, 0.0, 0.0, 0.0],
        "axis_maximum": axis_maximum or [250.0, 250.0, 240.0, 0.0],
    }


@contextlib.contextmanager
def serve_mock_moonraker(
    *,
    api_key: str | None = None,
    step: float = 0.4,
    axis_minimum: list[float] | None = None,
    axis_maximum: list[float] | None = None,
) -> Iterator[tuple[str, dict[str, Any]]]:
    """Run the mock on an ephemeral 127.0.0.1 port. Yields ``(base_url, state)``.

    ``step`` is how much a single print_stats/virtual_sdcard poll advances progress (0.4 →
    done by the 3rd poll). ``api_key=None`` runs unauthenticated (the common Klipper LAN case).
    ``axis_minimum``/``axis_maximum`` override the reported travel (defaults model a 250×250×240
    bed at origin); pass a negative minimum to exercise a non-zero build origin.
    """
    state = _initial_state(step, axis_minimum, axis_maximum)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(state, api_key))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}", state
    finally:
        httpd.shutdown()
        httpd.server_close()


def main() -> None:  # pragma: no cover - manual dev convenience
    import argparse

    ap = argparse.ArgumentParser(description="Mock Moonraker server (dev/test, no hardware).")
    ap.add_argument("--port", type=int, default=7125)  # Moonraker's default port
    ap.add_argument("--api-key", default=None)
    args = ap.parse_args()
    httpd = ThreadingHTTPServer(
        ("127.0.0.1", args.port), _make_handler(_initial_state(0.1), args.api_key)
    )
    key_note = f"  (X-Api-Key: {args.api_key})" if args.api_key else "  (no auth)"
    print(f"Mock Moonraker on http://127.0.0.1:{args.port}{key_note}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":  # pragma: no cover
    main()
