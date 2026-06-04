"""Hardware- and availability-aware LLM model advisor (Stage 6).

The model KimCad runs is **choosable, never hardwired** -- `config/default.yaml` defines
named backends, `config/local.yaml` overrides per machine, and `--backend` overrides per
run (see `kimcad.config`). This module adds the missing half: it *examines the machine*
(RAM, and a discrete GPU's VRAM if present) and *what's installed* (the models Ollama has
pulled) and **recommends** the best model that actually fits -- or, if the box could run
something better, suggests pulling it. It only ever advises; it never rewrites config.

Everything is best-effort and side-effect-free to probe: a missing `nvidia-smi`, an Ollama
that isn't running, or an unreadable `/proc/meminfo` degrade to "unknown", never an
exception. The decision function :func:`recommend` is pure (hardware + installed list +
catalog in, a recommendation out), so it's unit-tested without touching the real machine.

The catalog's RAM floors are **conservative heuristics** (roughly the q4-quantized weight
size plus headroom), not vendor specs -- they're tunable and exist to keep the advisor from
recommending a model that won't load. The model *origins* (who trained it) are factual and
matter for Scott's "keep a non-China alternative" requirement.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit, urlunsplit


@dataclass(frozen=True)
class HardwareProfile:
    """What the local machine can bring to on-device inference. Any field may be None when
    it couldn't be probed."""

    os_label: str
    cpu_count: int | None
    ram_gb: float | None
    gpu_name: str | None = None
    vram_gb: float | None = None

    @property
    def has_discrete_gpu(self) -> bool:
        return self.gpu_name is not None and (self.vram_gb or 0) > 0

    def summary(self) -> str:
        ram = f"{self.ram_gb:.0f} GB RAM" if self.ram_gb else "RAM unknown"
        cpu = f"{self.cpu_count}-core CPU" if self.cpu_count else "CPU unknown"
        gpu = (
            f"{self.gpu_name} ({self.vram_gb:.0f} GB VRAM)"
            if self.has_discrete_gpu
            else "no discrete GPU (CPU/iGPU inference)"
        )
        # ASCII separators only -- this string is printed to the (cp1252) Windows console.
        return f"{self.os_label} | {cpu} | {ram} | {gpu}"


@dataclass(frozen=True)
class InstalledModel:
    """A model Ollama reports as pulled (from `/api/tags`)."""

    name: str
    size_gb: float | None = None


@dataclass(frozen=True)
class ModelSpec:
    """A choosable model in the advisor's catalog. ``min_ram_gb`` is the conservative floor
    for CPU/iGPU inference; ``tier`` is a coarse quality rank (higher = better) used only to
    order candidates. ``origin`` is the training org; ``non_china`` flags whether it satisfies
    the 'keep a non-China alternative' requirement."""

    name: str  # the backend/Ollama tag, e.g. "qwen2.5-coder:1.5b"
    label: str
    params_b: float  # effective billions of parameters
    min_ram_gb: float
    tier: int
    origin: str
    non_china: bool
    location: str = "local"  # "local" | "cloud"
    notes: str = ""

    def fits(self, hw: HardwareProfile) -> bool:
        """Whether this model can plausibly load on the probed hardware. Cloud models always
        'fit' (no local resource cost). For local models, require enough RAM; if a discrete
        GPU is present its VRAM only helps, so RAM remains the conservative gate."""
        if self.location == "cloud":
            return True
        if hw.ram_gb is None:  # unknown RAM -- don't claim a fit we can't justify
            return False
        return hw.ram_gb >= self.min_ram_gb


# The choosable catalog. Local-first; cloud entries are opt-in alternatives (need a key).
# RAM floors are conservative heuristics (see module docstring). Tiers are relative.
MODEL_CATALOG: tuple[ModelSpec, ...] = (
    ModelSpec("qwen2.5-coder:1.5b", "Qwen2.5-Coder 1.5B", 1.5, min_ram_gb=6, tier=2,
              origin="Alibaba", non_china=False,
              notes="Small, fast, code-tuned -- the Stage 6 candidate default."),
    ModelSpec("qwen2.5-coder:3b", "Qwen2.5-Coder 3B", 3.0, min_ram_gb=10, tier=3,
              origin="Alibaba", non_china=False,
              notes="More capable than 1.5B; needs a bit more headroom."),
    ModelSpec("qwen2.5-coder:7b", "Qwen2.5-Coder 7B", 7.0, min_ram_gb=18, tier=5,
              origin="Alibaba", non_china=False,
              notes="Strong code model for a roomy box."),
    ModelSpec("gemma4:e4b", "Gemma E4B", 4.0, min_ram_gb=8, tier=3,
              origin="Google", non_china=True,
              notes="The current default; the non-China local alternative + vision-capable."),
    ModelSpec("llama3.1:8b", "Llama 3.1 8B", 8.0, min_ram_gb=18, tier=4,
              origin="Meta", non_china=True,
              notes="Non-China general model for a roomy box."),
    ModelSpec("cloud_deepseek", "DeepSeek (cloud)", 0.0, min_ram_gb=0, tier=6,
              origin="DeepSeek", non_china=False, location="cloud",
              notes="Opt-in cloud fallback -- needs DEEPSEEK_API_KEY; not local-first."),
)


@dataclass(frozen=True)
class Recommendation:
    """The advisor's verdict. ``primary`` is the model to use now; ``installed`` says whether
    it's already pulled (vs. needs `ollama pull`). ``non_china_alternative`` surfaces the best
    non-China local option (Scott's standing requirement). ``upgrade`` names a better model the
    hardware could run but isn't installed, if any."""

    primary: ModelSpec | None
    installed: bool
    reason: str
    non_china_alternative: ModelSpec | None = None
    non_china_installed: bool = False  # whether the non-China alternative is already pulled
    upgrade: ModelSpec | None = None
    alternatives: tuple[ModelSpec, ...] = field(default_factory=tuple)


# --- probing (best-effort, never raises) -----------------------------------------


def _total_ram_gb() -> float | None:
    system = platform.system()
    try:
        if system == "Windows":
            import ctypes

            class _MemStatusEx(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = _MemStatusEx()
            stat.dwLength = ctypes.sizeof(stat)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                return stat.ullTotalPhys / 1e9
            return None
        if system == "Linux":
            with open("/proc/meminfo", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        return int(line.split()[1]) * 1024 / 1e9  # kB -> bytes -> GB
            return None
        if system == "Darwin":
            out = subprocess.run(
                ["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=5
            )
            return int(out.stdout.strip()) / 1e9 if out.returncode == 0 else None
    except Exception:
        return None
    return None


def _probe_nvidia_gpu() -> tuple[str | None, float | None]:
    """Return (gpu_name, vram_gb) for the first NVIDIA GPU, or (None, None). The 780M-iGPU
    target has no discrete GPU, so this correctly returns (None, None) there."""
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, OSError, subprocess.SubprocessError):
        return None, None
    if out.returncode != 0 or not out.stdout.strip():
        return None, None
    first = out.stdout.strip().splitlines()[0]
    parts = [p.strip() for p in first.split(",")]
    if len(parts) < 2:
        return None, None
    name = parts[0]
    try:
        vram_gb = float(parts[1]) / 1024.0  # MiB -> GB (approx; advisory only)
    except ValueError:
        return name or None, None
    return name or None, vram_gb


def probe_hardware() -> HardwareProfile:
    """Probe the local machine. Best-effort: every field degrades to None on failure."""
    gpu_name, vram_gb = _probe_nvidia_gpu()
    return HardwareProfile(
        os_label=f"{platform.system()} {platform.release()}".strip(),
        cpu_count=os.cpu_count(),
        ram_gb=_total_ram_gb(),
        gpu_name=gpu_name,
        vram_gb=vram_gb,
    )


def _ollama_tags_url(base_url: str) -> str:
    """Map an OpenAI-compatible base_url (...:11434/v1) to Ollama's native, host-rooted
    ``/api/tags`` endpoint -- preserving scheme + host[:port] and discarding the whole path
    (``/v1``, or a proxied sub-path like ``/ollama/v1``), so a base_url with a path tail
    can't leak into the tags URL."""
    parts = urlsplit(base_url)
    if parts.scheme and parts.netloc:
        return urlunsplit((parts.scheme, parts.netloc, "/api/tags", "", ""))
    # No scheme/netloc (a bare host or odd input): fall back to the host-prefix split.
    host = base_url.split("/v1", 1)[0].rstrip("/")
    return f"{host}/api/tags"


def friendly_label(installed_name: str, catalog: tuple[ModelSpec, ...] = MODEL_CATALOG) -> str | None:
    """The catalog's friendly label for an installed Ollama tag, matched by family (exact, or
    the catalog name followed by a quant/variant suffix -- e.g. ``gemma4:e4b-it-q4_K_M`` ->
    ``"Gemma E4B"``). Returns None when no catalog entry matches. Prefers the longest (most
    specific) matching catalog name so a sibling tag can't shadow the right one."""
    best: ModelSpec | None = None
    for spec in catalog:
        if installed_name == spec.name or installed_name.startswith(spec.name + "-"):
            if best is None or len(spec.name) > len(best.name):
                best = spec
    return best.label if best is not None else None


def _parse_tags(data: Any) -> list[InstalledModel]:
    out: list[InstalledModel] = []
    for m in data.get("models", []) if isinstance(data, dict) else []:
        name = m.get("name") or m.get("model")
        if not name:
            continue
        size = m.get("size")
        out.append(InstalledModel(name=name, size_gb=size / 1e9 if isinstance(size, (int, float)) else None))
    return out


def probe_installed_models(base_url: str, *, timeout: float = 3.0) -> list[InstalledModel]:
    """Ask Ollama (at ``base_url``) which models are pulled, via `/api/tags`. Returns [] if
    Ollama isn't running or the response is unreadable -- never raises."""
    try:
        with urllib.request.urlopen(_ollama_tags_url(base_url), timeout=timeout) as r:
            data = json.load(r)
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return []
    return _parse_tags(data)


def probe_ollama(base_url: str, *, timeout: float = 3.0) -> tuple[bool, list[InstalledModel]]:
    """``(reachable, installed-models)``. Unlike :func:`probe_installed_models` (which returns []
    for both a down server AND an up-but-empty one), this distinguishes the two: ``reachable`` is
    True whenever Ollama answered `/api/tags`, even with no models. Used by the Settings model-status
    so the UI can tell "not running" (start Ollama) apart from "running, model not pulled" (get the
    model). Never raises."""
    try:
        with urllib.request.urlopen(_ollama_tags_url(base_url), timeout=timeout) as r:
            data = json.load(r)
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return False, []
    return True, _parse_tags(data)


# --- the pure decision (unit-tested without the machine) -------------------------


def _installed_match(spec: ModelSpec, installed: list[InstalledModel]) -> bool:
    """Whether a catalog model is actually pulled. A SPECIFIC tag must match EXACTLY -- a
    `qwen2.5-coder:1.5b` install must NOT satisfy a `qwen2.5-coder:7b` spec (a different model)
    nor a `...:1.5b-instruct` variant. Only the implicit `:latest` default is tolerated: a bare
    `gemma4` install satisfies a tagless `gemma4` spec, and a spec pinned to `:latest` matches
    the bare name."""
    names = {m.name for m in installed}
    if spec.name in names:
        return True
    if ":" in spec.name:
        base, tag = spec.name.split(":", 1)
        return tag == "latest" and base in names  # specific tags must match exactly
    # A tagless spec matches the bare name or any single tag of it.
    return any(n == spec.name or n.startswith(spec.name + ":") for n in names)


def _non_china_escape(
    primary: ModelSpec | None, fitting_local: list[ModelSpec], installed: list[InstalledModel]
) -> tuple[ModelSpec | None, bool]:
    """A non-China local model to fall back to WHEN THE PRIMARY IS CHINA-ORIGIN (Scott's
    'keep a non-China alternative' requirement). Returns (None, False) when the primary is
    already non-China (no escape needed) or none fits. Prefers a non-China model that's already
    installed (usable now) over a better one that would need pulling. Returns (spec, is_installed)."""
    if primary is None or primary.non_china:
        return None, False
    candidates = [s for s in fitting_local if s.non_china and s.name != primary.name]
    installed_nc = [s for s in candidates if _installed_match(s, installed)]
    best = max(installed_nc or candidates, key=lambda s: s.tier, default=None)
    return best, (best is not None and _installed_match(best, installed))


def recommend(
    hardware: HardwareProfile,
    installed: list[InstalledModel],
    catalog: tuple[ModelSpec, ...] = MODEL_CATALOG,
) -> Recommendation:
    """Pick the model to use now: the highest-tier LOCAL model that both fits the hardware
    and is already installed. If the box could run a higher-tier local model that isn't
    installed, name it as an ``upgrade`` (pull suggestion). When the pick is China-origin,
    surface a non-China escape (preferring an installed one). Cloud models are alternatives
    only (opt-in, need a key), never the primary when any local model fits -- KimCad is
    local-first.

    Pure: same inputs -> same output, no I/O."""
    local = [s for s in catalog if s.location == "local"]
    fitting_local = [s for s in local if s.fits(hardware)]
    fitting_installed = sorted(
        (s for s in fitting_local if _installed_match(s, installed)),
        key=lambda s: s.tier,
        reverse=True,
    )
    best_fitting = max(fitting_local, key=lambda s: s.tier, default=None)

    if fitting_installed:
        primary = fitting_installed[0]
        upgrade = best_fitting if best_fitting and best_fitting.tier > primary.tier else None
        reason = (
            f"{primary.label} is the strongest model you have installed that fits this machine"
            f" ({hardware.summary()})."
        )
        if upgrade:
            reason += (
                f" Your hardware could also run {upgrade.label} -- a larger model that may"
                " plan better; run `kimcad bakeoff` to confirm before switching (the tiers"
                " here are heuristics, not measured)."
            )
        nc, nc_installed = _non_china_escape(primary, fitting_local, installed)
        return Recommendation(
            primary=primary,
            installed=True,
            reason=reason,
            non_china_alternative=nc,
            non_china_installed=nc_installed,
            upgrade=upgrade,
            alternatives=tuple(fitting_installed[1:]),
        )

    # Nothing installed fits (or nothing installed at all): recommend the best one to pull.
    if best_fitting is not None:
        nc, nc_installed = _non_china_escape(best_fitting, fitting_local, installed)
        reason = (
            f"No installed model fits this machine yet. {best_fitting.label} is the best fit"
            f" for it ({hardware.summary()}) -- pull it (`ollama pull {best_fitting.name}`)."
        )
        return Recommendation(
            primary=best_fitting,
            installed=False,
            reason=reason,
            non_china_alternative=nc,
            non_china_installed=nc_installed,
            alternatives=tuple(
                s for s in sorted(fitting_local, key=lambda s: s.tier, reverse=True)
                if s.name != best_fitting.name
            ),
        )

    # No local model fits (tiny box or RAM unknown): fall back to the cloud option, if any.
    cloud = max((s for s in catalog if s.location == "cloud"), key=lambda s: s.tier, default=None)
    if cloud is not None:
        why = (
            "couldn't read this machine's RAM"
            if hardware.ram_gb is None
            else f"this machine ({hardware.summary()}) is below every local model's floor"
        )
        return Recommendation(
            primary=cloud,
            installed=False,
            reason=f"No local model fits -- {why}. The opt-in cloud backend ({cloud.label},"
            f" needs a key) is the fallback.",
        )
    return Recommendation(primary=None, installed=False, reason="No model in the catalog fits this machine.")
