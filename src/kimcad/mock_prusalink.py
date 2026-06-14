"""A mock PrusaLink server for offline testing of the PrusaLink connector.

Implements just the REST subset KimCad's
:class:`~kimcad.prusalink_connector.PrusaLinkConnector` uses — `GET /api/v1/info`,
`GET /api/v1/status`, `PUT /api/v1/files/<storage>/<name>` — with X-Api-Key auth. No real
hardware. Run it with ``python -m kimcad.mock_prusalink`` or use the
:func:`serve_mock_prusalink` context manager in tests.
"""

from __future__ import annotations

import contextlib
import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import unquote, urlsplit

DEFAULT_API_KEY = "mock-prusa-key"
MAX_BODY_BYTES = 64 * 1024 * 1024


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
                self._json(401, {"title": "Unauthorized", "message": "bad api key"})
                return False
            return True

        def do_GET(self) -> None:
            if not self._auth():
                return
            path = urlsplit(self.path).path
            if path == "/api/v1/info":
                self._json(200, {"nozzle_diameter": 0.4, "name": "Mock Prusa", "hostname": "mk4"})
                return
            if path == "/api/v1/status":
                with lock:
                    if state["printing"]:
                        state["progress"] = min(100.0, state["progress"] + state["step"])
                        if state["progress"] >= 100.0:
                            state["printing"] = False
                            state["printer_state"] = "FINISHED"
                    printer = {
                        "state": state["printer_state"],
                        "temp_nozzle": 215.0 if state["printing"] else 25.0,
                        "temp_bed": 60.0 if state["printing"] else 25.0,
                    }
                    job = {"progress": state["progress"]} if state.get("filename") else {}
                self._json(200, {"printer": printer, "job": job})
                return
            self._json(404, {"title": "Not Found", "message": "not found"})

        def do_PUT(self) -> None:
            if not self._auth():
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except (ValueError, TypeError):
                self._json(400, {"title": "Bad Request", "message": "bad content-length"})
                return
            if length > MAX_BODY_BYTES:
                # Drain a bounded prefix + close so the 413 isn't a Windows RST on a streaming
                # client (mirrors webapp._reject_oversized_body; keeps this mock a faithful
                # oracle). Time-bounded so a declared-but-unsent body can't hang the thread.
                self.close_connection = True
                self.connection.settimeout(1.5)
                rem = min(length, 64 * 1024 * 1024)
                try:
                    while rem > 0 and (c := self.rfile.read(min(rem, 65536))):
                        rem -= len(c)
                except OSError:
                    pass
                self._json(413, {"title": "Too Large", "message": "request body too large"})
                return
            _body = self.rfile.read(length) if length else b""  # consume the gcode body
            path = urlsplit(self.path).path
            if path.startswith("/api/v1/files/"):
                fname = unquote(path.rsplit("/", 1)[-1])
                do_print = self.headers.get("Print-After-Upload", "").strip() in ("?1", "1", "true")
                overwrite = self.headers.get("Overwrite", "").strip() in ("?1", "1", "true")
                with lock:
                    if state["printing"]:
                        # PrusaLink rejects a print-upload while already printing.
                        self._json(409, {"title": "Conflict", "message": "printer is printing"})
                        return
                    if fname in state["files"] and not overwrite:
                        # A duplicate filename 409s unless the Overwrite header is set (ENG-007).
                        self._json(409, {"title": "Conflict", "message": "file already exists"})
                        return
                    if fname not in state["files"]:
                        state["files"].append(fname)
                    if do_print:
                        state["printing"] = True
                        state["progress"] = 0.0
                        state["printer_state"] = "PRINTING"
                        state["filename"] = fname
                self._json(201, {"name": fname})
                return
            self._json(404, {"title": "Not Found", "message": "not found"})

    return Handler


def _initial_state(step: float) -> dict[str, Any]:
    return {
        "files": [],
        "printing": False,
        "progress": 0.0,
        "printer_state": "IDLE",
        "filename": "",
        "step": step,
    }


@contextlib.contextmanager
def serve_mock_prusalink(
    *, api_key: str | None = DEFAULT_API_KEY, step: float = 40.0
) -> Iterator[tuple[str, dict[str, Any]]]:
    """Run the mock on an ephemeral 127.0.0.1 port. Yields ``(base_url, state)``.

    ``step`` is how much a single ``/api/v1/status`` poll advances progress, as a percentage
    (40 -> done by the 3rd poll). ``api_key=None`` runs unauthenticated.
    """
    state = _initial_state(step)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(state, api_key))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}", state
    finally:
        httpd.shutdown()
        httpd.server_close()


def main() -> None:  # pragma: no cover - manual dev convenience
    import argparse

    ap = argparse.ArgumentParser(description="Mock PrusaLink server (dev/test, no hardware).")
    ap.add_argument("--port", type=int, default=8080)  # PrusaLink's default HTTP port
    ap.add_argument("--api-key", default=DEFAULT_API_KEY)
    args = ap.parse_args()
    httpd = ThreadingHTTPServer(
        ("127.0.0.1", args.port), _make_handler(_initial_state(10.0), args.api_key)
    )
    print(f"Mock PrusaLink on http://127.0.0.1:{args.port}  (X-Api-Key: {args.api_key})")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":  # pragma: no cover
    main()
