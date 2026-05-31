"""Configuration loading.

Reads ``config/default.yaml`` and overlays an optional, gitignored
``config/local.yaml`` (per-machine overrides: binary paths, API keys via env, model
choice). Exposes typed accessors for the parts the pipeline needs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "default.yaml"
LOCAL_CONFIG = PROJECT_ROOT / "config" / "local.yaml"


@dataclass(frozen=True)
class Printer:
    key: str
    name: str
    build_volume: tuple[float, float, float]
    nozzle_diameter: float
    orca_machine_profile: str | None = None
    # OrcaSlicer process (print-settings) profile name, and a material-key -> filament
    # profile name map. Names resolve to the shipped profile JSON files at slice time.
    orca_process_profile: str | None = None
    orca_filament_profiles: dict[str, str] = field(default_factory=dict)
    reference_hardware: bool = False


@dataclass(frozen=True)
class Material:
    key: str
    name: str
    nozzle_temp: int
    bed_temp: int
    wall_multiplier: float
    shrinkage: float

    def min_wall_mm(self, nozzle_diameter: float) -> float:
        """Minimum recommended wall thickness for this material on a given nozzle."""
        return self.wall_multiplier * nozzle_diameter


@dataclass(frozen=True)
class LLMBackend:
    key: str
    provider: str
    base_url: str
    model_name: str
    api_key_env: str | None
    temperature: float
    max_tokens: int
    supports_structured_output: bool
    # Per-request timeout. A local CPU model can take many minutes for one generation,
    # well past the OpenAI client's 10-minute default, so this defaults generously.
    timeout_s: float = 1200.0


def _deep_merge(base: dict, overlay: dict) -> dict:
    out = dict(base)
    for k, v in overlay.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


class Config:
    def __init__(self, data: dict[str, Any]):
        self._d = data

    @classmethod
    def load(cls, default: Path = DEFAULT_CONFIG, local: Path = LOCAL_CONFIG) -> Config:
        data = yaml.safe_load(default.read_text(encoding="utf-8")) or {}
        if local and local.exists():
            overlay = yaml.safe_load(local.read_text(encoding="utf-8")) or {}
            data = _deep_merge(data, overlay)
        return cls(data)

    @property
    def raw(self) -> dict[str, Any]:
        return self._d

    # --- binaries -----------------------------------------------------------
    def binary_path(self, name: str) -> Path:
        """Resolve a configured binary path against the project root if relative."""
        raw = self._d["binaries"][name]
        p = Path(raw)
        return p if p.is_absolute() else (PROJECT_ROOT / p)

    def orca_profiles_root(self) -> Path:
        """The shipped OrcaSlicer profile tree (``resources/profiles``) next to the
        bundled binary. Profile names in ``printers`` resolve to JSON files here."""
        return self.binary_path("orcaslicer").parent / "resources" / "profiles"

    # --- printers / materials ----------------------------------------------
    def printer(self, key: str | None = None) -> Printer:
        key = key or self._d["defaults"]["printer"]
        p = self._d["printers"][key]
        bv = p["build_volume"]
        return Printer(
            key=key,
            name=p["name"],
            build_volume=(float(bv[0]), float(bv[1]), float(bv[2])),
            nozzle_diameter=float(p["nozzle_diameter"]),
            orca_machine_profile=p.get("orca_machine_profile"),
            orca_process_profile=p.get("orca_process_profile"),
            orca_filament_profiles=dict(p.get("orca_filament_profiles", {})),
            reference_hardware=bool(p.get("reference_hardware", False)),
        )

    def material(self, key: str | None = None) -> Material:
        key = key or self._d["defaults"]["material"]
        m = self._d["materials"][key]
        return Material(
            key=key,
            name=m["name"],
            nozzle_temp=int(m["nozzle_temp"]),
            bed_temp=int(m["bed_temp"]),
            wall_multiplier=float(m["wall_multiplier"]),
            shrinkage=float(m["shrinkage"]),
        )

    # --- llm ----------------------------------------------------------------
    def llm_backend(self, key: str | None = None) -> LLMBackend:
        key = key or self._d["llm"]["active"]
        b = self._d["llm"]["backends"][key]
        return LLMBackend(
            key=key,
            provider=b["provider"],
            base_url=b["base_url"],
            model_name=b["model_name"],
            api_key_env=b.get("api_key_env"),
            temperature=float(b.get("temperature", 0.2)),
            max_tokens=int(b.get("max_tokens", 8192)),
            supports_structured_output=bool(b.get("supports_structured_output", False)),
            timeout_s=float(b.get("timeout_s", 1200.0)),
        )

    # --- limits / misc ------------------------------------------------------
    def limit(self, name: str) -> int:
        return int(self._d["limits"][name])

    def default_output_format(self) -> str:
        return str(self._d["defaults"].get("output_format", "3mf"))
