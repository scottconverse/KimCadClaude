"""Configuration loading.

Reads ``config/default.yaml`` and overlays an optional, gitignored
``config/local.yaml`` (per-machine overrides: binary paths, API keys via env, model
choice, and the ``paths.history`` / ``paths.designs`` store locations). Exposes typed
accessors for the parts the pipeline needs.
"""

from __future__ import annotations

import ipaddress
import os
import threading
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml

# Slice 11.4: PROJECT_ROOT is the READ root — the repo root in dev, the install dir when
# the launcher sets KIMCAD_INSTALL_ROOT (paths.py is the one switch). Everything that was
# PROJECT_ROOT-relative (config templates, tools/, the worker venv) keeps working in both
# layouts because the installer stages those trees under the install root.
from kimcad.paths import install_root as _install_root
from kimcad.paths import user_config_path as _user_config_path

PROJECT_ROOT = _install_root()
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "default.yaml"
# The user overlay is WRITABLE in both layouts (11.4-audit FINDING-003): repo-local in
# dev, %LOCALAPPDATA%\KimCad\config\local.yaml when installed.
LOCAL_CONFIG = _user_config_path()


class UnknownConfigKey(RuntimeError):
    """An unknown printer/material/backend/connector name (QA-301). A RuntimeError subclass so the
    CLI's RuntimeError handler prints it cleanly; the web layer catches it for a 400 (not a 500)."""


class UntrustedCloudHost(RuntimeError):
    """ENG-001 (audit-team-b4): a cloud LLM backend that would receive a SAVED API key resolves to a
    base_url that is not on the shipped allow-list (or isn't https). A tampered/imported
    ``config/local.yaml`` could otherwise point a saved key at an attacker host and exfiltrate it.
    A RuntimeError subclass so the CLI prints it cleanly and the web layer can return a 400."""


# ENG-001 (audit-team-b4): the explicit, documented escape hatch for advanced users who KNOWINGLY
# add a custom cloud endpoint. Fail closed by default; this env var (set to "1"/"true"/"yes") opts
# out of the cloud base_url allow-list for the whole process. Mirrors model_pull's loopback rigor:
# the allow-list is the default; the opt-out must be a deliberate, visible action.
_ALLOW_CUSTOM_CLOUD_ENV = "KIMCAD_ALLOW_CUSTOM_CLOUD_HOST"


def _custom_cloud_host_allowed() -> bool:
    return os.environ.get(_ALLOW_CUSTOM_CLOUD_ENV, "").strip().lower() in ("1", "true", "yes")


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
    # Nominal filament density (g/cm³). Used to estimate print *weight* from the slicer's
    # reported filament volume when the OrcaSlicer profile itself carries no density (several
    # shipped vendor profiles set ``filament_density = 0``, so the slicer emits volume but no
    # grams). A real spool varies by brand/colour, so a weight derived from this is an estimate.
    density: float | None = None

    def min_wall_mm(self, nozzle_diameter: float) -> float:
        """Minimum recommended wall thickness for this material on a given nozzle."""
        return self.wall_multiplier * nozzle_diameter


# ENG-1009 (stage-10 gate): THE fallback model names, defined once — the webapp's
# model-status/model-pull handlers and the backend default below all read these.
# PLANNER = qwen2.5:7b: on-machine bake-off (2026-06-15, 16-thread CPU / 780M iGPU, no CUDA) it
# planned the prompt set 4/4 where gemma4:e4b managed 1/4 and llama3.1:8b 0/4; the
# grammar-constrained plan path (llm_provider._complete_plan) keeps small-model output parseable.
DEFAULT_CHAT_MODEL = "qwen2.5:7b"
DEFAULT_VISION_MODEL = "qwen2.5vl:3b"


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
    # Stage 9: the DEDICATED local vision model for the photo/sketch on-ramps. Measured on
    # the target box (docs/benchmarks/stage-9-vision-onramps.md): gemma4:e4b's vision is
    # broken on this stack (the model itself reports no image was provided), while
    # qwen2.5vl:3b reads dimensioned sketches 3/3 on-target. Same trust boundary — the
    # read still happens on local Ollama; nothing leaves the machine.
    vision_model: str = DEFAULT_VISION_MODEL


@dataclass(frozen=True)
class ConnectorConfig:
    """A named send-to-printer target. The API key is read from ``api_key_env`` at use
    time and is never stored in config."""

    name: str
    type: str  # "loopback" | "octoprint" | "moonraker" | "prusalink" | "bambu" | …
    base_url: str | None = None
    api_key_env: str | None = None
    storage: str | None = None  # e.g. PrusaLink target storage ("usb" | "local")
    serial: str | None = None  # Bambu: the printer's serial number (LAN-mode identity)
    use_ams: bool = True  # Bambu: feed from the AMS (True) or the external spool (False)


def _deep_merge(base: dict, overlay: dict) -> dict:
    out = dict(base)
    for k, v in overlay.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


_UNSET = object()


class Config:
    def __init__(self, data: dict[str, Any]):
        self._d = data
        # Cache for the discovered CadQuery interpreter (probing spawns a subprocess, so do it
        # at most once per Config). _UNSET = not yet probed; None = probed, unavailable. The
        # lock makes the probe-once guarantee hold on the threaded web server, where one Config
        # is shared across worker threads (SLICE2-001) — without it, two cold requests could
        # each spawn the ~3-4s probe.
        self._cadquery_interpreter: Any = _UNSET
        self._cadquery_lock = threading.Lock()

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
        """Resolve a configured binary path against the project root if relative.

        ENG-002 (audit-team-b4): the result is handed to ``subprocess.run`` (OrcaSlicer/OpenSCAD),
        so assert it actually resolves to a file — a missing/typo'd path now fails with a typed,
        readable message instead of an opaque downstream OSError — and warn when a configured
        binary resolves OUTSIDE the install root (operator-controlled config only, so a warning,
        not a hard error: an absolute bundled-binary path is honored by design). Mirrors the
        existing :meth:`printproof3d_binary` existence check (the inconsistency it closes)."""
        raw = self._d["binaries"][name]
        p = Path(raw)
        p = p if p.is_absolute() else (PROJECT_ROOT / p)
        if not p.is_file():
            raise UnknownConfigKey(
                f"configured binary '{name}' resolves to {p}, which is not a file. "
                "Fix binaries." + name + " in config/local.yaml (or fetch the bundled binary)."
            )
        if not self._within_install_root(p):
            warnings.warn(
                f"configured binary '{name}' resolves to {p}, outside the install root "
                f"{PROJECT_ROOT} — make sure this is intentional.",
                stacklevel=2,
            )
        return p

    @staticmethod
    def _within_install_root(p: Path) -> bool:
        """True when the resolved path sits under PROJECT_ROOT (the install/repo root). Used to
        warn — not block — on a binary configured outside the bundle (ENG-002)."""
        try:
            p.resolve().relative_to(PROJECT_ROOT.resolve())
            return True
        except ValueError:
            return False

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

    def cadquery_interpreter(self) -> Path | None:
        """Resolve the Python interpreter the CadQuery backend runs in, or None when CadQuery
        isn't available (the backend then stays off — graceful absence, like
        :meth:`printproof3d_binary`). Driven by ``binaries.cadquery_python``:

        - ``null``/absent -> auto-discover (`py -3.13/-3.12/-3.11`, then python3.x on PATH);
        - ``false`` or ``""`` -> force OFF (return None without probing);
        - a path / argv list -> use ONLY that (authoritative; no auto-discovery fall-through).

        The discovered interpreter is cached on this Config so repeated calls (every design that
        might fall back to CadQuery) don't re-spawn the probe."""
        if self._cadquery_interpreter is not _UNSET:
            return self._cadquery_interpreter

        # Imported lazily so importing Config never drags in the runner (which is only needed
        # when the CadQuery backend is actually used).
        from kimcad.cadquery_runner import find_cadquery_interpreter

        with self._cadquery_lock:
            # Double-checked: another thread may have probed while we waited for the lock.
            if self._cadquery_interpreter is not _UNSET:
                return self._cadquery_interpreter
            raw = self._d.get("binaries", {}).get("cadquery_python")
            # `false` (sentinel) or an explicitly-cleared empty string => force OFF, no probe.
            if raw is False or raw == "":
                result: Path | None = None
            elif raw:
                result = find_cadquery_interpreter([raw], include_defaults=False)
            else:
                result = find_cadquery_interpreter()
            self._cadquery_interpreter = result
            return result

    def recheck_cadquery_interpreter(self) -> Path | None:
        """Drop the cached probe and discover again — the Settings card's explicit
        "check again" after the user installs CadQuery mid-session (KC-2, #8). The
        passive paths keep the cache; only this deliberate action pays a fresh probe."""
        with self._cadquery_lock:
            self._cadquery_interpreter = _UNSET
        return self.cadquery_interpreter()

    def cadquery_timeout_s(self) -> int:
        """Wall-clock limit for the out-of-process CadQuery worker (default 120s)."""
        return int(self._d.get("limits", {}).get("cadquery_timeout_s", 120))

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

    def settings_path(self) -> Path:
        """Where the in-app Settings store lives (Stage 8.5 Slice 6). Defaults to a per-user file
        (``~/.kimcad/settings.json``) so the user's choices (default printer/material, and later the
        LLM backend + cloud opt-in + experimental toggle) persist across sessions and never land in
        the repo; override with ``paths.settings`` in config (a relative path resolves against the
        project root). Local-first — nothing here leaves the machine."""
        raw = self._d.get("paths", {}).get("settings")
        if raw:
            p = Path(raw)
            return p if p.is_absolute() else (PROJECT_ROOT / p)
        return Path.home() / ".kimcad" / "settings.json"

    @staticmethod
    def _require(mapping: dict, key: str, kind: str) -> Any:
        """Look up ``key`` in ``mapping`` or raise a friendly :class:`UnknownConfigKey` naming the
        valid options (QA-301). It's a RuntimeError subclass, so the CLI's RuntimeError handler
        prints it cleanly — a bare KeyError would instead dump a traceback for a simple typo like an
        unknown ``--printer``/``--material``/backend — while the web layer can catch it specifically
        to return a 400 (vs a 500 for a real slice failure)."""
        try:
            return mapping[key]
        except (KeyError, TypeError):
            opts = ", ".join(sorted(mapping)) if isinstance(mapping, dict) and mapping else "(none configured)"
            raise UnknownConfigKey(f"unknown {kind} '{key}'. Available: {opts}.") from None

    # --- printers / materials ----------------------------------------------
    def printer(self, key: str | None = None) -> Printer:
        key = key or self._d["defaults"]["printer"]
        p = self._require(self._d.get("printers", {}), key, "printer")
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
        m = self._require(self._d.get("materials", {}), key, "material")
        density = m.get("density")
        return Material(
            key=key,
            name=m["name"],
            nozzle_temp=int(m["nozzle_temp"]),
            bed_temp=int(m["bed_temp"]),
            wall_multiplier=float(m["wall_multiplier"]),
            shrinkage=float(m["shrinkage"]),
            density=float(density) if density is not None else None,
        )

    # --- connectors (send-to-printer) --------------------------------------
    def connectors(self) -> list[str]:
        return list(self._d.get("connectors", {}))

    def connector_config(self, name: str) -> ConnectorConfig:
        c = self._require(self._d.get("connectors", {}), name, "connector")
        return ConnectorConfig(
            name=name,
            type=c["type"],
            base_url=c.get("base_url"),
            api_key_env=c.get("api_key_env"),
            storage=c.get("storage"),
            serial=c.get("serial"),
            use_ams=bool(c.get("use_ams", True)),
        )

    # --- llm ----------------------------------------------------------------
    def llm_backend(self, key: str | None = None) -> LLMBackend:
        key = key or self._d["llm"]["active"]
        b = self._require(self._d.get("llm", {}).get("backends", {}), key, "LLM backend")
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
            vision_model=str(b.get("vision_model", "qwen2.5vl:3b")),
        )

    @staticmethod
    def _is_local_base_url(base_url: str) -> bool:
        """ENG-001 (audit-team-b4): is this a local/loopback LLM endpoint (Ollama/LM Studio)?
        The cloud allow-list applies ONLY to non-local hosts — a loopback key is never exfiltrated
        off-box. Parsed as an IP when possible (so ``127.evil.example`` doesn't sneak through as a
        loopback), mirroring :func:`kimcad.model_pull.is_loopback_url`."""
        host = (urlsplit(base_url).hostname or "").lower()
        if not host:
            return False
        if host == "localhost":
            return True
        try:
            return ipaddress.ip_address(host).is_loopback
        except ValueError:
            return False

    @classmethod
    def shipped_cloud_hosts(cls) -> set[str]:
        """The host allow-list for cloud LLM backends, read from the SHIPPED ``config/default.yaml``
        backends (not from the merged config) so a tampered/imported ``local.yaml`` can never widen
        it — every non-local ``base_url`` host the product ships with (today: ``openrouter.ai`` and
        ``api.deepseek.com``). ENG-001: hosts are derived, not hardcoded, so adding a shipped cloud
        backend keeps the guard correct automatically."""
        try:
            shipped = yaml.safe_load(DEFAULT_CONFIG.read_text(encoding="utf-8")) or {}
        except OSError:
            shipped = {}
        hosts: set[str] = set()
        for b in (shipped.get("llm", {}).get("backends", {}) or {}).values():
            url = (b or {}).get("base_url") or ""
            if cls._is_local_base_url(url):
                continue
            host = (urlsplit(url).hostname or "").lower()
            if host:
                hosts.add(host)
        return hosts

    @classmethod
    def validate_cloud_base_url(cls, base_url: str) -> str:
        """ENG-001 (audit-team-b4): validate a CLOUD ``base_url`` that is about to receive a saved
        API key. Require ``https`` AND a host on the shipped allow-list (:meth:`shipped_cloud_hosts`).
        Fails closed by default; an advanced user who knowingly adds a custom endpoint opts out with
        ``KIMCAD_ALLOW_CUSTOM_CLOUD_HOST=1``. Local/loopback URLs are exempt (handled by the caller,
        but re-checked here for safety). Raises :class:`UntrustedCloudHost` otherwise. Returns the
        validated URL unchanged so callers can use it inline. Mirrors ``model_pull.is_loopback_url``
        in spirit: validate the host at the boundary, parse as an IP where possible."""
        if cls._is_local_base_url(base_url):
            return base_url
        if _custom_cloud_host_allowed():
            return base_url
        parts = urlsplit(base_url)
        host = (parts.hostname or "").lower()
        if parts.scheme != "https":
            raise UntrustedCloudHost(
                f"refusing to send a saved API key to a non-https cloud endpoint ({base_url!r}). "
                "Cloud LLM endpoints must use https. To knowingly allow a custom endpoint, set "
                f"{_ALLOW_CUSTOM_CLOUD_ENV}=1."
            )
        if host not in cls.shipped_cloud_hosts():
            allowed = ", ".join(sorted(cls.shipped_cloud_hosts())) or "(none)"
            raise UntrustedCloudHost(
                f"refusing to send a saved API key to an unrecognized cloud host {host!r}. "
                f"Allowed cloud hosts: {allowed}. If you knowingly added a custom endpoint, set "
                f"{_ALLOW_CUSTOM_CLOUD_ENV}=1 to opt out of this check."
            )
        return base_url

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
