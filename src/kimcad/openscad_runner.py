"""OpenSCAD execution & sandboxing (spec §6.4, §6.8, §12).

Generated OpenSCAD is **untrusted**. Before it ever reaches the binary it is
sanitized: file-I/O statements (``import()``, ``surface()``, and ``use``/``include``
outside the approved ``library/`` path) are stripped, and ``minkowski()`` — which
can pin a CPU for hours at high ``$fn`` — is treated as a hard block so the
orchestrator re-prompts rather than rendering it.

The binary is then invoked in an isolated temp directory with a timeout and an
output-size guard:

    openscad -o part.3mf part.scad

3MF is the default (it carries units, dodging the classic STL scale bug). If the
shipped binary lacks ``lib3mf`` the render is retried as binary STL and the
fallback is recorded (§6.8).

The sanitizer and result handling are pure functions so they are testable without
the binary; only :func:`render_scad` shells out.
"""

from __future__ import annotations

import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from kimcad.config import PROJECT_ROOT
from kimcad.errors import ToolMissingError

LIBRARY_DIR = PROJECT_ROOT / "library"

# Only `use`/`include` pointing inside this relative path survive sanitization.
_APPROVED_PREFIX = "library/"

_IMPORT_RE = re.compile(r"\b(?:import|surface)\s*\(")
_MINKOWSKI_RE = re.compile(r"\bminkowski\s*\(")
_USE_INCLUDE_RE = re.compile(r"\b(use|include)\s*<([^>]*)>")

# stderr fingerprints that mean "this binary can't write 3MF", not "bad model".
_NO_3MF_RE = re.compile(r"lib3mf|3mf|Unknown file|unsupported file format", re.IGNORECASE)


class RenderError(Exception):
    """Base class for all render failures."""


class BlockedCodeError(RenderError):
    """The generated code contains an op we refuse to run (e.g. minkowski)."""

    def __init__(self, violations: list[str]):
        self.violations = violations
        super().__init__("; ".join(violations))


class RenderTimeout(RenderError):
    """The binary exceeded the allotted wall-clock time."""


class RenderFailed(RenderError):
    """The geometry backend failed to produce a mesh (non-zero exit, or — for the CadQuery
    worker — a clean error report). ``engine`` names the backend so the message is accurate
    regardless of which one produced the part."""

    def __init__(self, returncode: int, stderr: str, *, engine: str = "openscad"):
        self.returncode = returncode
        self.stderr = stderr
        self.engine = engine
        detail = stderr.strip()[:500]
        msg = (
            f"openscad exited {returncode}: {detail}"
            if engine == "openscad"
            else f"{engine} render failed: {detail}"
        )
        super().__init__(msg)


class OversizeOutput(RenderError):
    """The rendered mesh exceeded the configured size guard."""


@dataclass
class SanitizeResult:
    code: str
    removed: list[str] = field(default_factory=list)
    blocked: list[str] = field(default_factory=list)
    added: list[str] = field(default_factory=list)

    @property
    def safe(self) -> bool:
        return not self.blocked


@dataclass
class RenderResult:
    output_path: Path
    output_format: str
    stdout: str
    stderr: str
    duration_s: float
    sanitize: SanitizeResult
    fell_back_to_stl: bool = False
    # Which geometry backend produced this mesh ("openscad" | "cadquery"). Lets the report
    # and the live-slider/export surfaces know whether an editable STEP is available.
    backend: str = "openscad"
    # The editable-CAD export (STEP), produced only by the CadQuery backend (Stage 8);
    # None for OpenSCAD, which cannot emit a BREP/STEP.
    step_path: Path | None = None


def _approved_library_path(path: str) -> bool:
    """True only for a clean relative path inside ``library/`` (no traversal)."""
    p = path.strip()
    if not p.startswith(_APPROVED_PREFIX):
        return False
    if ".." in p or "\\" in p or p.startswith("/"):
        return False
    # reject a Windows drive-absolute path like C:library/...
    if re.match(r"^[A-Za-z]:", p):
        return False
    return True


def _library_module_map(library_dir: Path = LIBRARY_DIR) -> dict[str, str]:
    """Map each library module name to its ``.scad`` file, parsed from the manifest.

    Derived from the same manifest the codegen prompt advertises, so the runner and
    the prompt can never drift on which modules exist.
    """
    try:
        data = yaml.safe_load((library_dir / "manifest.yaml").read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    mapping: dict[str, str] = {}
    for mod in data.get("modules", []):
        file = mod.get("file")
        if not file:
            continue
        for sig in mod.get("signatures", []):
            m = re.match(r"\s*(\w+)\s*\(", sig)
            if m:
                mapping[m.group(1)] = file
    return mapping


def inject_library_uses(
    code: str, module_map: dict[str, str] | None = None
) -> tuple[str, list[str]]:
    """Prepend the ``use <library/FILE.scad>;`` for any library module the code calls
    but forgot to include.

    The model regularly calls a real helper (``rounded_box``, ``l_bracket``) without
    its ``use`` line; OpenSCAD then treats it as an unknown module and silently renders
    nothing — a failure that surfaces as a confusing empty/garbage mesh rather than a
    clear error. Fixing it deterministically here is far more reliable than asking a
    flaky model to remember boilerplate. Modules the code defines itself are skipped so
    a user-supplied definition is never shadowed by a library import.
    """
    module_map = module_map if module_map is not None else _library_module_map()
    if not module_map:
        return code, []
    already_used = {
        m.group(2).rsplit("/", 1)[-1]
        for m in _USE_INCLUDE_RE.finditer(code)
        if m.group(2).startswith(_APPROVED_PREFIX)
    }
    defined_locally = set(re.findall(r"\bmodule\s+(\w+)", code))
    needed: list[str] = []
    for name, file in module_map.items():
        if name in defined_locally or file in already_used or file in needed:
            continue
        if re.search(rf"\b{re.escape(name)}\s*\(", code):
            needed.append(file)
    if not needed:
        return code, []
    added = [f"use <library/{f}>;" for f in needed]
    return "\n".join(added) + "\n" + code, added


def ensure_terminated(code: str) -> tuple[str, bool]:
    """Append a missing ``;`` when the code ends with an unterminated call.

    A small model frequently emits a valid trailing module call like ``wall_hook(...)``
    but drops the statement terminator, which OpenSCAD rejects as a parser error — and
    the render-retry rarely recovers from a single missing ``;``. Appending it is safe:
    code whose last statement ends in ``)`` without a terminator is always a syntax
    error, so adding ``;`` can only fix it. A trailing line comment is preserved.
    """
    body = re.sub(r"/\*.*?\*/", "", code, flags=re.DOTALL)
    if not re.sub(r"//[^\n]*", "", body).rstrip().endswith(")"):
        return code, False
    lines = code.rstrip("\n").split("\n")
    for i in range(len(lines) - 1, -1, -1):
        cidx = lines[i].find("//")
        codepart = (lines[i] if cidx < 0 else lines[i][:cidx]).rstrip()
        if not codepart:
            continue  # comment-only / blank line; keep scanning upward
        if codepart.endswith(")"):
            comment = "" if cidx < 0 else "  " + lines[i][cidx:]
            lines[i] = codepart + ";" + comment
            return "\n".join(lines) + "\n", True
        return code, False
    return code, False


def _strip_comments(code: str) -> str:
    """Blank out comments so a construct can't hide in one (and can't be evaluated)."""
    code = re.sub(r"/\*.*?\*/", " ", code, flags=re.DOTALL)
    code = re.sub(r"//[^\n]*", " ", code)
    return code


def sanitize_scad(code: str) -> SanitizeResult:
    """Block code that reaches outside the approved library or risks a CPU/RAM DoS.

    Detection runs on the **full source** (with comments blanked), not line by line, so a
    construct split across newlines — ``minkowski\\n(...)``, ``import\\n("…")``,
    ``use\\n</etc/x>`` — cannot slip past (the regexes' ``\\s*`` spans newlines once it
    isn't confined to a single line). Anything dangerous is **blocked** — the caller
    re-prompts — rather than stripped, so valid geometry is never silently destroyed and
    there is no partial-strip bypass. Only ``use``/``include`` inside ``library/`` survive.
    """
    scan = _strip_comments(code)
    blocked: list[str] = []

    if _MINKOWSKI_RE.search(scan):
        blocked.append("minkowski() is banned (CPU/RAM risk at high $fn)")
    if _IMPORT_RE.search(scan):
        blocked.append("import()/surface() file I/O is not allowed")
    for m in _USE_INCLUDE_RE.finditer(scan):
        if not _approved_library_path(m.group(2)):
            blocked.append(
                f"{m.group(1)} <{m.group(2)}> reaches outside the approved library/ path"
            )

    return SanitizeResult(code=code, removed=[], blocked=blocked)


def _run(cmd: list[str], *, cwd: Path, timeout_s: int) -> subprocess.CompletedProcess[str]:
    env_path = str(PROJECT_ROOT)
    env = dict(os.environ)
    # Let `use <library/...>` resolve while the working dir stays the isolated temp.
    existing = env.get("OPENSCADPATH")
    env["OPENSCADPATH"] = env_path if not existing else f"{env_path}{os.pathsep}{existing}"
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout_s,
    )


def render_scad(
    code: str,
    *,
    binary: Path,
    out_dir: Path,
    basename: str = "part",
    output_format: str = "3mf",
    timeout_s: int = 30,
    max_output_bytes: int = 209_715_200,
) -> RenderResult:
    """Sanitize and render OpenSCAD source to a mesh file in ``out_dir``.

    Raises :class:`BlockedCodeError`, :class:`RenderTimeout`, :class:`RenderFailed`,
    :class:`~kimcad.errors.ToolMissingError` (binary not on disk — checked before the
    subprocess spawn so a skipped fetch_tools step never surfaces as a raw
    FileNotFoundError, QA-003), or :class:`OversizeOutput`. On success returns a
    :class:`RenderResult` pointing at the written mesh. Sanitization runs FIRST:
    blocked code is blocked regardless of whether the tool is installed.
    """
    injected, added = inject_library_uses(code)
    injected, terminated = ensure_terminated(injected)
    sanitized = sanitize_scad(injected)
    sanitized.added = added + (["appended ';' to terminate a trailing call"] if terminated else [])
    if not sanitized.safe:
        raise BlockedCodeError(sanitized.blocked)

    # Resolve to absolute: the binary runs with cwd=out_dir (sandbox isolation), so
    # a relative out_dir would make the -o/scad paths resolve under themselves.
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    scad_path = out_dir / f"{basename}.scad"
    scad_path.write_text(sanitized.code, encoding="utf-8")

    if not Path(binary).is_file():
        raise ToolMissingError("OpenSCAD", Path(binary))
    fmt = output_format.lower()
    started = time.monotonic()
    proc, fmt, fell_back = _render_once(binary, scad_path, out_dir, basename, fmt, timeout_s)
    duration = time.monotonic() - started

    if proc.returncode != 0:
        raise RenderFailed(proc.returncode, proc.stderr)

    output_path = out_dir / f"{basename}.{fmt}"
    if not output_path.exists():
        raise RenderFailed(proc.returncode, f"expected {output_path.name} was not written")

    size = output_path.stat().st_size
    if size > max_output_bytes:
        output_path.unlink(missing_ok=True)
        raise OversizeOutput(f"render produced {size} bytes (> {max_output_bytes} guard)")

    return RenderResult(
        output_path=output_path,
        output_format=fmt,
        stdout=proc.stdout,
        stderr=proc.stderr,
        duration_s=duration,
        sanitize=sanitized,
        fell_back_to_stl=fell_back,
    )


def _render_once(
    binary: Path,
    scad_path: Path,
    out_dir: Path,
    basename: str,
    fmt: str,
    timeout_s: int,
) -> tuple[subprocess.CompletedProcess[str], str, bool]:
    """Run the binary; if 3MF fails for a format reason, retry as STL once."""
    out_path = out_dir / f"{basename}.{fmt}"
    cmd = [str(binary), "-o", str(out_path), str(scad_path)]
    try:
        proc = _run(cmd, cwd=out_dir, timeout_s=timeout_s)
    except subprocess.TimeoutExpired as e:
        raise RenderTimeout(f"openscad exceeded {timeout_s}s") from e

    if fmt == "3mf" and proc.returncode != 0 and _NO_3MF_RE.search(proc.stderr or ""):
        stl_path = out_dir / f"{basename}.stl"
        cmd = [str(binary), "-o", str(stl_path), str(scad_path)]
        try:
            proc = _run(cmd, cwd=out_dir, timeout_s=timeout_s)
        except subprocess.TimeoutExpired as e:
            raise RenderTimeout(f"openscad exceeded {timeout_s}s (stl fallback)") from e
        return proc, "stl", True

    return proc, fmt, False
