"""Configuration loading.

Reads ``config/default.yaml`` and overlays an optional, gitignored
``config/local.yaml`` (per-machine overrides: binary paths, API keys via env, model
choice, and the ``paths.history`` / ``paths.designs`` store locations). Exposes typed
accessors for the parts the pipeline needs.
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
    # Physical envelope + nozzle. Either may be left blank (None) in config and filled
    # from a connector's reported capabilities (see kimcad.capability.reconcile).
    build_volume: tuple[float, float, float] | None
    nozzle_diameter: float | None
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


@dataclass(frozen=True)
class ConnectorConfig:
    """A named send-to-printer target. The API key is read from ``api_key_env`` at use
    time and is never stored in config."""

    name: str
    type: str  # "loopback" | "octoprint" | "moonraker" | "prusalink" | …
    base_url: str | None = None
    api_key_env: str | None = None
    storage: str | None = None  # e.g. PrusaLink target storage ("usb" | "local")


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

    def printproof3d_binary(self) -> Path | None:
        """The PrintProof3D validation-engine binary, or None when it isn't configured or
        isn't present on disk (Stage 7). Optional by design: a missing engine means Smart
        Mesh falls back to KimCad's own gate rather than failing. Resolves a relative path
        against the project root, like :meth:`binary_path`, but never raises on absence."""
        raw = self._d.get("binaries", {}).get("printproof3d")
        if not raw:
            return None
        p = Path(raw)
        p = p if p.is_absolute() else (PROJECT_ROOT / p)
        return p if p.exists() else None

    def history_path(self) -> Path:
        """Where the Smart Mesh learning store lives (Stage 7). Defaults to a per-user file
        (``~/.kimcad/history.json``) so it persists across projects and never lands in the repo;
        override with ``paths.history`` in config (a relative path resolves against the project
        root). The store is local-first and best-effort — nothing here leaves the machine."""
        raw = self._d.get("paths", {}).get("history")
        if raw:
            p = Path(raw)
            return p if p.is_absolute() else (PROJECT_ROOT / p)
        return Path.home() / ".kimcad" / "history.json"

    def designs_path(self) -> Path:
        """Where the "My Designs" store lives (Stage 8.5). Defaults to a per-user directory
        (``~/.kimcad/designs/``) so saved designs persist across sessions and never land in the
        repo; override with ``paths.designs`` in config (a relative path resolves against the
        project root). Local-first — nothing here leaves the machine."""
        raw = self._d.get("paths", {}).get("designs")
        if raw:
            p = Path(raw)
            return p if p.is_absolute() else (PROJECT_ROOT / p)
        return Path.home() / ".kimcad" / "designs"

    # --- printers / materials ----------------------------------------------
    def printer(self, key: str | None = None) -> Printer:
        key = key or self._d["defaults"]["printer"]
        p = self._d["printers"][key]
        bv = p.get("build_volume")
        # A 3-element value is the envelope; anything else (missing, empty, malformed) is
        # blank (None) — to be filled from a connector's reported capabilities.
        build_volume = (
            (float(bv[0]), float(bv[1]), float(bv[2]))
            if isinstance(bv, (list, tuple)) and len(bv) == 3
            else None
        )
        nozzle = p.get("nozzle_diameter")
        return Printer(
            key=key,
            name=p["name"],
            build_volume=build_volume,
            nozzle_diameter=float(nozzle) if nozzle is not None else None,
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

    # --- connectors (send-to-printer) --------------------------------------
    def connectors(self) -> list[str]:
        return list(self._d.get("connectors", {}))

    def connector_config(self, name: str) -> ConnectorConfig:
        c = self._d.get("connectors", {})[name]
        return ConnectorConfig(
            name=name,
            type=c["type"],
            base_url=c.get("base_url"),
            api_key_env=c.get("api_key_env"),
            storage=c.get("storage"),
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

    def llm_alt_backend(self) -> LLMBackend | None:
        """Return the configured alt/fallback LLM backend, or None if not set.

        Set ``llm.alt_backend`` in ``config/local.yaml`` to a backend key (e.g.
        ``cloud_deepseek``) to enable the tiered fallback chain; leave it null (the
        default) to keep the single-backend behaviour.
        """
        key = self._d.get("llm", {}).get("alt_backend")
        if not key:
            return None
        return self.llm_backend(key)

    # --- limits / misc ------------------------------------------------------
    def limit(self, name: str) -> int:
        return int(self._d["limits"][name])

    def default_output_format(self) -> str:
        return str(self._d["defaults"].get("output_format", "3mf"))
