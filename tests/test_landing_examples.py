"""ENG-002 / UX-001 — the landing one-tap examples must build on the DETERMINISTIC template
path with the default local model, not gamble on a free-form codegen run that 100-160 s later
dead-ends at the experimental offer. Two checks, escalating in cost:

1. ``test_each_landing_example_intent_maps_to_a_family`` (always runs, no model): each example is
   phrased around a real template family; its canonical object_type maps. This locks the
   chip↔family design intent so a catalog edit can't silently orphan a landing chip.
2. ``test_default_model_plans_each_landing_example_to_a_family`` (Ollama-gated): the REAL default
   model plans each example and the plan maps to a family via the (broadened) matcher — proving
   the model + matcher + wording connect end to end. Skips where the default model isn't pulled
   (CI has no Ollama lane yet — TEST-003); runs on the dev box and any future lane.

Keep ``EXAMPLES`` in sync with ``frontend/src/components/Landing.tsx``'s ``EXAMPLES`` array.
"""
from __future__ import annotations

import functools

import pytest

from kimcad.config import Config
from kimcad.ir import DesignPlan
from kimcad.templates import default_registry

# (landing prompt, the family alias it is phrased around) — mirrors Landing.tsx EXAMPLES.
EXAMPLES = [
    ("an 80 × 60 × 40 mm project box with a lid", "project box"),
    ("a desk cable clip for an 8 mm cable", "cable clip"),
    ("a round trinket dish, 90 mm across", "trinket dish"),
]


@pytest.mark.parametrize("prompt,canonical", EXAMPLES)
def test_each_landing_example_intent_maps_to_a_family(prompt, canonical):
    plan = DesignPlan(
        object_type=canonical, summary=prompt, dimensions={},
        printer="bambu_p2s", material="pla",
    )
    match = default_registry().match(plan)
    assert match is not None, f"landing example {prompt!r} (alias {canonical!r}) maps to no family"


@functools.lru_cache(maxsize=1)
def _default_model() -> tuple[bool, str, str]:
    """(is the configured default chat model pulled, its name, the probe base_url). Cached so the
    Ollama probe runs at most once per session, and only when the gated test actually runs."""
    from kimcad.model_advisor import probe_installed_models

    backend = Config.load().llm_backend(None)
    names = {m.name for m in probe_installed_models(backend.base_url)}
    ok = any(backend.model_name == n or backend.model_name in n for n in names)
    return ok, backend.model_name, backend.base_url


@pytest.mark.live  # TEST-102: runs the REAL default model; joins the gate's `-m live … 0 skipped`
@pytest.mark.parametrize("prompt,canonical", EXAMPLES)
def test_default_model_plans_each_landing_example_to_a_family(prompt, canonical):
    ok, model, base = _default_model()
    if not ok:
        pytest.skip(f"default chat model {model!r} not pulled at {base} (no Ollama lane — TEST-003)")

    from kimcad.llm_provider import LLMProvider

    config = Config.load()
    provider = LLMProvider(config.llm_backend(None))
    plan = provider.generate_design_plan(prompt, config.printer(None), config.material(None))
    match = default_registry().match(plan)
    assert match is not None, (
        f"the default model planned {prompt!r} as object_type={plan.object_type!r}, which maps to "
        f"NO template family — the landing chip would dead-end at the experimental-codegen offer"
    )
