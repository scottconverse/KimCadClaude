"""A mock RepRapFirmware / Duet HTTP server for offline testing of the Duet connector.

Implements just the RRF subset :class:`~kimcad.duet_connector.DuetConnector` uses —
``GET /rr_connect``, ``GET /rr_status``, ``POST /rr_upload``, ``GET /rr_gcode`` — with optional
password auth and a live print that advances ``fractionPrinted`` as it's polled. No real hardware.
Run it with ``python -m kimcad.mock_duet`` or use the :func:`serve_mock_duet` context manager in
tests. It is a conformance oracle: the JSON shape it emits is exactly what the connector reads.
"""

from __future__ import annotations

import contextlib
import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlsplit

MAX_BODY_BYTES = 64 * 1024 * 1024


def _status_payload(status_type: int, state: dict[str, Any]) -> dict[str, Any]:
    """Build the rr_status payload, advancing a live print's progress one step per type-3 poll."""
    if status_type >= 3 and state["printing"]:
        state["fraction"] = min(100.0, state["fraction"] + state["step"])
        if state["fraction"] >= 100.0:
            state["printing"] = False
            state["status"] = "I"  # RRF returns to idle when the print completes
    printing = state["printing"]
    out: dict[str, Any] = {
        "status": state["status"],
        "temps": {
            "bed": {"current": 60.0 if printing else 25.0},
            "current": [60.0 if printing else 25.0, 210.0 if printing else 25.0],
        },
    }
    if status_type >= 2:
        out["axisMins"] = state["axis_mins"]
        out["axisMaxes"] = state["axis_maxes"]
    if status_type >= 3:
        out["fractionPrinted"] = round(state["fraction"], 2)
    return out


def _make_handler(state: dict[str, Any], password: str | None) -> type[BaseHTTPRequestHandler]:
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args: Any) -> None:  # silence default stderr logging
            pass

        def _json(self, code: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _authorized(self) -> bool:
            # On a password-protected board, the protected endpoints require a prior successful
            # /rr_connect (RRF tracks the session by client; the mock tracks one `connected` flag).
            # A 403 here surfaces in the connector as AuthError, distinct from offline.
            if password and not state["connected"]:
                self._json(403, {"err": 1})
                return False
            return True

        def do_GET(self) -> None:
            parts = urlsplit(self.path)
            query = parse_qs(parts.query, keep_blank_values=True)
            if parts.path == "/rr_connect":
                # err 0 ok, err 1 wrong password. A board with no password ignores the value.
                if password and (query.get("password", [""])[0] != password):
                    self._json(200, {"err": 1})
                else:
                    with lock:
                        state["connected"] = True
                    self._json(200, {"err": 0, "sessionTimeout": 8000})
                return
            if not self._authorized():
                return
            if parts.path == "/rr_status":
                try:
                    status_type = int(query.get("type", ["1"])[0])
                except (ValueError, TypeError):
                    status_type = 1
                with lock:
                    self._json(200, _status_payload(status_type, state))
                return
            if parts.path == "/rr_gcode":
                gcode = query.get("gcode", [""])[0]
                with lock:
                    if gcode.startswith("M32"):  # select + start an SD print
                        state["printing"] = True
                        state["fraction"] = 0.0
                        state["status"] = "P"
                self._json(200, {"buff": 240})
                return
            self._json(404, {"err": 1})

        def do_POST(self) -> None:
            parts = urlsplit(self.path)
            if not self._authorized():
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except (ValueError, TypeError):
                self._json(200, {"err": 1})
                return
            if length > MAX_BODY_BYTES:
                # Bounded, time-limited drain + close so a 413 isn't a Windows RST on a streaming
                # client (mirrors mock_moonraker; keeps this a faithful oracle).
                self.close_connection = True
                self.connection.settimeout(1.5)
                rem = length
                try:
                    while rem > 0 and (c := self.rfile.read(min(rem, 65536))):
                        rem -= len(c)
                except OSError:
                    pass
                self._json(413, {"err": 1})
                return
            body = self.rfile.read(length) if length else b""
            if parts.path == "/rr_upload":
                name = parse_qs(parts.query).get("name", [""])[0]
                if not name:
                    self._json(200, {"err": 1})
                    return
                with lock:
                    state["files"].append(name)
                    state["uploaded_bytes"] = len(body)
                self._json(200, {"err": 0})
                return
            self._json(404, {"err": 1})

    return Handler


def _initial_state(
    step: float,
    axis_mins: list[float] | None = None,
    axis_maxes: list[float] | None = None,
) -> dict[str, Any]:
    return {
        "files": [],
        "uploaded_bytes": 0,
        "connected": False,
        "printing": False,
        "status": "I",
        "fraction": 0.0,
        "step": step,
        "axis_mins": axis_mins or [0.0, 0.0, 0.0],
        "axis_maxes": axis_maxes or [230.0, 210.0, 200.0],
    }


@contextlib.contextmanager
def serve_mock_duet(
    *,
    password: str | None = None,
    step: float = 40.0,
    axis_mins: list[float] | None = None,
    axis_maxes: list[float] | None = None,
) -> Iterator[tuple[str, dict[str, Any]]]:
    """Run the mock on an ephemeral 127.0.0.1 port. Yields ``(base_url, state)``.

    ``step`` is the percent a single type-3 status poll advances the print (40 → done by the 3rd
    poll). ``password=None`` runs open (the common Duet LAN case). ``axis_mins``/``axis_maxes``
    override the reported travel (defaults model a 230×210×200 bed at origin)."""
    state = _initial_state(step, axis_mins, axis_maxes)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(state, password))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}", state
    finally:
        httpd.shutdown()
        httpd.server_close()


def main() -> None:  # pragma: no cover - manual dev convenience
    import argparse

    ap = argparse.ArgumentParser(description="Mock RepRapFirmware/Duet server (dev/test, no hardware).")
    ap.add_argument("--port", type=int, default=8085)
    ap.add_argument("--password", default=None)
    args = ap.parse_args()
    httpd = ThreadingHTTPServer(
        ("127.0.0.1", args.port), _make_handler(_initial_state(5.0), args.password)
    )
    note = f"  (password: {args.password})" if args.password else "  (no auth)"
    print(f"Mock Duet/RRF on http://127.0.0.1:{args.port}{note}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":  # pragma: no cover
    main()
