"""Command-line interface — the Phase-1 user surface (spec §5).

Three subcommands:

    kimcad "a wall bracket for a 25mm pipe"     # design a part (default verb)
    kimcad design "..." [--printer ... --material ...] [--slice]
    kimcad bench [--prompts bench/prompts.yaml] [--min-success-rate 0.7]
    kimcad web [--host ... --port ... --demo]   # local browser UI (Phase 2)

``--slice`` is the explicit print confirmation: only with it does a passing part get
sliced into a printable G-code 3MF for the chosen printer + material.

The CLI only wires already-tested pieces together: it loads config, builds the
configured LLM backend, runs the :class:`~kimcad.pipeline.Pipeline`, and prints the
print report. Foreseeable setup problems — a bad config, a missing API key, or a
missing prompt file — fail with a plain-English message and a non-zero exit code
rather than a traceback.
"""

from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path
from typing import Any

from kimcad.config import Config

_SUBCOMMANDS = {"design", "bench", "web"}


def _force_utf8_output(stream: Any) -> None:
    """Make a text stream emit UTF-8 so report glyphs (×, ³, °, >=) never crash.

    Windows consoles default to cp1252, which cannot encode the characters the
    print report and benchmark verdict use; without this, output raises
    UnicodeEncodeError after the work is already done. ``reconfigure`` is absent
    on some wrapped streams (e.g. pytest's capture), so the call is best-effort.
    """
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is None:
        return
    try:
        reconfigure(encoding="utf-8")
    except (ValueError, OSError):
        pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kimcad",
        description="Turn a plain-English description into a printable 3D part.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    d = sub.add_parser("design", help="Generate a printable part from a prompt.")
    d.add_argument("prompt", help="What to build, in plain English.")
    d.add_argument("--printer", default=None, help="Printer key (default from config).")
    d.add_argument("--material", default=None, help="Material key (default from config).")
    d.add_argument("--backend", default=None, help="LLM backend key (default from config).")
    d.add_argument("--out", default="output", help="Output directory (default: output/).")
    d.add_argument(
        "--proceed-anyway",
        action="store_true",
        help="Continue past a failing Printability Gate (advanced).",
    )
    d.add_argument(
        "--slice",
        dest="do_slice",
        action="store_true",
        help="After a passing gate, also slice the part into a printable G-code 3MF "
        "for the chosen printer + material (explicit print confirmation).",
    )
    d.add_argument(
        "--send",
        default=None,
        metavar="CONNECTOR",
        help="Slice, then send the print job to a configured connector by name "
        "(e.g. 'mock' or 'octoprint'). This is the explicit per-send confirmation.",
    )

    w = sub.add_parser("web", help="Launch the local web UI (Phase 2).")
    w.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1).")
    w.add_argument("--port", type=int, default=8765, help="Bind port (default: 8765).")
    w.add_argument("--backend", default=None, help="LLM backend key (default from config).")
    w.add_argument(
        "--demo",
        action="store_true",
        help="Serve a fixed sample part with no LLM call (fast UI demo).",
    )

    b = sub.add_parser("bench", help="Run the Phase-1 benchmark (the done-gate).")
    b.add_argument("--prompts", default="bench/prompts.yaml", help="Benchmark prompt YAML.")
    b.add_argument("--out", default="output/bench", help="Output directory.")
    b.add_argument("--backend", default=None, help="LLM backend key (default from config).")
    b.add_argument("--printer", default=None, help="Printer key (default from config).")
    b.add_argument("--material", default=None, help="Material key (default from config).")
    b.add_argument(
        "--min-success-rate",
        type=float,
        default=None,
        help="If set, exit non-zero unless the batch meets this pass rate (§4.2).",
    )
    return parser


def _normalize_argv(argv: list[str]) -> list[str]:
    """Allow a bare prompt: ``kimcad "..."`` is treated as ``kimcad design "..."``.

    Guards against a typo'd subcommand: a single bare word that's a near-miss of a real
    subcommand (e.g. ``benhc`` → ``bench``, ``wbe`` → ``web``) is left as-is so argparse
    rejects it with the valid choices, instead of silently being taken as a one-word part
    description and launching a multi-minute design run.
    """
    if not argv or argv[0] in _SUBCOMMANDS or argv[0].startswith("-"):
        return argv
    first = argv[0]
    if " " not in first and difflib.get_close_matches(first, sorted(_SUBCOMMANDS), cutoff=0.6):
        return argv
    return ["design", *argv]


def _build_pipeline(config: Config, args: argparse.Namespace):
    from kimcad.llm_provider import LLMProvider
    from kimcad.pipeline import Pipeline

    printer = config.printer(args.printer)
    material = config.material(args.material)
    provider = LLMProvider(config.llm_backend(args.backend))
    return Pipeline(config, printer, material, provider)


def _slice_intent(config: Config, printer: Any, material: Any) -> str:
    """A plain-English line, shown before a ``--slice`` run, naming the printer +
    material and the exact OrcaSlicer profiles the part will be sliced with — or a
    clear note when the chosen printer can't be sliced (no process profile)."""
    from kimcad.slicer import OrcaProfileError, resolve_slice_settings

    try:
        s = resolve_slice_settings(config.orca_profiles_root(), printer, material)
    except OrcaProfileError as e:
        return f"Note: cannot slice for {printer.name} + {material.name} — {e}"
    return (
        f"Will slice for {printer.name} + {material.name} using:\n"
        f"  machine   = {s.machine.stem}\n"
        f"  process   = {s.process.stem}\n"
        f"  filament  = {s.filament.stem}"
    )


def _send_print_job(config: Config, connector_name: str, gcode_path: str) -> None:
    """Build the named connector and send the sliced G-code, then print the job + printer
    status. Any connector problem (unknown/offline/auth/refused) is shown plainly with the
    on-disk G-code as the fallback — never a traceback."""
    from pathlib import Path as _Path

    from kimcad.connectors import build_connector
    from kimcad.printer_connector import ConnectorError

    try:
        connector = build_connector(config, connector_name)
        job = connector.send(_Path(gcode_path), confirm=True)
    except ConnectorError as e:
        print(f"\nNot sent to {connector_name}: {e}")
        print(f"Your G-code is still on disk: {gcode_path}")
        return
    print(f"\nSent to {connector_name}: job {job.job_id} ({job.state.value}).")
    try:
        st = connector.status()
        detail = f" — {st.detail}" if st.detail else ""
        print(f"  Printer: {st.state.value}{detail}")
    except ConnectorError as e:
        print(f"  (couldn't read printer status: {e})")


def _cmd_design(config: Config, args: argparse.Namespace) -> int:
    # --send implies slicing (you can't send what wasn't sliced); validate the connector
    # up front so a typo fails fast, not after a multi-minute run.
    do_slice = args.do_slice or bool(args.send)
    if args.send and args.send not in config.connectors():
        known = ", ".join(config.connectors()) or "(none configured)"
        print(f"Unknown connector '{args.send}'. Configured connectors: {known}")
        return 2

    pipeline = _build_pipeline(config, args)
    if do_slice:
        print(_slice_intent(config, pipeline.printer, pipeline.material))
    result = pipeline.run(
        args.prompt,
        Path(args.out),
        proceed_anyway=args.proceed_anyway,
        confirm_print=do_slice,
    )

    from kimcad.pipeline import PipelineStatus

    if result.status is PipelineStatus.clarification_needed:
        print(f"I need one detail before building:\n  {result.clarification}")
        return 3
    if result.status is PipelineStatus.render_failed:
        print(f"Could not produce a valid model after retries.\n  {result.error}")
        return 4
    if result.report is not None:
        print(result.report.to_text())
    if result.status is PipelineStatus.gate_failed:
        print("\nPrintability Gate FAILED. Re-run with --proceed-anyway to override.")
        return 5
    if args.send:
        if result.report is not None and result.report.sliced and result.report.gcode_path:
            _send_print_job(config, args.send, result.report.gcode_path)
        else:
            print(f"\nNothing to send to {args.send}: no G-code was produced.")
    print(f"\nMesh: {result.mesh_path}")
    return 0


def _cmd_bench(config: Config, args: argparse.Namespace) -> int:
    from kimcad.benchmark import load_cases, make_case_runner, run_benchmark

    prompts_path = Path(args.prompts)
    if not prompts_path.exists():
        print(
            f"No benchmark prompts at {prompts_path}.\n"
            "Copy bench/prompts.example.yaml to bench/prompts.yaml and fill in the "
            "Appendix B prompts."
        )
        return 2

    pipeline = _build_pipeline(config, args)
    cases = load_cases(prompts_path)
    out_dir = Path(args.out)
    summary = run_benchmark(cases, make_case_runner(pipeline, out_dir))
    text = summary.to_text(min_success_rate=args.min_success_rate)
    # Persist the verdict before printing: a batch is minutes of CPU, and a
    # console-encoding error at print time must never discard the result.
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.txt").write_text(text, encoding="utf-8")
    print(text)
    if args.min_success_rate is not None and not summary.meets(args.min_success_rate):
        return 1
    return 0


def _cmd_web(args: argparse.Namespace) -> int:
    from kimcad.webapp import serve

    serve(host=args.host, port=args.port, demo=args.demo, backend=args.backend)
    return 0


def main(argv: list[str] | None = None) -> int:
    _force_utf8_output(sys.stdout)
    _force_utf8_output(sys.stderr)
    argv = _normalize_argv(list(sys.argv[1:] if argv is None else argv))
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "web":
            return _cmd_web(args)
        # design / bench need config; loading it inside the try means a malformed
        # config.yaml fails with a clean message instead of a raw traceback.
        config = Config.load()
        if args.command == "design":
            return _cmd_design(config, args)
        if args.command == "bench":
            return _cmd_bench(config, args)
    except RuntimeError as e:
        # e.g. a configured backend whose API key env var is unset.
        print(f"Error: {e}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
