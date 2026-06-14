"""A mock Marlin printer (TCP) for offline testing of the Marlin connector.

Speaks the M-code line subset :class:`~kimcad.marlin_connector.MarlinConnector` uses — ``M115``,
``M105``, ``M110``, the line-numbered + checksummed SD stream (``M28``…``M29``), ``M23``/``M24``,
``M27`` — over a TCP socket, the same transport a serial-over-network bridge exposes. It strips the
``N<n> … *<cs>`` framing (storing the plain command, as real Marlin does), can inject a ``Resend:``
or an ``Error:`` to exercise the connector's integrity/cleanup paths, and faithfully reports "Not SD
printing" once a print completes (so the test proves the connector's done-LATCH, not a sticky
fiction). No real hardware. Run with ``python -m kimcad.mock_marlin`` or use :func:`serve_mock_marlin`.
"""

from __future__ import annotations

import contextlib
import math
import re
import socketserver
import threading
from collections.abc import Iterator
from typing import Any

_FIRMWARE = "FIRMWARE_NAME:Marlin 2.1.2 (KimCad mock) SOURCE_CODE_URL:mock MACHINE_TYPE:Mock EXTRUDER_COUNT:1"
_FRAME = re.compile(r"^N(\d+)\s+(.*?)(?:\*\d+)?$")  # "N12 G1 X1*45" -> (12, "G1 X1")


def _strip_frame(line: str) -> tuple[int | None, str]:
    m = _FRAME.match(line)
    if m:
        return int(m.group(1)), m.group(2).strip()
    return None, line


def _make_server_class(state: dict[str, Any], lock: threading.Lock) -> type[socketserver.BaseRequestHandler]:
    class Handler(socketserver.StreamRequestHandler):
        timeout = 10

        def _w(self, text: str) -> None:
            self.wfile.write(text.encode("ascii", "replace"))
            self.wfile.flush()

        def _ok(self) -> None:
            self._w("ok\n")

        def handle(self) -> None:
            writing = False  # between M28 and M29 every line is SD-file data (per connection)
            written = 0
            stream_idx = 0  # 1-based count of streamed data lines (for fault injection)
            resent: set[int] = set()  # resend-faults already fired (so the replay succeeds)
            if state.get("banner"):
                self._w("start\necho:Marlin (mock) boot\n")  # boot chatter the reader must skip
            while True:
                raw = self.rfile.readline()
                if not raw:
                    return
                line = raw.decode("utf-8", "replace").strip()
                if not line:
                    continue
                _n, cmd_body = _strip_frame(line)
                cmd = cmd_body.split()[0].upper() if cmd_body else ""
                with lock:
                    if writing and cmd != "M29":
                        stream_idx += 1
                        if state.get("resend_at") == stream_idx and stream_idx not in resent:
                            resent.add(stream_idx)
                            self._w(f"Resend: {_n if _n is not None else stream_idx}\n")
                            stream_idx -= 1  # the resent line will be re-counted on replay
                            continue
                        if state.get("error_at") == stream_idx:
                            self._w("Error: mock mid-stream failure\n")
                            continue
                        written += len(cmd_body) + 1  # the STRIPPED command is what lands on SD
                        state["sd_lines"].append(cmd_body)  # capture content for an exactness test
                        self._ok()
                        continue
                    if cmd == "M110":  # reset line numbers
                        self._ok()
                    elif cmd == "M28":  # open SD file for writing
                        writing, written, stream_idx = True, 0, 0
                        state["sd_lines"] = []
                        self._ok()
                    elif cmd == "M29":  # close SD file — its size is the print total
                        writing = False
                        state["total"] = written
                        self._ok()
                    elif cmd == "M115":
                        self._w(_FIRMWARE + "\n")
                        self._ok()
                    elif cmd == "M105":  # read-only temp report
                        nozzle = 210.0 if state["printing"] else 25.0
                        bed = 60.0 if state["printing"] else 25.0
                        self._w(f"ok T:{nozzle:.2f} /0.00 B:{bed:.2f} /0.00 @:0 B@:0\n")
                    elif cmd == "M23":  # select the file
                        self._w("File opened\nFile selected\n")
                        self._ok()
                    elif cmd == "M24":  # start the SD print
                        state["printing"] = True
                        state["printed"] = 0
                        state["step"] = max(1, math.ceil(state["total"] / state["poll_count"]))
                        self._ok()
                    elif cmd == "M27":  # report SD print progress (advances the mock's print)
                        if state["printing"] and state["total"] > 0:
                            state["printed"] = min(state["total"], state["printed"] + state["step"])
                            self._w(f"SD printing byte {state['printed']}/{state['total']}\n")
                            if state["printed"] >= state["total"]:
                                state["printing"] = False  # faithful: progress clears on completion
                            self._ok()
                        else:
                            self._w("Not SD printing\n")  # idle OR finished-and-cleared
                            self._ok()
                    else:
                        self._ok()  # accept any other streamed/control line

    return Handler


def _initial_state(poll_count: int, *, resend_at: int | None, error_at: int | None,
                   banner: bool) -> dict[str, Any]:
    return {
        "total": 0, "printed": 0, "printing": False, "step": 1, "poll_count": poll_count,
        "resend_at": resend_at, "error_at": error_at, "banner": banner, "sd_lines": [],
    }


@contextlib.contextmanager
def serve_mock_marlin(
    *, poll_count: int = 2, resend_at: int | None = None, error_at: int | None = None,
    banner: bool = False,
) -> Iterator[tuple[str, dict[str, Any]]]:
    """Run the mock on an ephemeral 127.0.0.1 port. Yields ``("host:port", state)`` (the target the
    MarlinConnector takes). ``poll_count`` = how many ``M27`` polls complete the print. ``resend_at``
    / ``error_at`` inject a ``Resend:`` / ``Error:`` at the Nth streamed SD line. ``banner`` emits
    boot chatter the reader must skip."""
    state = _initial_state(poll_count, resend_at=resend_at, error_at=error_at, banner=banner)
    lock = threading.Lock()
    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), _make_server_class(state, lock))
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    host, port = server.server_address[:2]
    try:
        yield f"{host}:{port}", state
    finally:
        server.shutdown()
        server.server_close()


def main() -> None:  # pragma: no cover - manual dev convenience
    import argparse

    ap = argparse.ArgumentParser(description="Mock Marlin printer over TCP (dev/test, no hardware).")
    ap.add_argument("--port", type=int, default=8099)
    ap.add_argument("--poll-count", type=int, default=8)
    args = ap.parse_args()
    state = _initial_state(args.poll_count, resend_at=None, error_at=None, banner=True)
    lock = threading.Lock()
    server = socketserver.ThreadingTCPServer(("127.0.0.1", args.port), _make_server_class(state, lock))
    print(f"Mock Marlin (TCP) on 127.0.0.1:{args.port}  — point a connector at this host:port")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":  # pragma: no cover
    main()
