import io
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


class _NativeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _mock_native_chat(monkeypatch, content, capture=None):
    """Stub Ollama's native /api/chat — the LOCAL design-plan transport (schema-constrained
    `format`). Returns `content` as the assistant message; optionally captures the request body.

    ENG-007: the plan path first sends a cheap, body-less GET (``_native_responsive``) to fail-fast
    on a wedged server; that probe is answered with an empty OK here, and only the POST that carries
    a JSON body is captured — so the responsiveness pre-flight doesn't clobber the captured body."""
    import kimcad.llm_provider as lp

    def _urlopen(req, timeout=None):
        data = getattr(req, "data", None)
        if data is None:  # the GET responsiveness probe — answer OK, don't capture
            return _NativeResp(b"{}")
        if capture is not None:
            capture["body"] = json.loads(data)
        return _NativeResp(json.dumps({"message": {"content": content}}).encode())

    monkeypatch.setattr(lp.urllib.request, "urlopen", _urlopen)


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


def test_generate_design_plan_parses_json_through_fences(monkeypatch):
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
    # BACKEND is a loopback host -> a local Ollama backend -> the plan goes through the native
    # /api/chat schema-constrained `format` path. The parser still tolerates stray fences.
    fenced = "```json\n" + json.dumps(plan_json) + "\n```"
    cap: dict = {}
    _mock_native_chat(monkeypatch, fenced, cap)
    provider = LLMProvider(BACKEND, client=FakeChatClient("unused"))

    plan = provider.generate_design_plan("an L bracket", BAMBU, PLA)

    assert isinstance(plan, DesignPlan)
    assert plan.object_type == "bracket"
    assert plan.bounding_box_mm == [40.0, 30.0, 40.0]

    # local backend -> native /api/chat with the plan JSON schema as the token-level `format`
    body = cap["body"]
    assert "properties" in body["format"]  # the DesignPlan JSON schema
    assert body["model"] == "test-model"
    assert body["messages"][0]["role"] == "system"
    assert "Bambu Lab P2S" in body["messages"][0]["content"]
    assert body["messages"][-1] == {"role": "user", "content": "an L bracket"}


def test_generate_design_plan_raises_plan_parse_error_on_schema_echo(monkeypatch):
    # A too-small model echoing the JSON schema back: valid JSON, wrong shape. The parse
    # boundary must raise PlanParseError (carrying the underlying ValidationError), not let
    # a raw pydantic error escape.
    from kimcad.ir import design_plan_schema
    from kimcad.llm_provider import PlanParseError

    _mock_native_chat(monkeypatch, json.dumps(design_plan_schema()))
    provider = LLMProvider(BACKEND, client=FakeChatClient("unused"))
    try:
        provider.generate_design_plan("a box", BAMBU, PLA)
        raise AssertionError("expected PlanParseError")
    except PlanParseError as e:
        assert type(e.original).__name__ == "ValidationError"


def test_generate_design_plan_raises_plan_parse_error_on_bad_json(monkeypatch):
    from kimcad.llm_provider import PlanParseError

    # Even with the schema-constrained `format`, a model can return empty/garbage; the parse
    # boundary still raises PlanParseError carrying the JSONDecodeError.
    _mock_native_chat(monkeypatch, "this is not json at all")
    provider = LLMProvider(BACKEND, client=FakeChatClient("unused"))
    try:
        provider.generate_design_plan("a box", BAMBU, PLA)
        raise AssertionError("expected PlanParseError")
    except PlanParseError as e:
        assert isinstance(e.original, json.JSONDecodeError)


def test_generate_design_plan_does_not_wrap_a_connection_error_as_plan_parse_error(monkeypatch):
    # The network call (_complete_plan) sits OUTSIDE the parse try, so a transport error must
    # escape as itself, NOT be wrapped as PlanParseError (which would mask an outage as a
    # "model too small" plan failure and stop the fallback chain from firing). On the local
    # native path that transport error is a urllib URLError.
    import urllib.error

    import kimcad.llm_provider as lp
    from kimcad.llm_provider import PlanParseError

    def _down(req, timeout=None):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(lp.urllib.request, "urlopen", _down)
    # First-attempt failure + an unreachable probe -> raise now (don't burn the retry budget).
    monkeypatch.setattr(LLMProvider, "_server_reachable", lambda self, timeout_s=2.0: False)
    provider = LLMProvider(BACKEND, client=FakeChatClient("unused"), max_attempts=2, retry_wait_s=0)
    try:
        provider.generate_design_plan("a box", BAMBU, PLA)
        raise AssertionError("expected URLError")
    except PlanParseError as e:  # noqa: TRY203 - we are asserting this does NOT happen
        raise AssertionError("connection error was wrongly wrapped as PlanParseError") from e
    except urllib.error.URLError:
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


def test_local_ollama_backend_uses_native_schema_constrained_format(monkeypatch):
    # A local Ollama backend plans via the NATIVE /api/chat path with the DesignPlan JSON schema
    # as the token-level `format` constraint (so a model that wraps JSON in prose/fences/comments
    # still yields a parseable object), NOT the OpenAI-compatible client. The OpenAI client is left
    # untouched for this call.
    backend = LLMBackend(
        key="local",
        provider="ollama",
        base_url="http://localhost:11434/v1",
        model_name="qwen2.5:7b",
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
    cap: dict = {}
    _mock_native_chat(monkeypatch, json.dumps(plan_json), cap)
    client = FakeChatClient(json.dumps(plan_json))
    provider = LLMProvider(backend, client=client)

    provider.generate_design_plan("a cube", BAMBU, PLA)

    assert client.calls == []  # the OpenAI client was NOT used for a local plan
    assert "properties" in cap["body"]["format"]  # native schema-constrained `format`
    assert cap["body"]["model"] == "qwen2.5:7b"


def test_describe_image_targets_the_dedicated_vision_model(monkeypatch):
    """Stage 9: the photo/sketch reads go to the DEDICATED vision model (gemma4:e4b's
    vision is broken on this stack — see docs/benchmarks/stage-9-vision-onramps.md), and
    the image rides along base64-encoded on the user message."""
    import io
    import json as _json

    import kimcad.llm_provider as lp

    seen = {}

    def _fake_urlopen(req, timeout=None):
        seen["body"] = _json.loads(req.data)
        resp = io.BytesIO(_json.dumps({"message": {"content": "a part"}}).encode())
        resp.__enter__ = lambda *a: resp
        resp.__exit__ = lambda *a: False
        return resp

    monkeypatch.setattr(lp.urllib.request, "urlopen", _fake_urlopen)
    provider = LLMProvider(BACKEND, client=FakeChatClient("unused"))
    out = provider.describe_sketch(b"png-bytes", BAMBU, PLA)
    assert out == "a part"
    assert seen["body"]["model"] == BACKEND.vision_model  # NOT the chat model
    assert seen["body"]["model"] != BACKEND.model_name
    assert seen["body"]["messages"][1]["images"]  # the image is attached


def test_missing_vision_model_raises_typed_with_pull_command(monkeypatch):
    """Stage 9: Ollama 404 for the vision model = a setup state with the exact recovery
    command — never a generic transport error that ends up blaming the user's image."""
    import urllib.error

    import kimcad.llm_provider as lp
    from kimcad.llm_provider import VisionModelMissing

    def _404(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 404, "model not found", {}, None)

    monkeypatch.setattr(lp.urllib.request, "urlopen", _404)
    provider = LLMProvider(BACKEND, client=FakeChatClient("unused"))
    try:
        provider.describe_photo(b"png-bytes", BAMBU, PLA)
        raise AssertionError("expected VisionModelMissing")
    except VisionModelMissing as e:
        assert "Settings" in str(e)  # ENG-005: recovery points to Settings, not "ollama pull"
        assert "download" in str(e).lower()
        assert "ollama pull" not in str(e)  # no brand leak


def test_non_404_vision_http_error_is_a_read_error_not_missing_model(monkeypatch):
    """TEST-004 (stage-9 gate): a 5xx/429 from Ollama must NOT masquerade as a missing
    model (wrong advice) — it maps to VisionReadError ("try again in a moment")."""
    import urllib.error

    import kimcad.llm_provider as lp
    from kimcad.llm_provider import VisionModelMissing, VisionReadError

    def _500(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 500, "model runner crashed", {}, None)

    monkeypatch.setattr(lp.urllib.request, "urlopen", _500)
    provider = LLMProvider(BACKEND, client=FakeChatClient("unused"))
    try:
        provider.describe_photo(b"png-bytes", BAMBU, PLA)
        raise AssertionError("expected VisionReadError")
    except VisionModelMissing:
        raise AssertionError("a 500 must not claim the model is missing")
    except VisionReadError as e:
        assert e.code == 500
        assert "try again" in str(e).lower()


def _cloud_backend(base_url: str) -> LLMBackend:
    return LLMBackend(
        key="cloud", provider="openai_compatible", base_url=base_url,
        model_name="x", api_key_env=None, temperature=0.2, max_tokens=100,
        supports_structured_output=True,
    )


def test_build_client_refuses_saved_key_to_unlisted_cloud_host(monkeypatch):
    # ENG-001 (audit-team-b4): a tampered config naming an attacker cloud host must NOT receive a
    # saved API key — building the client refuses before the OpenAI client (and the Bearer header)
    # is ever constructed.
    from kimcad.config import UntrustedCloudHost

    monkeypatch.delenv("KIMCAD_ALLOW_CUSTOM_CLOUD_HOST", raising=False)
    backend = _cloud_backend("https://attacker.example/v1")
    try:
        LLMProvider(backend, api_key="sk-secret-key")
        raise AssertionError("expected UntrustedCloudHost")
    except UntrustedCloudHost as e:
        assert "attacker.example" in str(e)


def test_build_client_allows_saved_key_to_shipped_cloud_hosts(monkeypatch):
    # ENG-001: the shipped OpenRouter + DeepSeek endpoints accept a saved key (the in-app Settings
    # path). The real OpenAI client is built; no exception.
    monkeypatch.delenv("KIMCAD_ALLOW_CUSTOM_CLOUD_HOST", raising=False)
    for url in ("https://openrouter.ai/api/v1", "https://api.deepseek.com/v1"):
        provider = LLMProvider(_cloud_backend(url), api_key="sk-secret-key")
        assert provider.client is not None


def test_build_client_escape_hatch_allows_custom_cloud_host(monkeypatch):
    # ENG-001: the documented opt-out lets an advanced user knowingly send a saved key to a custom
    # endpoint. Fail closed without it (covered above); succeed with it set.
    monkeypatch.setenv("KIMCAD_ALLOW_CUSTOM_CLOUD_HOST", "1")
    provider = LLMProvider(_cloud_backend("https://my-proxy.internal/v1"), api_key="sk-secret-key")
    assert provider.client is not None


def test_build_client_keyless_cloud_backend_is_not_gated(monkeypatch):
    # ENG-001: the validation guards SAVED KEYS. A backend with no key (the "not-needed" sentinel)
    # sends no credential, so an arbitrary base_url is not a key-exfiltration path and is not gated.
    monkeypatch.delenv("KIMCAD_ALLOW_CUSTOM_CLOUD_HOST", raising=False)
    provider = LLMProvider(_cloud_backend("https://attacker.example/v1"))  # no api_key
    assert provider.client is not None


def test_native_plan_path_fails_fast_on_wedged_but_listening_server(monkeypatch):
    # ENG-007 (audit-team-b4): a server that ACCEPTS the connection but never responds must fail
    # fast (within the short connect/first-byte budget) instead of blocking for the full timeout_s.
    # The responsiveness pre-flight GET times out -> the call raises promptly, never reaching the
    # long-budget generation urlopen.
    import socket

    import kimcad.llm_provider as lp

    backend = LLMBackend(
        key="local", provider="ollama", base_url="http://localhost:11434/v1",
        model_name="qwen2.5:7b", api_key_env=None, temperature=0.2,
        max_tokens=100, supports_structured_output=False,
        timeout_s=1200.0,  # the long generation budget we must NOT block on
    )
    calls: list[float | None] = []

    def _wedged_urlopen(req, timeout=None):
        # Record the timeout each urlopen was given, then emulate a wedged server: it accepts the
        # connection but never answers, so the read times out after `timeout` seconds.
        calls.append(timeout)
        raise socket.timeout("timed out")

    monkeypatch.setattr(lp.urllib.request, "urlopen", _wedged_urlopen)
    provider = LLMProvider(backend, client=FakeChatClient("unused"), max_attempts=6, retry_wait_s=0)
    try:
        provider.generate_design_plan("a box", BAMBU, PLA)
        raise AssertionError("expected a transport error")
    except Exception as e:  # noqa: BLE001 - asserting it fails fast, not which exact type
        assert not isinstance(e, AssertionError)
    # The FIRST urlopen (the responsiveness probe) used the SHORT budget, not the 1200 s read
    # budget — proof the wedged server can't hold the call open for the full timeout_s.
    assert calls, "the responsiveness probe should have run"
    assert calls[0] == provider._NATIVE_CONNECT_TIMEOUT_S
    assert all(t == provider._NATIVE_CONNECT_TIMEOUT_S for t in calls)


def test_vision_refuses_a_non_local_host_structurally(monkeypatch):
    """ENG-002 (stage-9 gate): the image-stays-local promise is enforced INSIDE the
    transport — a cloud base_url is refused before any request is built."""
    from kimcad.config import LLMBackend

    cloud = LLMBackend(
        key="cloud", provider="openrouter", base_url="https://openrouter.ai/api/v1",
        model_name="x", api_key_env=None, temperature=0.2, max_tokens=100,
        supports_structured_output=True,
    )
    provider = LLMProvider(cloud, client=FakeChatClient("unused"))
    try:
        provider.describe_photo(b"png-bytes", BAMBU, PLA)
        raise AssertionError("expected refusal")
    except RuntimeError as e:
        assert "local-only" in str(e)
