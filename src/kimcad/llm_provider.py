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
import urllib.request
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlsplit, urlunsplit

import yaml
from pydantic import ValidationError

from kimcad.config import LLMBackend, Material, Printer
from kimcad.ir import DesignPlan, design_plan_schema, normalize_plan_dict, parse_design_plan

PROMPT_DIR = Path(__file__).parent / "prompts"
LIBRARY_DIR = Path(__file__).resolve().parents[2] / "library"

_FENCE = re.compile(r"^\s*```(?:\w+)?\s*|\s*```\s*$", re.MULTILINE)

# Exceptions from turning untrusted model output into a DesignPlan: bad JSON
# (JSONDecodeError < ValueError), schema-invalid JSON (pydantic ValidationError), or a
# non-dict body (TypeError/AttributeError/KeyError during normalize).
_PLAN_PARSE_ERRORS = (ValueError, TypeError, KeyError, AttributeError, ValidationError)


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

    # Stage 8: the CadQuery parallel-backend codegen. Declared on the Protocol so the contract
    # is total — every provider answers it (FallbackProvider delegates to its primary). Only
    # called when the OpenSCAD path fails and a CadQuery interpreter is available.
    def generate_cadquery(
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
        if not key:
            key = "not-needed"
        return OpenAI(base_url=backend.base_url, api_key=key, timeout=backend.timeout_s)

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
                if attempt < self.max_attempts:
                    time.sleep(self.retry_wait_s)
        raise last_err if last_err is not None else RuntimeError("LLM call failed")

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
        # _complete is the network call; its connection/timeout errors propagate as-is.
        raw = self._complete(messages, json_mode=True)
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

    def generate_cadquery(
        self,
        plan: DesignPlan,
        printer: Printer,
        material: Material,
        history: list[dict[str, str]] | None = None,
    ) -> str:
        """Generate a CadQuery (Python) script for the plan — KimCad's parallel geometry
        backend (Stage 8). Same shape as :meth:`generate_openscad`: a system prompt with the
        printer/material constraints, the plan as the user turn, fences stripped. The script
        is untrusted and is statically sanitized + run in the out-of-process worker's sandbox
        before any geometry is produced (see :mod:`kimcad.cadquery_runner`)."""
        system = _load_prompt("system_cadquery.md").replace(
            "{constraints}", build_constraints_block(printer, material)
        )
        messages = [{"role": "system", "content": system}]
        messages.extend(history or [])
        messages.append(
            {"role": "user", "content": "Design plan:\n" + plan.model_dump_json(indent=2)}
        )
        return _strip_fences(self._complete(messages, json_mode=False))

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
        system = _load_prompt(prompt_name).replace(
            "{constraints}", build_constraints_block(printer, material)
        )
        body = json.dumps({
            "model": self.backend.model_name,
            "messages": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": user_msg,
                    "images": [base64.b64encode(image_bytes).decode()],
                },
            ],
            "stream": False,
            # ``think: false`` is what keeps gemma4:e4b's thinking mode from spending the whole
            # budget on an empty reply. NOTE: older Ollama builds that predate the ``think`` field
            # silently ignore it, so vision can come back empty on a stale Ollama — which then looks
            # identical to an unreadable image. We log a one-line hint below so the cause is
            # debuggable; the user still gets the graceful "couldn't read that image" 422.
            "think": False,
            "options": {"temperature": 0, "num_predict": 400},
        }).encode()
        req = urllib.request.Request(
            chat_url, data=body, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=self.backend.timeout_s) as r:
            data = json.load(r)
        seed = _strip_fences(((data.get("message") or {}).get("content") or "").strip())
        if not seed:
            print(
                "[kimcad] vision returned an empty description; if this recurs on a clear image, "
                "update Ollama (older builds ignore think:false and gemma4 vision returns empty).",
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

    def generate_cadquery(
        self,
        plan: DesignPlan,
        printer: Printer,
        material: Material,
        history: list[dict[str, str]] | None = None,
    ) -> str:
        return self._call("generate_cadquery", plan, printer, material, history=history)

    def describe_photo(self, image_bytes: bytes, printer: Printer, material: Material) -> str:
        # ENG-004: complete the Provider contract. Delegates through the same primary→alt fallback
        # as the other calls. (The web photo path routes vision to a dedicated LOCAL provider per the
        # trust rule and doesn't reach this; this makes the contract total + type-checked regardless.)
        return self._call("describe_photo", image_bytes, printer, material)

    def describe_sketch(self, image_bytes: bytes, printer: Printer, material: Material) -> str:
        # Stage 9: complete the contract for the sketch on-ramp (same local-vision trust rule as
        # describe_photo — the web layer routes it to a dedicated LOCAL provider).
        return self._call("describe_sketch", image_bytes, printer, material)
