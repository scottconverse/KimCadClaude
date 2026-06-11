"""Command-line interface — the user-facing CLI surface (spec §5).

Five subcommands:

    kimcad "a wall bracket for a 25mm pipe"     # design a part (default verb)
    kimcad design "..." [--printer ... --material ...] [--slice]
    kimcad bench [--prompts bench/prompts.yaml] [--min-success-rate 0.7] [--slice]
    kimcad web [--host ... --port ... --demo]   # local browser UI (Phase 2)
    kimcad models                               # advise a model for this machine (Stage 6)
    kimcad bakeoff [--backends a,b]             # compare models on the benchmark (Stage 6)

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

_SUBCOMMANDS = {"design", "bench", "web", "shell", "models", "bakeoff"}


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
    # Slice 11.3: the single-sourced version on the CLI surface (`kimcad --version`).
    from kimcad import __version__

    parser.add_argument("--version", action="version", version=f"kimcad {__version__}")
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
        help="Slice, then send the print job to a configured connector by name. The stock config "
        "ships 'mock' (loopback) and 'octoprint' active, plus 'bambu_p2s'/'bambu_a1' templates "
        "(Bambu LAN mode — fill in the IP + serial and set the access-code env var; needs the "
        "optional bambulabs-api package); 'moonraker'/'prusalink' are supported but commented "
        "out in config until you enable one. This is the explicit per-send confirmation.",
    )

    w = sub.add_parser("web", help="Launch the local web UI (Phase 2).")
    w.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1).")
    w.add_argument(
        "--allow-remote",
        action="store_true",
        help="Required to bind a non-loopback --host. The server has NO authentication: "
        "anyone who can reach the port can run the full design pipeline and dispatch "
        "prints. Loopback (the default) needs nothing.",
    )
    w.add_argument("--port", type=int, default=8765, help="Bind port (default: 8765).")
    w.add_argument("--backend", default=None, help="LLM backend key (default from config).")
    w.add_argument(
        "--demo",
        action="store_true",
        help="Serve a fixed sample part with no LLM call (fast UI demo).",
    )

    sh = sub.add_parser(
        "shell",
        help="Launch KimCad as a windowed app (WebView2) — what the installer's shortcut runs. "
        "Same app as `kimcad web`, in its own window on a private ephemeral port; closing the "
        "window exits cleanly.",
    )
    sh.add_argument("--backend", default=None, help="LLM backend key (default from config).")
    sh.add_argument(
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
    b.add_argument(
        "--slice",
        action="store_true",
        help="Also slice each part (real OrcaSlicer) to grade the slices-clean axis. "
        "Slower; off by default. The matches-request and correct-dimensions axes are "
        "graded either way.",
    )

    m = sub.add_parser(
        "models",
        help="Examine this machine + your installed models and recommend one (advisory).",
    )
    m.add_argument(
        "--base-url",
        default=None,
        help="Ollama base URL to query for installed models (default: the configured "
        "local backend, else http://localhost:11434/v1).",
    )

    bo = sub.add_parser(
        "bakeoff",
        help="Run the benchmark across two+ model backends and compare them (Stage 6).",
    )
    bo.add_argument(
        "--backends",
        default="local_qwen,local",
        help="Comma-separated config backend keys to compare (default: local_qwen,local). "
        "Each must be defined under llm.backends; each backend's model_name is what runs.",
    )
    bo.add_argument("--prompts", default="bench/prompts.yaml", help="Benchmark prompt YAML.")
    bo.add_argument("--out", default="output/bakeoff", help="Output directory.")
    bo.add_argument("--printer", default=None, help="Printer key (default from config).")
    bo.add_argument("--material", default=None, help="Material key (default from config).")
    bo.add_argument(
        "--no-slice",
        action="store_true",
        help="Skip slicing (drops the slices-clean axis from the comparison). Slicing is "
        "on by default for a bake-off so all three axes are compared.",
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
    from kimcad.history import HistoryStore
    from kimcad.llm_provider import FallbackProvider, LLMProvider
    from kimcad.pipeline import Pipeline

    printer = config.printer(args.printer)
    material = config.material(args.material)
    primary = LLMProvider(config.llm_backend(args.backend))
    alt_cfg = config.llm_alt_backend()
    alt = LLMProvider(alt_cfg) if alt_cfg is not None else None
    provider = FallbackProvider(primary, alt) if alt is not None else primary
    # A real design is remembered for the Smart Mesh learning comparison (local-first, best-effort).
    return Pipeline(
        config, printer, material, provider, history=HistoryStore(config.history_path())
    )


def _pipeline_for_backend(config: Config, backend_key: str, printer: Any, material: Any):
    """Build a pipeline pinned to one backend, with NO fallback chain — the bake-off
    measures each model in isolation, so a silent fallback would contaminate the
    comparison by swapping in the other model mid-run."""
    from kimcad.llm_provider import LLMProvider
    from kimcad.pipeline import Pipeline

    provider = LLMProvider(config.llm_backend(backend_key))
    return Pipeline(config, printer, material, provider)


def _slice_intent(config: Config, printer: Any, material: Any) -> str:
    """A plain-English line, shown before a ``--slice`` run, naming the printer +
    material and the exact OrcaSlicer profiles the part will be sliced with — or a
    clear note when the chosen printer can't be sliced (no process profile)."""
    from kimcad.errors import ToolMissingError
    from kimcad.slicer import OrcaProfileError, resolve_slice_settings

    # QA-A-002: a never-fetched OrcaSlicer must read as "tool missing + how to fetch it",
    # not as a profile-resolution failure with a raw path.
    orca = config.binary_path("orcaslicer")
    if not orca.is_file():
        return f"Note: {ToolMissingError('OrcaSlicer', orca)}"
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
    from kimcad.connectors import build_connector
    from kimcad.printer_connector import ConnectorError

    try:
        connector = build_connector(config, connector_name)
        job = connector.send(Path(gcode_path), confirm=True)
    except ConnectorError as e:
        print(f"\nNot sent to {connector_name}: {e}")
        print(f"Your G-code is still on disk: {gcode_path}")
        return
    if getattr(connector, "drives_hardware", True):
        print(f"\nSent to {connector_name}: job {job.job_id} ({job.state.value}).")
    else:
        # Honest copy: a loopback/simulated connector touches no hardware (UX-001).
        print(
            f"\nSimulated send to {connector_name} (no real printer was used): job "
            f"{job.job_id} ({job.state.value}). The real file is on disk: {gcode_path}"
        )
    try:
        st = connector.status()
        detail = f" — {st.detail}" if st.detail else ""
        print(f"  Printer: {st.state.value}{detail}")
    except ConnectorError as e:
        print(f"  (couldn't read printer status: {e})")


# QA-005: human labels for the pipeline's coarse phases (same vocabulary the web UI shows).
# ASCII on purpose (QA-A-004): a piped/redirected console on a legacy codepage (cp437/cp1252)
# mojibakes non-ASCII even though direct console output is UTF-8-reconfigured.
_PHASE_LABELS = {
    "planning": "Planning the shape...",
    "generating": "Writing the CAD code...",
    "rendering": "Rendering the part...",
    "validating": "Checking it for printing...",
}


def _phase_printer():
    """Progress sink for CLI runs — one line per phase to stderr (stdout stays the report).
    Consecutive repeats are deduped: codegen retries re-emit 'generating' and shouldn't stutter."""
    last: list[str | None] = [None]

    def emit(phase: str) -> None:
        if phase == last[0]:
            return
        last[0] = phase
        print(f"  {_PHASE_LABELS.get(phase, phase)}", file=sys.stderr, flush=True)

    return emit


def _resolve_out(raw: str) -> Path:
    """Slice 11.4 (+11.4-audit FINDING-004): in the INSTALLED app a relative --out must
    not land in Program Files / whatever CWD the shortcut launched with — it goes to the
    per-user writable tree. Dev behavior (CWD-relative) is unchanged. Shared by design,
    bench, and bakeoff."""
    out = Path(raw)
    if not out.is_absolute():
        from kimcad.paths import is_installed, writable_root

        if is_installed():
            out = writable_root() / out
    return out


def _cmd_design(config: Config, args: argparse.Namespace) -> int:
    # --send implies slicing (you can't send what wasn't sliced); validate the connector
    # up front so a typo fails fast, not after a multi-minute run. QA-1004 (stage-10 gate):
    # name membership isn't enough — the shipped templates (bambu_p2s, octoprint-without-
    # its-key) EXIST but can't send, and discovering that after a multi-minute design run
    # is the worst possible moment. BUILD the connector now; a config gap fails in <1s
    # with the connector's own actionable message.
    do_slice = args.do_slice or bool(args.send)
    if args.send:
        if args.send not in config.connectors():
            known = ", ".join(config.connectors()) or "(none configured)"
            print(f"Unknown connector '{args.send}'. Configured connectors: {known}", file=sys.stderr)
            return 2
        from kimcad.connectors import build_connector
        from kimcad.printer_connector import ConnectorError

        try:
            build_connector(config, args.send)
        except ConnectorError as e:
            print(e.user_message or str(e), file=sys.stderr)
            return 2

    pipeline = _build_pipeline(config, args)
    if do_slice:
        print(_slice_intent(config, pipeline.printer, pipeline.material))
    out_path = _resolve_out(args.out)
    result = pipeline.run(
        args.prompt,
        out_path,
        proceed_anyway=args.proceed_anyway,
        confirm_print=do_slice,
        # QA-005: a real local generation takes minutes on the CPU target; a silent console
        # reads as a freeze. Phases go to stderr so stdout stays clean for the report.
        progress=_phase_printer(),
    )

    from kimcad.pipeline import PipelineStatus

    if result.status is PipelineStatus.clarification_needed:
        print(f"I need one detail before building:\n  {result.clarification}")
        return 3
    if result.status is PipelineStatus.plan_failed:
        # Distinct exit code from gate_failed (5): a plan failure means the model produced
        # nothing buildable, so there's nothing to --proceed-anyway with.
        print(result.error or "The model didn't return a usable design plan.")
        return 6
    if result.status is PipelineStatus.render_failed:
        print(f"Could not produce a valid model after retries.\n  {result.error}")
        return 4
    if result.report is not None:
        print(result.report.to_text())
    if result.status is PipelineStatus.gate_failed:
        print("\nPrintability Gate FAILED. Re-run with --proceed-anyway to override.")
        return 5
    if args.send:
        report = result.report
        if report is None or not (report.sliced and report.gcode_path):
            print(f"\nNothing to send to {args.send}: no G-code was produced.")
        elif report.gate_status == "fail":
            # ENG-201: --proceed-anyway lets a gate-FAILED part be sliced for export/inspection,
            # but a part the printability gate rejected is never dispatched to a printer.
            print(
                f"\nNot sending to {args.send}: this part FAILED the printability gate. "
                "--proceed-anyway lets you export it to inspect, but a gate-failed part is "
                "never sent to a printer."
            )
            print(f"Your G-code is on disk: {report.gcode_path}")
        else:
            _send_print_job(config, args.send, report.gcode_path)
    print(f"\nMesh: {result.mesh_path}")
    return 0


def _cmd_bench(config: Config, args: argparse.Namespace) -> int:
    from kimcad.benchmark import load_cases, make_case_runner, run_benchmark

    prompts_path = Path(args.prompts)
    if not prompts_path.exists():
        print(
            f"No benchmark prompts at {prompts_path}.\n"
            "Copy bench/prompts.example.yaml to bench/prompts.yaml and fill in the "
            "Appendix B prompts.",
            file=sys.stderr,
        )
        return 2

    pipeline = _build_pipeline(config, args)
    cases = load_cases(prompts_path)
    out_dir = _resolve_out(args.out)
    summary = run_benchmark(
        cases, make_case_runner(pipeline, out_dir, slice_for_grade=args.slice)
    )
    text = summary.to_text(min_success_rate=args.min_success_rate)
    # Persist the verdict before printing: a batch is minutes of CPU, and a
    # console-encoding error at print time must never discard the result.
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.txt").write_text(text, encoding="utf-8")
    print(text)
    if args.min_success_rate is not None and not summary.meets(args.min_success_rate):
        return 1
    return 0


def _cmd_bakeoff(config: Config, args: argparse.Namespace) -> int:
    from kimcad.bakeoff import run_bakeoff
    from kimcad.benchmark import load_cases

    prompts_path = Path(args.prompts)
    if not prompts_path.exists():
        print(
            f"No benchmark prompts at {prompts_path}.\n"
            "Copy bench/prompts.example.yaml to bench/prompts.yaml and fill in the "
            "Appendix B prompts.",
            file=sys.stderr,
        )
        return 2

    backends = [b.strip() for b in args.backends.split(",") if b.strip()]
    if len(backends) < 2:
        print("bakeoff needs at least two backends, e.g. --backends local_qwen,local", file=sys.stderr)
        return 2
    # Validate every backend resolves before running — a bake-off is many minutes of CPU
    # per backend, so fail fast on a typo'd key rather than after the first batch.
    known_backends = config.raw.get("llm", {}).get("backends", {})
    for key in backends:
        if key not in known_backends:
            names = ", ".join(known_backends) or "(none configured)"
            print(f"Unknown backend '{key}'. Configured backends: {names}", file=sys.stderr)
            return 2

    printer = config.printer(args.printer)
    material = config.material(args.material)
    incumbent = config.raw["llm"]["active"]
    cases = load_cases(prompts_path)
    out_dir = _resolve_out(args.out)

    bakeoff = run_bakeoff(
        backends,
        make_pipeline=lambda key: _pipeline_for_backend(config, key, printer, material),
        model_name_for=lambda key: config.llm_backend(key).model_name,
        cases=cases,
        out_root=out_dir,
        slice_for_grade=not args.no_slice,
        incumbent=incumbent,
    )
    text = bakeoff.to_text()
    # Persist before printing: a bake-off is a long CPU run, and a console-encoding
    # error at print time must never discard the result.
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "bakeoff.txt").write_text(text, encoding="utf-8")
    print(text)
    return 0


def _cmd_web(args: argparse.Namespace) -> int:
    from kimcad.webapp import serve

    # ENG-002 (stage-C): refuse a silent non-loopback bind. The server is unauthenticated
    # by design (single trusted user on loopback); exposing it is an explicit, warned act.
    if not _is_loopback_host(args.host) and not args.allow_remote:
        print(
            f"Error: refusing to bind non-loopback host {args.host!r} without --allow-remote.\n"
            "  KimCad's web server has NO authentication: anyone who can reach the port can\n"
            "  run the full design pipeline and dispatch prints. If you really mean to expose\n"
            "  it on this network, re-run with --allow-remote.",
            file=sys.stderr,
        )
        return 2
    if not _is_loopback_host(args.host):
        print(
            f"WARNING: serving on {args.host} with NO authentication - anyone on this "
            "network can use this KimCad, including sending prints.",
            file=sys.stderr,
        )
    serve(host=args.host, port=args.port, demo=args.demo, backend=args.backend)
    return 0


def _is_loopback_host(host: str) -> bool:
    """True for hosts that only ever reach this machine (localhost / 127.x / ::1)."""
    import ipaddress

    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _cmd_models(config: Config, args: argparse.Namespace) -> int:
    """Probe the machine + the installed Ollama models and print a recommendation. Purely
    advisory — it never rewrites config; the model stays choosable (config / --backend)."""
    from kimcad.model_advisor import (
        friendly_label,
        probe_hardware,
        probe_installed_models,
        recommend,
    )

    base_url = args.base_url
    if base_url is None:
        # ADV-003: probe the active backend's URL if it looks local, else the conventional
        # `local` backend, else the standard Ollama default.
        for key in (None, "local"):
            try:
                candidate = config.llm_backend(key).base_url
            except Exception:
                continue
            if "localhost" in candidate or "127.0.0.1" in candidate:
                base_url = candidate
                break
        if base_url is None:
            base_url = "http://localhost:11434/v1"

    hw = probe_hardware()
    installed = probe_installed_models(base_url)
    rec = recommend(hw, installed)

    print("Hardware")
    print(f"  {hw.summary()}")
    print()
    print(f"Installed models (Ollama @ {base_url})")
    if installed:
        for m in installed:
            size = f"  ({m.size_gb:.1f} GB)" if m.size_gb else ""
            label = friendly_label(m.name)
            tag = f"  -- {label}" if label else ""
            print(f"  - {m.name}{size}{tag}")
    else:
        print("  (none detected -- is Ollama running, with models pulled?)")
    print()
    print("Recommendation")
    if rec.primary is not None:
        state = "installed" if rec.installed else "NOT installed -- pull it first"
        print(f"  -> {rec.primary.label}  [{rec.primary.name}]  ({state})")
    print(f"  {rec.reason}")
    if rec.upgrade is not None:
        print(f"  Upgrade you could run: {rec.upgrade.label}  (ollama pull {rec.upgrade.name})")
    if rec.non_china_alternative is not None:
        alt = rec.non_china_alternative
        state = "installed" if rec.non_china_installed else f"not installed -- ollama pull {alt.name}"
        print(f"  Non-China local option: {alt.label}  [{alt.name}]  ({state})")
    # Stage 9: the photo/sketch on-ramps use a DEDICATED local vision model — surface its
    # state here too, so `kimcad models` is the one-stop setup check.
    try:
        vision = config.llm_backend("local").vision_model
    except Exception:  # noqa: BLE001 - advisory only
        vision = "qwen2.5vl:3b"
    have_vision = any(m.name == vision for m in installed)
    vstate = "installed" if have_vision else f"NOT installed -- ollama pull {vision}"
    print(f"  Vision model (photo/sketch on-ramps): {vision}  ({vstate})")
    print()
    print("The model is never hardwired. To choose one: set `llm.active` (or a backend's")
    print("`model_name`) in config/local.yaml, or pass `--backend <key>` to design/web/bench.")
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
        if args.command == "shell":
            from kimcad.shell import build_shell

            build_shell(demo=args.demo, backend=args.backend, start_gui=True)
            return 0
        # design / bench need config; loading it inside the try means a malformed
        # config.yaml fails with a clean message instead of a raw traceback.
        config = Config.load()
        if args.command == "design":
            return _cmd_design(config, args)
        if args.command == "bench":
            return _cmd_bench(config, args)
        if args.command == "bakeoff":
            return _cmd_bakeoff(config, args)
        if args.command == "models":
            return _cmd_models(config, args)
    except RuntimeError as e:
        # ToolMissingError (a RuntimeError) lands here too: e.g. OpenSCAD/OrcaSlicer never
        # fetched — the message already carries the fetch_tools.py recovery hint (QA-003).
        # Plain RuntimeError: e.g. a configured backend whose API key env var is unset.
        print(f"Error: {e}", file=sys.stderr)
        return 2
    except Exception as e:  # noqa: BLE001 — last-resort mapping, see below
        # QA-001: the most likely first-run failures must end in one actionable line, not a
        # traceback. Model-server down (Ollama not started) and model-not-pulled are matched
        # by class NAME (duck-typed, mirroring pipeline._is_model_unreachable) so the CLI
        # needn't import the OpenAI SDK; anything unrecognized re-raises — a real bug should
        # still crash loudly, not hide behind a friendly message.
        from kimcad.pipeline import MODEL_UNAVAILABLE_MESSAGE, _is_model_unreachable

        # UX-A-003 (stage-A gate): the recovery command names the CONFIGURED model, not a
        # hardcoded default — confidently-wrong advice is worse than generic advice.
        def _model_name() -> str:
            try:
                return Config.load().llm_backend(getattr(args, "backend", None)).model_name
            except Exception:  # noqa: BLE001 - advice fallback only; never mask the real error
                return "gemma4:e4b"

        if _is_model_unreachable(e):
            print(f"Error: {MODEL_UNAVAILABLE_MESSAGE}", file=sys.stderr)
            print(
                f"  Start Ollama, pull the model if you haven't (`ollama pull {_model_name()}`), "
                "then try again. `kimcad models` shows what's installed.",
                file=sys.stderr,
            )
            return 2
        if type(e).__name__ == "NotFoundError" and type(e).__module__.startswith("openai"):
            print(
                "Error: the model isn't available on your local AI server. "
                f"Pull it first (`ollama pull {_model_name()}`), then try again. "
                "`kimcad models` shows what's installed.",
                file=sys.stderr,
            )
            return 2
        raise
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
