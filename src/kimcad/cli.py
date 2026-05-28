"""Command-line interface — the Phase-1 user surface (spec §5).

Two subcommands:

    kimcad "a wall bracket for a 25mm pipe"     # design a part (default verb)
    kimcad design "..." [--printer ... --material ...]
    kimcad bench [--prompts bench/prompts.yaml] [--min-success-rate 0.7]

The CLI only wires already-tested pieces together: it builds the configured LLM
backend, runs the :class:`~kimcad.pipeline.Pipeline`, and prints the print report.
Missing prerequisites (no API key, no prompt file) fail with a plain-English message
and a non-zero exit code rather than a traceback.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from kimcad.config import Config

_SUBCOMMANDS = {"design", "bench"}


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
    """Allow a bare prompt: ``kimcad "..."`` is treated as ``kimcad design "..."``."""
    if argv and argv[0] not in _SUBCOMMANDS and not argv[0].startswith("-"):
        return ["design", *argv]
    return argv


def _build_pipeline(config: Config, args: argparse.Namespace):
    from kimcad.llm_provider import LLMProvider
    from kimcad.pipeline import Pipeline

    printer = config.printer(args.printer)
    material = config.material(args.material)
    provider = LLMProvider(config.llm_backend(args.backend))
    return Pipeline(config, printer, material, provider)


def _cmd_design(config: Config, args: argparse.Namespace) -> int:
    pipeline = _build_pipeline(config, args)
    result = pipeline.run(args.prompt, Path(args.out), proceed_anyway=args.proceed_anyway)

    from kimcad.pipeline import PipelineStatus

    if result.status is PipelineStatus.clarification_needed:
        print(f"I need one detail before building:\n  {result.clarification}")
        return 3
    if result.status is PipelineStatus.render_failed:
        print(f"Could not produce a valid model after retries.\n  {result.error}")
        return 4
    print(result.report.to_text())
    if result.status is PipelineStatus.gate_failed:
        print("\nPrintability Gate FAILED. Re-run with --proceed-anyway to override.")
        return 5
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
    summary = run_benchmark(cases, make_case_runner(pipeline, Path(args.out)))
    print(summary.to_text(min_success_rate=args.min_success_rate))
    if args.min_success_rate is not None and not summary.meets(args.min_success_rate):
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = _normalize_argv(list(sys.argv[1:] if argv is None else argv))
    parser = build_parser()
    args = parser.parse_args(argv)

    config = Config.load()
    try:
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
