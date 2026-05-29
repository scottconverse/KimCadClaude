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

import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from kimcad.config import PROJECT_ROOT

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
    """The binary exited non-zero."""

    def __init__(self, returncode: int, stderr: str):
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(f"openscad exited {returncode}: {stderr.strip()[:500]}")


class OversizeOutput(RenderError):
    """The rendered mesh exceeded the configured size guard."""


@dataclass
class SanitizeResult:
    code: str
    removed: list[str] = field(default_factory=list)
    blocked: list[str] = field(default_factory=list)

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


def sanitize_scad(code: str) -> SanitizeResult:
    """Strip file-I/O statements and flag blocking ops, line by line.

    Returns the cleaned source plus a record of what was removed and any blocking
    violations. If ``blocked`` is non-empty the caller must not render.
    """
    out_lines: list[str] = []
    removed: list[str] = []
    blocked: list[str] = []

    for n, line in enumerate(code.splitlines(), start=1):
        if _MINKOWSKI_RE.search(line):
            blocked.append(f"line {n}: minkowski() is banned (CPU/RAM risk at high $fn)")
            out_lines.append(line)
            continue

        m = _USE_INCLUDE_RE.search(line)
        if m and not _approved_library_path(m.group(2)):
            removed.append(f"line {n}: {m.group(1)} <{m.group(2)}> outside approved library")
            out_lines.append(f"// [kimcad] removed file reference: {line.strip()}")
            continue

        if _IMPORT_RE.search(line):
            removed.append(f"line {n}: import/surface file I/O")
            out_lines.append(f"// [kimcad] removed file I/O: {line.strip()}")
            continue

        out_lines.append(line)

    return SanitizeResult(code="\n".join(out_lines), removed=removed, blocked=blocked)


def _run(cmd: list[str], *, cwd: Path, timeout_s: int) -> subprocess.CompletedProcess[str]:
    env_path = str(PROJECT_ROOT)
    import os

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
    or :class:`OversizeOutput`. On success returns a :class:`RenderResult` pointing
    at the written mesh.
    """
    sanitized = sanitize_scad(code)
    if not sanitized.safe:
        raise BlockedCodeError(sanitized.blocked)

    # Resolve to absolute: the binary runs with cwd=out_dir (sandbox isolation), so
    # a relative out_dir would make the -o/scad paths resolve under themselves.
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    scad_path = out_dir / f"{basename}.scad"
    scad_path.write_text(sanitized.code, encoding="utf-8")

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
