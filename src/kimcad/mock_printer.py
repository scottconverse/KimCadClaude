"""A mock OctoPrint server for dev/test — no real hardware (ROADMAP Stage 2).

Emulates the small subset of the OctoPrint REST API that
:class:`kimcad.octoprint_connector.OctoPrintConnector` uses, so the whole send-to-printer
path can be exercised end to end on the dev box: API-key auth, version, printer state +
temps, printer-profile (capabilities), file upload with select/print, and job progress.

Use :func:`serve_mock_octoprint` (a context manager that binds an ephemeral port) in tests,
or run ``python -m kimcad.mock_printer`` to poke it by hand. Real printing waits for Kim's
beta (Stage 10); this never drives hardware.
"""

from __future__ import annotations

import contextlib
import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

DEFAULT_API_KEY = "mock-key"
# Mirror the production web layer's body guard: a runaway/oversized upload is rejected
# before it's read into memory (ENG-205). The largest legitimate test upload is tiny G-code.
MAX_BODY_BYTES = 64 * 1024 * 1024


def _parse_upload(body: bytes, content_type: str) -> tuple[str | None, bool]:
    """Minimal multipart/form-data parse: return (uploaded filename, print-requested).

    Only what the mock needs — find the file part's ``filename`` and whether the ``print``
    field is ``true``. Not a general multipart parser.
    """
    if "boundary=" not in content_type:
        return None, False
    boundary = content_type.split("boundary=", 1)[1].strip().strip('"')
    filename: str | None = None
    do_print = False
    for part in body.split(("--" + boundary).encode()):
        if b"Content-Disposition" not in part:
            continue
        header, _, content = part.partition(b"\r\n\r\n")
        hdr = header.decode("latin-1", "replace")
        if 'filename="' in hdr:
            filename = hdr.split('filename="', 1)[1].split('"', 1)[0]
        elif 'name="print"' in hdr and content.strip().lower().startswith(b"true"):
            do_print = True
    return filename, do_print


def _make_handler(state: dict[str, Any], api_key: str) -> type[BaseHTTPRequestHandler]:
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args: Any) -> None:  # keep the console quiet
            pass

        def _auth(self) -> bool:
            if self.headers.get("X-Api-Key") == api_key:
                return True
            self._json(403, {"error": "invalid api key"})
            return False

        def _json(self, code: int, obj: dict[str, Any]) -> None:
            payload = json.dumps(obj).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _no_content(self) -> None:
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self) -> None:
            if not self._auth():
                return
            if self.path == "/api/version":
                self._json(200, {"server": "1.9.0-mock", "api": "0.1", "text": "OctoPrint mock"})
                return
            if self.path == "/api/printerprofiles":
                self._json(
                    200,
                    {
                        "profiles": {
                            "_default": {
                                "name": "Mock Printer",
                                "volume": {"width": 250, "depth": 210, "height": 210},
                                "extruder": {"nozzleDiameter": 0.4, "count": 1},
                            }
                        }
                    },
                )
                return
            if self.path == "/api/printer":
                with lock:
                    job = state["job"]
                    printing = job is not None and job["completion"] < 100.0
                self._json(
                    200,
                    {
                        "state": {
                            "text": "Printing" if printing else "Operational",
                            "flags": {
                                "printing": printing,
                                "operational": True,
                                "ready": not printing,
                            },
                        },
                        "temperature": {
                            "tool0": {"actual": 210.0 if printing else 25.0, "target": 0},
                            "bed": {"actual": 55.0 if printing else 25.0, "target": 0},
                        },
                    },
                )
                return
            if self.path == "/api/job":
                with lock:
                    job = state["job"]
                    if job is None:
                        self._json(
                            200,
                            {"job": {"file": {"name": None}}, "progress": {"completion": None},
                             "state": "Operational"},
                        )
                        return
                    # each poll advances the print toward completion (deterministic)
                    job["completion"] = min(100.0, job["completion"] + state["step"])
                    done = job["completion"] >= 100.0
                    self._json(
                        200,
                        {
                            "job": {"file": {"name": job["name"]}},
                            "progress": {"completion": job["completion"]},
                            "state": "Operational" if done else "Printing",
                        },
                    )
                return
            self._json(404, {"error": "not found"})

        def do_POST(self) -> None:
            if not self._auth():
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except (ValueError, TypeError):
                self._json(400, {"error": "bad content-length"})
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
                self._json(413, {"error": "request body too large"})
                return
            body = self.rfile.read(length) if length else b""
            if self.path == "/api/files/local":
                fname, do_print = _parse_upload(body, self.headers.get("Content-Type", ""))
                if fname is None:
                    self._json(400, {"error": "no file part"})
                    return
                with lock:
                    state["files"].append(fname)
                    if do_print:
                        state["job"] = {"name": fname, "completion": 0.0}
                self._json(201, {"done": True, "files": {"local": {"name": fname}}})
                return
            if self.path == "/api/job":
                try:
                    cmd = json.loads(body or b"{}").get("command")
                except (ValueError, TypeError):
                    self._json(400, {"error": "bad json"})
                    return
                with lock:
                    if cmd == "cancel":
                        state["job"] = None
                self._no_content()
                return
            self._json(404, {"error": "not found"})

    return Handler


@contextlib.contextmanager
def serve_mock_octoprint(
    *, api_key: str = DEFAULT_API_KEY, step: float = 40.0
) -> Iterator[tuple[str, dict[str, Any]]]:
    """Run the mock on an ephemeral 127.0.0.1 port. Yields ``(base_url, state)``.

    ``step`` is how much a single ``GET /api/job`` advances completion (40 → done by the
    3rd poll), so a status-flow can be driven deterministically.
    """
    state: dict[str, Any] = {"files": [], "job": None, "step": step}
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(state, api_key))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}", state
    finally:
        httpd.shutdown()
        httpd.server_close()


def main() -> None:  # pragma: no cover - manual dev convenience
    import argparse

    ap = argparse.ArgumentParser(description="Mock OctoPrint server (dev/test, no hardware).")
    # Default matches the shipped `octoprint` connector's base_url (127.0.0.1:5000), so a
    # bare `python -m kimcad.mock_printer` lines up with `--send octoprint` (QA-001).
    ap.add_argument("--port", type=int, default=5000)
    ap.add_argument("--api-key", default=DEFAULT_API_KEY)
    args = ap.parse_args()
    httpd = ThreadingHTTPServer(
        ("127.0.0.1", args.port), _make_handler({"files": [], "job": None, "step": 5.0}, args.api_key)
    )
    print(f"Mock OctoPrint on http://127.0.0.1:{args.port}  (X-Api-Key: {args.api_key})")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        httpd.server_close()


if __name__ == "__main__":  # pragma: no cover
    main()
