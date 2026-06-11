"""KC-4 — measure the realized CadQuery fallback lift on the shipping local model.

The LLM-CadQuery fallback only fires when the LLM-OpenSCAD codegen path fails the gate, which
only happens when there is NO template match (templates emit OpenSCAD and never touch CadQuery).
So the realized union lift = the number of prompts whose WINNING result was built by the CadQuery
backend (``result.backend == "cadquery"`` with a non-FAIL outcome). Because the fallback can only
replace an OpenSCAD result that failed (``Pipeline._better_result``), this single instrumented
run — CadQuery enabled — measures the lift directly, with no two-pass LLM noise.

Run (CadQuery is enabled via config/local.yaml's binaries.cadquery_python):

    .venv/Scripts/python -m scripts.measure_cadquery_lift            # or: python scripts/measure_cadquery_lift.py

Writes output/kc4-cadquery-lift/result.json and prints a verdict.
"""

from __future__ import annotations

import json
import time
from argparse import Namespace
from pathlib import Path

from kimcad.benchmark import load_cases
from kimcad.cli import _build_pipeline
from kimcad.config import Config


def main() -> int:
    config = Config.load()
    interp = config.cadquery_interpreter()
    args = Namespace(printer=None, material=None, backend=None)
    pipeline = _build_pipeline(config, args)
    cases = load_cases(Path("bench/prompts.yaml"))
    out_root = Path("output/kc4-cadquery-lift")
    out_root.mkdir(parents=True, exist_ok=True)

    print(f"CadQuery interpreter resolved: {interp}")
    print(f"Model: {config.llm_backend(None).model_name}")
    print(f"Running {len(cases)} prompts (CadQuery enabled)...\n", flush=True)

    rows = []
    for i, case in enumerate(cases, 1):
        started = time.monotonic()
        result = pipeline.run(case.prompt, out_root / case.id)
        dur = time.monotonic() - started
        template = getattr(result, "template_family", None)
        backend = getattr(result, "backend", "openscad")
        gate = str(result.gate.status) if getattr(result, "gate", None) else None
        row = {
            "id": case.id,
            "prompt": case.prompt,
            "status": result.status.value,
            "gate": gate,
            "backend": backend,
            "template_family": template,
            "llm_codegen_path": template is None,
            "duration_s": round(dur, 1),
        }
        rows.append(row)
        print(
            f"[{i:2}/{len(cases)}] {case.id:24} status={row['status']:11} "
            f"gate={str(gate):10} backend={backend:9} "
            f"{'TEMPLATE' if template else 'LLM-CODEGEN'} ({dur:.0f}s)",
            flush=True,
        )

    completed = [r for r in rows if r["status"] == "completed"]
    codegen = [r for r in rows if r["llm_codegen_path"]]
    cq_wins = [r for r in rows if r["backend"] == "cadquery" and r["status"] == "completed"]

    summary = {
        "total": len(rows),
        "completed": len(completed),
        "llm_codegen_prompts": len(codegen),
        "cadquery_fallback_wins": len(cq_wins),
        "cadquery_win_ids": [r["id"] for r in cq_wins],
        "realized_lift": len(cq_wins),
        "rows": rows,
    }
    (out_root / "result.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("\n=== KC-4 VERDICT ===")
    print(f"Prompts total:                 {len(rows)}")
    print(f"Completed (passed pipeline):   {len(completed)}")
    print(f"Hit LLM-codegen path:          {len(codegen)}  (the only path CadQuery can help)")
    print(f"CadQuery fallback WON:         {len(cq_wins)}  <- realized lift")
    if cq_wins:
        print(f"  rescued: {', '.join(r['id'] for r in cq_wins)}")
    print(f"\nWrote {out_root / 'result.json'}")
    if len(cq_wins) == 0:
        print(
            "\nLIFT = 0 on this prompt set/model: the LLM-CadQuery fallback rescued nothing. "
            "Recommends dropping the LLM-CadQuery fallback (collapses KC-3; KC-2 -> templates-only)."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
