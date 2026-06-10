import json
from types import SimpleNamespace

from kimcad.config import LLMBackend, Material, Printer
from kimcad.ir import DesignPlan
from kimcad.llm_provider import (
    LLMProvider,
    build_constraints_block,
    build_library_manifest,
)

BAMBU = Printer(
    key="bambu_p2s",
    name="Bambu Lab P2S",
    build_volume=(256, 256, 256),
    nozzle_diameter=0.4,
)
PLA = Material(
    key="pla", name="PLA", nozzle_temp=210, bed_temp=55, wall_multiplier=2.0, shrinkage=0.002
)
BACKEND = LLMBackend(
    key="test",
    provider="openai",
    base_url="http://localhost:0/v1",
    model_name="test-model",
    api_key_env=None,
    temperature=0.2,
    max_tokens=4096,
    supports_structured_output=True,
)


class FakeChatClient:
    """Records the kwargs passed to create() and returns a canned response."""

    def __init__(self, content: str):
        self._content = content
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        message = SimpleNamespace(content=self._content)
        choice = SimpleNamespace(message=message)
        return SimpleNamespace(choices=[choice])


def test_constraints_block_mentions_printer_and_min_wall():
    block = build_constraints_block(BAMBU, PLA)
    assert "Bambu Lab P2S" in block
    assert "256 × 256 × 256" in block
    assert "0.40 mm" in block  # nozzle
    assert "0.8 mm" in block  # min wall = 2.0 * 0.4


def test_library_manifest_lists_modules_and_signatures():
    manifest = build_library_manifest()
    assert "use <library/box.scad>;" in manifest
    assert "box(width, depth, height" in manifest
    assert "l_bracket(" in manifest


def test_generate_design_plan_parses_json_through_fences():
    plan_json = {
        "object_type": "bracket",
        "summary": "A simple L bracket.",
        "dimensions": {"arm": 40.0, "wall": 4.0},
        "bounding_box_mm": [40.0, 30.0, 40.0],
        "features": [],
        "tolerances": {"clearance_mm": 0.2},
        "printer": "bambu_p2s",
        "material": "pla",
        "assumptions": [],
        "open_questions": [],
    }
    fenced = "```json\n" + json.dumps(plan_json) + "\n```"
    client = FakeChatClient(fenced)
    provider = LLMProvider(BACKEND, client=client)

    plan = provider.generate_design_plan("an L bracket", BAMBU, PLA)

    assert isinstance(plan, DesignPlan)
    assert plan.object_type == "bracket"
    assert plan.bounding_box_mm == [40.0, 30.0, 40.0]

    # json_mode + supports_structured_output -> response_format requested
    call = client.calls[0]
    assert call["response_format"] == {"type": "json_object"}
    assert call["model"] == "test-model"
    # system prompt carries the constraints block
    assert call["messages"][0]["role"] == "system"
    assert "Bambu Lab P2S" in call["messages"][0]["content"]
    assert call["messages"][-1] == {"role": "user", "content": "an L bracket"}


def test_generate_design_plan_raises_plan_parse_error_on_schema_echo():
    # A too-small model echoing the JSON schema back: valid JSON, wrong shape. The parse
    # boundary must raise PlanParseError (carrying the underlying ValidationError), not let
    # a raw pydantic error escape.
    from kimcad.ir import design_plan_schema
    from kimcad.llm_provider import PlanParseError

    client = FakeChatClient(json.dumps(design_plan_schema()))
    provider = LLMProvider(BACKEND, client=client)
    try:
        provider.generate_design_plan("a box", BAMBU, PLA)
        raise AssertionError("expected PlanParseError")
    except PlanParseError as e:
        assert type(e.original).__name__ == "ValidationError"


def test_generate_design_plan_raises_plan_parse_error_on_bad_json():
    from kimcad.llm_provider import PlanParseError

    client = FakeChatClient("this is not json at all")
    provider = LLMProvider(BACKEND, client=client)
    try:
        provider.generate_design_plan("a box", BAMBU, PLA)
        raise AssertionError("expected PlanParseError")
    except PlanParseError as e:
        assert isinstance(e.original, json.JSONDecodeError)


def test_generate_design_plan_does_not_wrap_a_connection_error_as_plan_parse_error():
    # The network call (_complete) sits OUTSIDE the parse try, so a transport error must
    # escape as itself, NOT be wrapped as PlanParseError (which would mask an outage as a
    # "model too small" plan failure and stop the fallback chain from firing).
    import httpx
    from openai import APIConnectionError

    from kimcad.llm_provider import PlanParseError

    class _ConnDownClient:
        def __init__(self):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

        def _create(self, **kwargs):
            raise APIConnectionError(request=httpx.Request("POST", "http://localhost:11434/v1"))

    provider = LLMProvider(BACKEND, client=_ConnDownClient(), max_attempts=2, retry_wait_s=0)
    try:
        provider.generate_design_plan("a box", BAMBU, PLA)
        raise AssertionError("expected APIConnectionError")
    except PlanParseError as e:  # noqa: TRY203 - we are asserting this does NOT happen
        raise AssertionError("connection error was wrongly wrapped as PlanParseError") from e
    except APIConnectionError:
        pass  # correct: the transport error escaped un-wrapped


def test_generate_openscad_strips_fences_and_sends_plan():
    plan = DesignPlan(
        object_type="cube",
        summary="A 20mm cube.",
        dimensions={"size": 20.0},
        bounding_box_mm=[20.0, 20.0, 20.0],
        printer="bambu_p2s",
        material="pla",
    )
    scad = "```openscad\ncube(20);\n```"
    client = FakeChatClient(scad)
    provider = LLMProvider(BACKEND, client=client)

    out = provider.generate_openscad(plan, BAMBU, PLA)

    assert out == "cube(20);"
    call = client.calls[0]
    # codegen is not JSON mode
    assert "response_format" not in call
    assert "library/box.scad" in call["messages"][0]["content"]
    assert "Design plan:" in call["messages"][-1]["content"]


def test_history_is_threaded_between_system_and_user():
    client = FakeChatClient("```\ncube(1);\n```")
    provider = LLMProvider(BACKEND, client=client)
    plan = DesignPlan(
        object_type="cube",
        summary="x",
        dimensions={"size": 1.0},
        bounding_box_mm=[1.0, 1.0, 1.0],
        printer="bambu_p2s",
        material="pla",
    )
    history = [
        {"role": "user", "content": "earlier turn"},
        {"role": "assistant", "content": "earlier reply"},
    ]
    provider.generate_openscad(plan, BAMBU, PLA, history=history)

    msgs = client.calls[0]["messages"]
    assert msgs[0]["role"] == "system"
    assert msgs[1] == {"role": "user", "content": "earlier turn"}
    assert msgs[2] == {"role": "assistant", "content": "earlier reply"}
    assert msgs[-1]["role"] == "user"


def test_complete_retries_then_succeeds_on_connection_error(monkeypatch):
    # A transient Ollama drop (APIConnectionError) should be retried, not fail the call.
    # QA-002: the retry loop now probes reachability on a FIRST-attempt failure; pin the
    # probe to True ("server is listening — this is a mid-run drop") so the test stays
    # hermetic regardless of whether a real Ollama is running on the host.
    import httpx
    from openai import APIConnectionError

    class FlakyClient:
        def __init__(self, fail_n: int):
            self.calls = 0
            self._fail_n = fail_n
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

        def _create(self, **kwargs):
            self.calls += 1
            if self.calls <= self._fail_n:
                raise APIConnectionError(request=httpx.Request("POST", "http://localhost:11434/v1"))
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))])

    monkeypatch.setattr(LLMProvider, "_server_reachable", lambda self, timeout_s=2.0: True)
    client = FlakyClient(fail_n=2)
    provider = LLMProvider(BACKEND, client=client, retry_wait_s=0)
    out = provider._complete([{"role": "user", "content": "x"}], json_mode=False)
    assert out == "ok"
    assert client.calls == 3  # failed twice, succeeded on the third


def test_complete_raises_after_exhausting_retries(monkeypatch):
    import httpx
    from openai import APIConnectionError

    class DeadClient:
        def __init__(self):
            self.calls = 0
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

        def _create(self, **kwargs):
            self.calls += 1
            raise APIConnectionError(request=httpx.Request("POST", "http://localhost:11434/v1"))

    # Probe pinned True: a listening-but-failing server burns the full retry budget (the
    # never-up fast path is covered in test_first_run_errors.py).
    monkeypatch.setattr(LLMProvider, "_server_reachable", lambda self, timeout_s=2.0: True)
    client = DeadClient()
    provider = LLMProvider(BACKEND, client=client, max_attempts=3, retry_wait_s=0)
    try:
        provider._complete([{"role": "user", "content": "x"}], json_mode=False)
        raise AssertionError("expected APIConnectionError")
    except APIConnectionError:
        pass
    assert client.calls == 3


def test_structured_output_suppressed_when_backend_lacks_support():
    backend = LLMBackend(
        key="local",
        provider="ollama",
        base_url="http://localhost:11434/v1",
        model_name="qwen3:8b",
        api_key_env=None,
        temperature=0.2,
        max_tokens=4096,
        supports_structured_output=False,
    )
    plan_json = {
        "object_type": "cube",
        "summary": "x",
        "dimensions": {"size": 1.0},
        "bounding_box_mm": [1.0, 1.0, 1.0],
        "printer": "bambu_p2s",
        "material": "pla",
    }
    client = FakeChatClient(json.dumps(plan_json))
    provider = LLMProvider(backend, client=client)

    provider.generate_design_plan("a cube", BAMBU, PLA)

    assert "response_format" not in client.calls[0]
