"""LLM integration layer (spec §6.1).

One module wraps all LLM communication via the OpenAI SDK as the universal client —
DeepSeek, OpenRouter, Gemini (proxy), and local runtimes all speak the
OpenAI-compatible chat-completions format. Two jobs:

    generate_design_plan(prompt, history, ...) -> DesignPlan
    generate_openscad(plan, history, ...)      -> str (OpenSCAD source)

The long system prompt is reused across a conversation to maximize prefix-cache hits
(§7.1). The OpenAI client is injectable so the assembly logic is testable offline.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Protocol

import yaml

from kimcad.config import LLMBackend, Material, Printer
from kimcad.ir import DesignPlan, design_plan_schema, parse_design_plan

PROMPT_DIR = Path(__file__).parent / "prompts"
LIBRARY_DIR = Path(__file__).resolve().parents[2] / "library"

_FENCE = re.compile(r"^\s*```(?:\w+)?\s*|\s*```\s*$", re.MULTILINE)


class ChatClient(Protocol):
    """Minimal structural type for the bit of the OpenAI client we use."""

    @property
    def chat(self) -> Any: ...


def _load_prompt(name: str) -> str:
    return (PROMPT_DIR / name).read_text(encoding="utf-8")


def _strip_fences(text: str) -> str:
    return _FENCE.sub("", text).strip()


def build_constraints_block(printer: Printer, material: Material) -> str:
    bv = printer.build_volume
    min_wall = material.min_wall_mm(printer.nozzle_diameter)
    return (
        f"- Printer: {printer.name}\n"
        f"- Build volume (x, y, z): {bv[0]:.0f} × {bv[1]:.0f} × {bv[2]:.0f} mm "
        "(the part must fit inside this)\n"
        f"- Nozzle diameter: {printer.nozzle_diameter:.2f} mm\n"
        f"- Material: {material.name} "
        f"(nozzle {material.nozzle_temp}°C, bed {material.bed_temp}°C)\n"
        f"- Minimum wall thickness: {min_wall:.1f} mm\n"
        f"- Default hole/peg clearance: 0.2 mm "
        f"(account for ~{material.shrinkage * 100:.1f}% shrinkage)\n"
    )


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
    def __init__(self, backend: LLMBackend, client: ChatClient | None = None):
        self.backend = backend
        self.client = client if client is not None else self._build_client(backend)

    @staticmethod
    def _build_client(backend: LLMBackend) -> ChatClient:
        from openai import OpenAI

        api_key = "not-needed"
        if backend.api_key_env:
            api_key = os.environ.get(backend.api_key_env) or ""
            if not api_key:
                raise RuntimeError(
                    f"Environment variable {backend.api_key_env} is not set; "
                    f"the {backend.key} backend needs an API key."
                )
        return OpenAI(base_url=backend.base_url, api_key=api_key)

    def _complete(self, messages: list[dict[str, str]], *, json_mode: bool) -> str:
        kwargs: dict[str, Any] = {
            "model": self.backend.model_name,
            "messages": messages,
            "temperature": self.backend.temperature,
            "max_tokens": self.backend.max_tokens,
        }
        if json_mode and self.backend.supports_structured_output:
            kwargs["response_format"] = {"type": "json_object"}
        resp = self.client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""

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
        raw = self._complete(messages, json_mode=True)
        return parse_design_plan(json.loads(_strip_fences(raw)))

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
