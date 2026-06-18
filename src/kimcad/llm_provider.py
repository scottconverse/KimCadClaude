"""LLM integration layer (spec §6.1).

One module wraps all LLM communication via the OpenAI SDK as the universal client —
DeepSeek, OpenRouter, Gemini (proxy), and local runtimes all speak the
OpenAI-compatible chat-completions format. Two jobs:

    generate_design_plan(prompt, history, ...) -> DesignPlan
    generate_openscad(plan, history, ...)      -> str (OpenSCAD source)

The long system prompt is reused across a conversation to maximize prefix-cache hits
(§7.1). The OpenAI client is injectable so the assembly logic is testable offline.

``FallbackProvider`` wraps a primary ``LLMProvider`` with an optional alt backend.
On a connection, timeout, or model-not-found error from the primary, the call is
retried against the alt. Thread-local stickiness keeps a falling-back request on alt
for its remaining calls, avoiding re-trying a dead primary on every codegen retry.
"""

from __future__ import annotations

import base64
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlsplit, urlunsplit

import yaml
from pydantic import ValidationError

from kimcad.config import LLMBackend, Material, Printer
from kimcad.ir import DesignPlan, design_plan_schema, normalize_plan_dict, parse_design_plan

PROMPT_DIR = Path(__file__).parent / "prompts"
# 11.4-audit FINDING-002: the library manifest reads from the INSTALL root (the seam),
# not a second parents[2] copy that could disagree with openscad_runner's routed twin.
from kimcad.config import PROJECT_ROOT as _ROOT  # noqa: E402

LIBRARY_DIR = _ROOT / "library"

_FENCE = re.compile(r"^\s*```(?:\w+)?\s*|\s*```\s*$", re.MULTILINE)

# Exceptions from turning untrusted model output into a DesignPlan: bad JSON
# (JSONDecodeError < ValueError), schema-invalid JSON (pydantic ValidationError), or a
# non-dict body (TypeError/AttributeError/KeyError during normalize).
_PLAN_PARSE_ERRORS = (ValueError, TypeError, KeyError, AttributeError, ValidationError)


class VisionModelMissing(Exception):
    """The dedicated local vision model isn't pulled (Ollama answered 404 for it).

    Stage 9: a setup state with an exact recovery command — the web layer maps it to a
    typed response so the UI never blames the user's image for a missing model.
    (UX-904: plain copy, no backticks/jargon — this string renders in the on-ramp card.)"""

    def __init__(self, model: str):
        self.model = model
        super().__init__(
            "KimCad's image-reading model isn't downloaded yet. "
            "Use Settings > AI setup to download it, then try again."
        )


class VisionReadError(Exception):
    """The local vision backend errored (a non-404 HTTPError: 5xx OOM loading the model,
    429, a runner crash). ENG-001 (stage-9 gate): an infrastructure hiccup must never be
    blamed on the user's image — the web layer maps this to a typed try-again response
    and logs the detail server-side."""

    def __init__(self, code: int):
        self.code = code
        super().__init__(
            "Your local AI had trouble reading the image just now (it may still be "
            "loading). Wait a moment and try again."
        )


class PlanParseError(Exception):
    """The model's response could not be parsed into a DesignPlan -- bad JSON, or valid JSON
    that doesn't match the schema (e.g. a too-small model echoing the schema back).

    Distinct from a connection/timeout error: this is a bad *output*, not a transport
    failure. Raised only at the parse boundary so the pipeline can map it to a clean
    ``plan_failed`` without a broad catch that could mask an unrelated bug. ``original``
    is the underlying parse exception (for a precise, debuggable detail)."""

    def __init__(self, message: str, *, original: Exception | None = None):
        super().__init__(message)
        self.original = original


class ChatClient(Protocol):
    """Minimal structural type for the bit of the OpenAI client we use."""

    @property
    def chat(self) -> Any: ...


class Provider(Protocol):
    """What the pipeline needs from an LLM provider: a design-plan generator and an
    OpenSCAD generator. Both :class:`LLMProvider` and :class:`FallbackProvider` satisfy
    this structurally (no inheritance), so the pipeline can be wired with either."""

    def generate_design_plan(
        self,
        prompt: str,
        printer: Printer,
        material: Material,
        history: list[dict[str, str]] | None = None,
    ) -> DesignPlan: ...

    def generate_openscad(
        self,
        plan: DesignPlan,
        printer: Printer,
        material: Material,
        history: list[dict[str, str]] | None = None,
    ) -> str: ...

    # ENG-004: the photo on-ramp's local-vision entry point. Declared on the Protocol so the
    # contract is total and type-checked — every provider must answer it (FallbackProvider delegates
    # to its primary). The trust rule (vision stays local) is enforced by the caller, not here.
    def describe_photo(
        self,
        image_bytes: bytes,
        printer: Printer,
        material: Material,
    ) -> str: ...

    # Stage 9: the sketch on-ramp's local-vision entry point — read a dimensioned sketch into an
    # editable seed. Declared on the Protocol so the contract stays total + type-checked.
    def describe_sketch(
        self,
        image_bytes: bytes,
        printer: Printer,
        material: Material,
    ) -> str: ...


def _load_prompt(name: str) -> str:
    return (PROMPT_DIR / name).read_text(encoding="utf-8")


def _strip_fences(text: str) -> str:
    return _FENCE.sub("", text).strip()


def _native_chat_url(base_url: str) -> str:
    """Map an OpenAI-compatible base_url (.../v1) to Ollama's native ``/api/chat`` endpoint,
    preserving scheme+host and discarding the path tail (mirrors the vision read's derivation)."""
    parts = urlsplit(base_url)
    if parts.scheme and parts.netloc:
        return urlunsplit((parts.scheme, parts.netloc, "/api/chat", "", ""))
    return base_url.rstrip("/").removesuffix("/v1") + "/api/chat"


def _is_ollama_backend(backend: LLMBackend) -> bool:
    """True for a local Ollama-style backend, where the native ``/api/chat`` ``format`` field
    (token-level JSON-schema constraint) is available: the provider declares ``ollama``, the
    endpoint is the Ollama port, or it's a loopback host (the local-first default). Cloud backends
    (OpenRouter/DeepSeek) are False — they keep the standard OpenAI-compatible json-mode call."""
    base = backend.base_url or ""
    if getattr(backend, "provider", "") == "ollama" or "11434" in base:
        return True
    host = (urlsplit(base).hostname or "").lower()
    return host in ("localhost", "127.0.0.1", "::1") or host.startswith("127.")


def build_constraints_block(printer: Printer, material: Material) -> str:
    lines = [f"- Printer: {printer.name}"]
    bv = printer.build_volume
    if bv is not None:
        lines.append(
            f"- Build volume (x, y, z): {bv[0]:.0f} × {bv[1]:.0f} × {bv[2]:.0f} mm "
            "(the part must fit inside this)"
        )
    if printer.nozzle_diameter is not None:
        lines.append(f"- Nozzle diameter: {printer.nozzle_diameter:.2f} mm")
    lines.append(
        f"- Material: {material.name} "
        f"(nozzle {material.nozzle_temp}°C, bed {material.bed_temp}°C)"
    )
    if printer.nozzle_diameter is not None:
        lines.append(
            f"- Minimum wall thickness: {material.min_wall_mm(printer.nozzle_diameter):.1f} mm"
        )
    lines.append(
        f"- Default hole/peg clearance: 0.2 mm "
        f"(account for ~{material.shrinkage * 100:.1f}% shrinkage)"
    )
    return "\n".join(lines) + "\n"


def build_library_manifest(library_dir: Path = LIBRARY_DIR) -> str:
    manifest_path = library_dir / "manifest.yaml"
    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    lines: list[str] = []
    for mod in data.get("modules", []):
        lines.append(f"`use <library/{mod['file']}>;` — {mod['summary']}")
        for sig in mod.get("signatures", []):
            lines.append(f"    {sig}")
    return "\n".join(lines)


class LLMProvider:
    def __init__(
        self,
        backend: LLMBackend,
        client: ChatClient | None = None,
        *,
        api_key: str | None = None,
        max_attempts: int = 6,
        retry_wait_s: float = 30.0,
    ):
        self.backend = backend
        # An explicit api_key (e.g. a key the user saved in the in-app Settings — Slice 6 MS-3)
        # takes precedence over the backend's api_key_env lookup, so a cloud backend can run on a
        # locally-saved consumer key without an environment variable.
        self.client = client if client is not None else self._build_client(backend, api_key=api_key)
        # A local CPU model server (Ollama) can briefly drop or restart mid-batch; retry
        # connection/timeout errors with a wait long enough to bridge a server restart
        # plus an 8 GB model reload, so one hiccup doesn't fail the case.
        self.max_attempts = max_attempts
        self.retry_wait_s = retry_wait_s

    @staticmethod
    def _build_client(backend: LLMBackend, *, api_key: str | None = None) -> ChatClient:
        from openai import OpenAI

        # An explicit (saved) key wins; otherwise fall back to the backend's env var.
        key = api_key
        if key is None and backend.api_key_env:
            key = os.environ.get(backend.api_key_env) or ""
            if not key:
                raise RuntimeError(
                    f"Environment variable {backend.api_key_env} is not set; "
                    f"the {backend.key} backend needs an API key."
                )
        # ENG-001 (audit-team-b4): before a REAL key is bound to a client, validate the cloud
        # base_url against the shipped host allow-list (https + openrouter.ai / api.deepseek.com),
        # so a tampered/imported config/local.yaml can't redirect a saved Bearer credential to an
        # attacker host. Loopback backends are exempt (the key never leaves the box); the explicit
        # KIMCAD_ALLOW_CUSTOM_CLOUD_HOST=1 escape hatch is honored inside validate_cloud_base_url.
        # Mirrors the loopback-pin already enforced on the vision + model-pull paths.
        if key:
            from kimcad.config import Config

            Config.validate_cloud_base_url(backend.base_url)
        else:
            key = "not-needed"
        # QA-004: split connect vs read. A generation may legitimately take many minutes on the
        # CPU target (the long read budget), but a TCP connect to a server that's up answers in
        # well under 5 s — so a wedged/absent server fails an attempt in seconds, not in
        # `timeout_s`. httpx ships with the openai client.
        import httpx

        # ENG-002 (stage-A gate): max_retries=0 — KimCad's own loop owns retry policy; the
        # SDK's default 2 internal retries stacked under it (up to 18 connect cycles).
        timeout = httpx.Timeout(backend.timeout_s, connect=5.0)
        return OpenAI(base_url=backend.base_url, api_key=key, timeout=timeout, max_retries=0)

    def _complete(self, messages: list[dict[str, str]], *, json_mode: bool) -> str:
        kwargs: dict[str, Any] = {
            "model": self.backend.model_name,
            "messages": messages,
            "temperature": self.backend.temperature,
            "max_tokens": self.backend.max_tokens,
        }
        if json_mode and self.backend.supports_structured_output:
            kwargs["response_format"] = {"type": "json_object"}

        from openai import APIConnectionError, APITimeoutError

        last_err: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                resp = self.client.chat.completions.create(**kwargs)
                return resp.choices[0].message.content or ""
            except (APIConnectionError, APITimeoutError) as e:
                last_err = e
                # QA-002: the 6×30 s retry loop exists to bridge a MID-RUN server restart — a
                # server that was up and dropped. A server that was NEVER up (the dominant
                # non-developer first-run state: Ollama not started) must fail fast instead of
                # sitting silent for ~4 minutes. A first-attempt connection error plus a failed
                # 2 s TCP probe means "never up" → raise now; a probe that answers means the
                # drop is transient → keep the full retry budget.
                if attempt == 1 and not self._server_reachable():
                    raise
                if attempt < self.max_attempts:
                    time.sleep(self.retry_wait_s)
        raise last_err if last_err is not None else RuntimeError("LLM call failed")

    def _server_reachable(self, timeout_s: float = 2.0) -> bool:
        """A bare TCP connect to the backend host:port. Cheap, no HTTP — just 'is anything
        listening?'. Used only to distinguish never-up from dropped-mid-run (QA-002).

        ENG-003 (stage-A gate): the probe is meaningful ONLY for local/loopback backends —
        the case the fail-fast exists for (Ollama never started). For a cloud backend a raw
        TCP verdict lies in both directions (a proxy-only network can't connect directly
        even when the API is fine; a CDN edge accepts connects even when the service behind
        it is down), so non-local hosts always report reachable and keep the retry budget."""
        import ipaddress
        import socket
        from urllib.parse import urlparse

        u = urlparse(self.backend.base_url)
        host = u.hostname or "localhost"
        if host != "localhost":
            try:
                if not ipaddress.ip_address(host).is_loopback:
                    return True  # non-loopback IP (cloud/LAN) — never fail-fast on a TCP probe
            except ValueError:
                return True  # a DNS name other than localhost — same: don't probe-judge it
        port = u.port or (443 if u.scheme == "https" else 80)
        try:
            with socket.create_connection((host, port), timeout=timeout_s):
                return True
        except OSError:
            return False

    def _complete_plan(self, messages: list[dict[str, str]]) -> str:
        """The design-plan completion. For a local Ollama backend, constrain the output to the
        plan JSON schema at the TOKEN LEVEL via Ollama's native ``/api/chat`` ``format`` field, so
        a model that would otherwise wrap its JSON in prose, ``//`` comments, or ``` fences still
        yields a parseable object (KC model-robustness: on-target, gemma/llama produced
        correct-but-wrapped plans that ``json.loads`` rejected; the schema constraint fixes that).
        Cloud / non-Ollama backends keep the standard OpenAI-compatible json-mode call."""
        if _is_ollama_backend(self.backend):
            return self._complete_native_schema(messages, design_plan_schema())
        return self._complete(messages, json_mode=True)

    # ENG-007 (audit-team-b4): connect/first-byte budget for the native plan path, mirroring the
    # OpenAI client's `connect=5.0` half of the QA-004 split. urllib exposes only ONE socket
    # timeout (it covers connect AND every read), so the long `timeout_s` alone would let a
    # wedged-but-listening server hang for the full read budget (default 1200 s). We can't bound
    # the generation read itself (a legit local generation takes minutes), so instead we send a
    # cheap fail-fast HEAD/GET probe with THIS short budget before committing to the long call.
    _NATIVE_CONNECT_TIMEOUT_S = 5.0

    def _native_responsive(self, chat_url: str) -> bool:
        """ENG-007: a wedged-but-listening server passes the bare-TCP ``_server_reachable`` probe
        (the socket accepts) yet never answers HTTP — so the long generation ``urlopen`` would
        block for the full ``timeout_s``. Before the first real attempt, send a cheap GET to the
        server root with the short connect/first-byte budget; if it doesn't ANSWER within that
        budget the server is wedged and we fail fast. Any HTTP reply at all (even an error status,
        which arrives as HTTPError) proves the server is alive and responsive — return True.
        Local-only path, so the probe cost is a localhost round-trip."""
        root = urlunsplit((*urlsplit(chat_url)[:2], "", "", ""))
        budget = min(self.backend.timeout_s, self._NATIVE_CONNECT_TIMEOUT_S)
        try:
            with urllib.request.urlopen(root, timeout=budget):
                return True
        except urllib.error.HTTPError:
            return True  # the server answered (with a status) — it's alive, just not at "/"
        except (urllib.error.URLError, OSError, TimeoutError):
            return False

    def _complete_native_schema(self, messages: list[dict[str, str]], schema: dict) -> str:
        """Ollama-native ``/api/chat`` with grammar-constrained ``format`` (a JSON schema). Reuses
        the same connect-retry / fail-fast policy as :meth:`_complete` (a never-up local server
        fails fast; a mid-run drop keeps the retry budget).

        ENG-007 (audit-team-b4): the OpenAI path gets ``httpx.Timeout(timeout_s, connect=5.0)``;
        urllib offers only a single socket timeout, so this path fail-fast probes the server BEFORE
        the first attempt — a never-up local Ollama (TCP refused) errors immediately, and a
        wedged-but-listening server (TCP accepts, HTTP silent) is caught by a short-budget GET
        (:meth:`_native_responsive`) instead of hanging for the full ``timeout_s``. Only once the
        server proves responsive do we commit to the long-budget generation call."""
        chat_url = _native_chat_url(self.backend.base_url)
        body = json.dumps({
            "model": self.backend.model_name,
            "messages": messages,
            "stream": False,
            "format": schema,
            "options": {
                "temperature": self.backend.temperature,
                "num_predict": self.backend.max_tokens,
            },
        }).encode()
        # Fail fast BEFORE the long-budget call: a cheap short-budget GET catches both a never-up
        # server (TCP refused -> URLError) and a wedged-but-listening one (TCP accepts, HTTP silent
        # -> times out within the short budget). Only a responsive server reaches the long call.
        if not self._native_responsive(chat_url):
            raise urllib.error.URLError(
                f"the local model server at {self.backend.base_url} is not responding"
            )
        last_err: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                req = urllib.request.Request(
                    chat_url, data=body, headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=self.backend.timeout_s) as r:
                    data = json.load(r)
                return (data.get("message") or {}).get("content") or ""
            except (urllib.error.URLError, OSError, TimeoutError) as e:
                last_err = e
                if attempt == 1 and not self._server_reachable():
                    raise
                if attempt < self.max_attempts:
                    time.sleep(self.retry_wait_s)
        raise last_err if last_err is not None else RuntimeError("LLM plan call failed")

    def generate_design_plan(
        self,
        prompt: str,
        printer: Printer,
        material: Material,
        history: list[dict[str, str]] | None = None,
    ) -> DesignPlan:
        system = (
            _load_prompt("system_design_plan.md")
            .replace("{constraints}", build_constraints_block(printer, material))
            .replace("{schema}", json.dumps(design_plan_schema(), indent=2))
        )
        messages = [{"role": "system", "content": system}]
        messages.extend(history or [])
        messages.append({"role": "user", "content": prompt})
        # The network call; its connection/timeout errors propagate as-is. Local Ollama backends
        # go through the native schema-constrained path (_complete_plan); cloud uses json-mode.
        raw = self._complete_plan(messages)
        # Only the PARSE is wrapped, so a bug elsewhere in this method can't be masked as a
        # plan failure -- only genuinely unparseable model output raises PlanParseError.
        try:
            return parse_design_plan(normalize_plan_dict(json.loads(_strip_fences(raw))))
        except _PLAN_PARSE_ERRORS as e:
            raise PlanParseError(str(e), original=e) from e

    def generate_openscad(
        self,
        plan: DesignPlan,
        printer: Printer,
        material: Material,
        history: list[dict[str, str]] | None = None,
    ) -> str:
        system = (
            _load_prompt("system_openscad.md")
            .replace("{constraints}", build_constraints_block(printer, material))
            .replace("{library_manifest}", build_library_manifest())
        )
        messages = [{"role": "system", "content": system}]
        messages.extend(history or [])
        messages.append(
            {"role": "user", "content": "Design plan:\n" + plan.model_dump_json(indent=2)}
        )
        return _strip_fences(self._complete(messages, json_mode=False))

    # KC-2/KC-4 (#8/#6): generate_cadquery was removed here — the LLM-CadQuery fallback's
    # realized lift measured 0 on the shipping model, so no provider writes CadQuery anymore.
    # CadQuery geometry now comes only from the trusted template twins
    # (kimcad.cadquery_templates), which no LLM ever authors.

    def _describe_image(
        self,
        image_bytes: bytes,
        printer: Printer,
        material: Material,
        *,
        prompt_name: str,
        user_msg: str,
    ) -> str:
        """Shared LOCAL-vision read of an image into a text seed (the photo + sketch on-ramps).

        The image is sent to the local Ollama vision model via the **native** ``/api/chat`` endpoint
        (derived from the backend base_url) with ``think`` disabled. The OpenAI-compatible ``/v1``
        path leaves vision output EMPTY because gemma4:e4b's 'thinking' mode spends the whole token
        budget before producing content; the native endpoint with ``think: false`` returns the
        description. The seed is a plain description the user confirms/edits — it never becomes the
        delivered geometry. Untrusted input into the validated DesignPlan, the same trust boundary
        as typed text. ``prompt_name`` selects the system prompt (photo: rough proportions; sketch:
        read the labeled dimensions)."""
        parts = urlsplit(self.backend.base_url)
        chat_url = (
            urlunsplit((parts.scheme, parts.netloc, "/api/chat", "", ""))
            if parts.scheme and parts.netloc
            else self.backend.base_url.rstrip("/").removesuffix("/v1") + "/api/chat"
        )
        # ENG-002 (stage-9 gate): "the image never leaves the machine" is enforced HERE,
        # structurally — not only by the router convention upstream. A cloud backend's
        # base_url would fail this check before any image byte is built into a request.
        host = (urlsplit(chat_url).hostname or "").lower()
        if host not in ("localhost", "127.0.0.1", "::1") and not host.startswith("127."):
            raise RuntimeError(
                f"vision reads are local-only by design; refusing non-local host {host!r}"
            )
        system = _load_prompt(prompt_name).replace(
            "{constraints}", build_constraints_block(printer, material)
        )
        body = json.dumps({
            # Stage 9: a DEDICATED vision model — measured on the target box, the chat
            # model's (gemma4:e4b) vision is broken on this stack: with thinking enabled it
            # reports "no visible image was provided", and with think:false it deterministically
            # hallucinates the same description for ANY image. qwen2.5vl:3b read dimensioned
            # sketches 3/3 on-target (docs/benchmarks/stage-9-vision-onramps.md). Still local
            # Ollama; the image never leaves the machine.
            "model": self.backend.vision_model,
            "messages": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": user_msg,
                    "images": [base64.b64encode(image_bytes).decode()],
                },
            ],
            "stream": False,
            "options": {"temperature": 0, "num_predict": 400},
        }).encode()
        req = urllib.request.Request(
            chat_url, data=body, headers={"Content-Type": "application/json"}
        )
        # QA-902 (stage-9 gate, documented limitation): this is a synchronous read on the
        # request thread — if the CLIENT aborts (the on-ramp's Cancel), the thread only
        # notices when it writes the response, so the model finishes the abandoned read and
        # an immediate retry queues behind it (~3x latency once, measured). Propagating
        # cancellation into Ollama would need an async transport; accepted for the beta —
        # the disconnect itself is handled quietly (webapp handle_error).
        try:
            with urllib.request.urlopen(req, timeout=self.backend.timeout_s) as r:
                data = json.load(r)
        except urllib.error.HTTPError as e:
            try:
                if e.code == 404:
                    # The vision model isn't pulled — a setup state with an exact recovery
                    # command, never "your image was unreadable".
                    raise VisionModelMissing(self.backend.vision_model) from e
                # ENG-001 (stage-9 gate): any OTHER backend error (5xx OOM on the
                # constrained box, 429, runner crash) is infrastructure, not a bad image.
                raise VisionReadError(e.code) from e
            finally:
                e.close()  # ENG-005: don't leak the error response's socket/fp
        seed = _strip_fences(((data.get("message") or {}).get("content") or "").strip())
        if not seed:
            print(
                f"[kimcad] vision ({self.backend.vision_model}) returned an empty description; "
                "if this recurs on a clear image, update Ollama and re-pull the vision model.",
                file=sys.stderr,
            )
        return seed

    def describe_photo(self, image_bytes: bytes, printer: Printer, material: Material) -> str:
        """Read a PHOTO into a rough, editable text seed (Stage 8.5 Slice 7). A photo carries no
        scale, so the seed gives rough proportions the user resizes."""
        return self._describe_image(
            image_bytes, printer, material,
            prompt_name="system_photo_seed.md",
            user_msg="Describe the object in this photo as a part to 3D-print.",
        )

    def describe_sketch(self, image_bytes: bytes, printer: Printer, material: Material) -> str:
        """Read a dimensioned SKETCH into an editable text seed (Stage 9). Unlike a photo, a sketch
        often LABELS sizes, so the seed captures those exact numbers (the maker's intent) for the
        user to confirm. Same local-vision plumbing + trust boundary as the photo on-ramp."""
        return self._describe_image(
            image_bytes, printer, material,
            prompt_name="system_sketch_seed.md",
            user_msg="Read this sketch of a part to 3D-print: its shape and any labeled dimensions.",
        )


class FallbackProvider:
    """Transparent primary-to-alt LLM fallback chain.

    On a connection error, timeout, or model-not-found (404) error from the primary,
    the call is retried against the alt backend (if one is configured). If no alt is
    configured, the primary error propagates unchanged.

    Thread-local stickiness: once a thread falls back to alt (e.g. during
    ``generate_design_plan``), subsequent calls on that thread (e.g. the
    ``generate_openscad`` retries in the codegen loop) go directly to alt without
    re-trying the dead primary. This avoids eating the primary's full retry budget
    (up to max_attempts * retry_wait_s) on every call.

    With an alt configured, ``primary.max_attempts`` is reduced to 1 so a dead primary
    (Ollama down, model unloaded) hands off quickly rather than waiting e.g. 3 minutes
    for 6 * 30 s of retries to exhaust first.
    """

    def __init__(self, primary: LLMProvider, alt: LLMProvider | None = None) -> None:
        self.primary = primary
        self.alt = alt
        if alt is not None:
            # Fail fast on primary so alt kicks in without waiting out the full retry budget.
            # NOTE: this mutates the passed-in primary in place. Safe because the pipeline
            # builders construct a fresh LLMProvider per FallbackProvider; don't reuse one
            # primary across constructions or the reduction compounds.
            self.primary.max_attempts = 1
        # Thread-local stickiness: _local.on_alt is set when we switch to alt on a thread.
        # It is never reset, so a thread that fell back stays on alt for its lifetime — the
        # right behaviour for a dead primary (a fresh thread/request retries primary). On a
        # long-lived thread-pool WSGI worker, a recovered primary isn't retried until the
        # process recycles; acceptable for this power-user opt-in path.
        self._local = threading.local()

    @property
    def _on_alt(self) -> bool:
        return getattr(self._local, "on_alt", False)

    def _call(self, method_name: str, *args: Any, **kwargs: Any) -> Any:
        from openai import APIConnectionError, APITimeoutError, NotFoundError

        # Once switched on this thread, stay on alt for the rest of the request.
        if self._on_alt and self.alt is not None:
            return getattr(self.alt, method_name)(*args, **kwargs)

        try:
            return getattr(self.primary, method_name)(*args, **kwargs)
        except (APIConnectionError, APITimeoutError, NotFoundError) as exc:
            if self.alt is None:
                raise
            self._local.on_alt = True
            print(
                f"[kimcad] primary model failed ({type(exc).__name__}); "
                f"switching to alt backend '{self.alt.backend.key}'",
                file=sys.stderr,
            )
            return getattr(self.alt, method_name)(*args, **kwargs)

    def generate_design_plan(
        self,
        prompt: str,
        printer: Printer,
        material: Material,
        history: list[dict[str, str]] | None = None,
    ) -> DesignPlan:
        return self._call("generate_design_plan", prompt, printer, material, history=history)

    def generate_openscad(
        self,
        plan: DesignPlan,
        printer: Printer,
        material: Material,
        history: list[dict[str, str]] | None = None,
    ) -> str:
        return self._call("generate_openscad", plan, printer, material, history=history)

    def describe_photo(self, image_bytes: bytes, printer: Printer, material: Material) -> str:
        # ENG-004: complete the Provider contract. Delegates through the same primary→alt fallback
        # as the other calls. (The web photo path routes vision to a dedicated LOCAL provider per the
        # trust rule and doesn't reach this; this makes the contract total + type-checked regardless.)
        return self._call("describe_photo", image_bytes, printer, material)

    def describe_sketch(self, image_bytes: bytes, printer: Printer, material: Material) -> str:
        # Stage 9: complete the contract for the sketch on-ramp (same local-vision trust rule as
        # describe_photo — the web layer routes it to a dedicated LOCAL provider).
        return self._call("describe_sketch", image_bytes, printer, material)
