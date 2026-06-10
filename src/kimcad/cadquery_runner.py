"""CadQuery backend — the in-process (Python 3.14) side that drives the out-of-process
worker (spec §6.4/§12, Stage 8).

CadQuery is the **parallel geometry backend** to OpenSCAD: the LLM can emit either, and a
prompt OpenSCAD codegen fails on may succeed under CadQuery (and vice versa), so the union
lifts the done-gate. CadQuery also exports **STEP** — editable, parametric CAD geometry
OpenSCAD cannot produce.

CadQuery's OCCT backend has no Python-3.14 wheels, so it runs in a separate <=3.13
interpreter via :mod:`kimcad.cadquery_worker`, shelled out exactly like OpenSCAD/OrcaSlicer.
This module:

1. **Statically sanitizes** the untrusted generated script (the first of two security
   layers; the worker's restricted builtins are the second). It blocks — rather than
   strips — anything dangerous, so the orchestrator re-prompts and valid geometry is never
   silently mangled.
2. Writes the script to an isolated temp dir, invokes the worker with a timeout + output
   size guard, and returns the same :class:`~kimcad.openscad_runner.RenderResult` the
   pipeline already consumes from the OpenSCAD path — so the orient/harden/gate tail is
   identical regardless of backend.

The sanitizer is a pure function (token-based, so a banned word inside a string or comment
is not a false positive) and is unit-tested without the interpreter; only
:func:`render_cadquery` shells out.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import time
from collections.abc import Sequence
from pathlib import Path

from kimcad.openscad_runner import (
    BlockedCodeError,
    OversizeOutput,
    RenderFailed,
    RenderResult,
    RenderTimeout,
    SanitizeResult,
)

# ENG-003 (stage-C): the secret-scrub now lives in kimcad.subprocess_env — ONE source of
# truth shared with the OpenSCAD runner. These aliases keep the existing tests/call sites
# (the precision tests for the scrub import _is_secret_env from here).
from kimcad.subprocess_env import is_secret_env as _is_secret_env  # noqa: F401
from kimcad.subprocess_env import scrubbed_env as _scrubbed_env


def _worker_env() -> dict[str, str]:
    """The parent environment MINUS secret-bearing variables — what the worker subprocess runs
    with (ENG-002), mirroring the OpenSCAD runner's env discipline. The worker is pure cadquery +
    stdlib and needs no credentials, so withholding the LLM/printer API keys bounds the blast
    radius if the sanitizer is ever bypassed."""
    return _scrubbed_env()

# The worker script, run by the foreign <=3.13 interpreter BY ABSOLUTE PATH (not `-m`,
# since the kimcad package isn't installed in the 3.13 environment). It's a sibling file.
WORKER_PATH = Path(__file__).with_name("cadquery_worker.py")
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Imports the generated script may make. Everything else is blocked. (The worker also
# pre-injects ``cq``/``cadquery``/``math``, so a well-formed script needs no import at all.)
_ALLOWED_IMPORT_ROOTS = frozenset({"cadquery", "math"})

# Bare names we refuse outright — code execution / introspection / file & process access.
# Most real escapes also need a dunder, which is blocked separately, but denying the names
# too gives a clean, specific re-prompt and defence in depth. Blocked as BOTH a Name (e.g.
# ``os``) AND an attribute (e.g. ``cq.exporters.os``), so the attribute-graph pivot the
# Stage-8 Slice-1 audit found is caught statically as well as by the worker's facade.
_BANNED_NAMES = frozenset({
    "eval", "exec", "compile", "open", "input", "__import__", "globals", "locals", "vars",
    "getattr", "setattr", "delattr", "breakpoint", "memoryview", "help", "exit", "quit",
    "os", "sys", "subprocess", "socket", "shutil", "pathlib", "importlib", "ctypes",
    "builtins", "threading", "multiprocessing", "signal", "tempfile", "pickle", "marshal",
    "urllib", "requests", "http", "ftplib", "platform", "pty", "code", "codeop", "glob",
})

# Dangerous attribute names, blocked only as attributes. Two groups, neither of which names
# a cadquery geometry method (so blocking them can't break valid modelling — unlike the
# cadquery submodule names ``sketch``/``assembly``…, which DO collide with real Workplane
# methods and so are left to the worker's geometry-only facade to neutralize):
#   1. OS/exec/file operations (system, popen, unlink …).
#   2. Frame/function INTROSPECTION attributes that reach a real, unrestricted ``__builtins__``
#      via ``__globals__``/frame objects (gi_frame, f_builtins, func_globals …) — the
#      Stage-8 Slice-1 RE-AUDIT (NEW-007) escape class — plus ``format``/``format_map``,
#      whose ``{0.attr}``/``{0[key]}`` fields hide an attribute/subscript pivot inside a string
#      literal that the AST walk can't see (an f-string, by contrast, exposes real AST nodes).
_BANNED_ATTRS = frozenset({
    # OS / exec / filesystem
    "system", "popen", "fork", "kill", "remove", "unlink", "rmdir", "removedirs", "rename",
    "replace", "chmod", "chown", "putenv", "startfile", "spawnl", "spawnv", "spawnvp",
    "execl", "execlp", "execv", "execve", "execvp", "exec_module", "load_module",
    # frame / generator / coroutine / traceback / function introspection
    "f_globals", "f_builtins", "f_locals", "f_back", "f_code", "f_trace",
    "gi_frame", "gi_code", "gi_yieldfrom", "cr_frame", "cr_code", "cr_await",
    "ag_frame", "ag_code", "tb_frame", "tb_next",
    "func_globals", "func_code", "func_closure", "func_defaults", "func_dict",
    # string-format field pivots (the f-string form is caught as real AST attributes instead)
    "format", "format_map",
})


def sanitize_cadquery(code: str) -> SanitizeResult:
    """Reject untrusted CadQuery source that could escape the geometry sandbox.

    Parses with :mod:`ast` (so a banned word inside a string or comment is never a false
    positive) and blocks — the caller re-prompts — on any of: a syntax error; an import of
    anything outside ``cadquery``/``math``; a banned builtin/module name (``open``, ``eval``,
    ``os`` …); or any ``__dunder__`` name/attribute, which is how nearly every restricted-exec
    escape (``__class__``, ``__subclasses__``, ``__builtins__``, ``__globals__``) is reached.
    Nothing is stripped, so valid geometry is never silently altered and there's no
    partial-strip bypass. The script is expected to assign a ``result`` object and do no I/O of
    its own — the worker performs every export.
    """
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError) as e:
        return SanitizeResult(code=code, blocked=[f"could not parse the CadQuery script: {e}"])

    blocked: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root not in _ALLOWED_IMPORT_ROOTS:
                    blocked.append(f"import of '{root}' is not allowed (only cadquery and math)")
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".", 1)[0]
            if root not in _ALLOWED_IMPORT_ROOTS:
                shown = node.module or "."  # `from . import x` -> relative, not allowed
                blocked.append(f"import of '{shown}' is not allowed (only cadquery and math)")
        elif isinstance(node, ast.Name):
            if "__" in node.id:
                blocked.append(f"dunder access '{node.id}' is not allowed")
            elif node.id in _BANNED_NAMES:
                blocked.append(f"use of '{node.id}' is not allowed in a CadQuery script")
        elif isinstance(node, ast.Attribute):
            if "__" in node.attr:
                blocked.append(f"dunder access '{node.attr}' is not allowed")
            elif node.attr in _BANNED_NAMES or node.attr in _BANNED_ATTRS:
                blocked.append(f"attribute access '.{node.attr}' is not allowed")
        elif isinstance(node, ast.Subscript):
            # A dunder hidden in a string-literal index — obj["__globals__"]["__import__"] —
            # is invisible to the Name/Attribute dunder checks (NEW-007). Catch str AND bytes
            # constant keys (ENG-003). NOTE: a *computed* dunder key (e.g. chr(95)+...) can't be
            # caught statically, but is inert by construction — the worker's restricted builtins
            # withhold the string-building primitives (chr/ord/bytes/type/getattr), so a dunder
            # string can't be built or used at runtime. Those two layers must stay coupled: never
            # add a string-construction builtin to the worker without re-hardening this check.
            sl = node.slice
            if isinstance(sl, ast.Constant) and isinstance(sl.value, (str, bytes)):
                key = sl.value if isinstance(sl.value, str) else sl.value.decode("latin-1", "ignore")
                if "__" in key:
                    blocked.append(f"subscript with a dunder key '{key}' is not allowed")
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            # AST stores these names as plain strings (not Name nodes), so scan them too.
            for nm in node.names:
                if "__" in nm or nm in _BANNED_NAMES:
                    blocked.append(f"use of '{nm}' is not allowed in a CadQuery script")

    # De-dupe while preserving order so the re-prompt feedback is concise.
    seen: set[str] = set()
    unique = [b for b in blocked if not (b in seen or seen.add(b))]
    return SanitizeResult(code=code, blocked=unique)


def render_cadquery(
    code: str,
    *,
    interpreter: Path,
    out_dir: Path,
    basename: str = "part",
    emit_step: bool = False,
    timeout_s: int = 120,
    max_output_bytes: int = 209_715_200,
    tessellation_mm: float = 0.1,
) -> RenderResult:
    """Sanitize and execute untrusted CadQuery ``code`` via the out-of-process worker,
    returning a :class:`RenderResult` pointing at the written STL (and the STEP, when
    ``emit_step``).

    Raises :class:`BlockedCodeError` (sanitizer rejected it — re-prompt),
    :class:`RenderTimeout`, :class:`RenderFailed` (worker / model error — re-prompt), or
    :class:`OversizeOutput`. ``interpreter`` is the resolved <=3.13 ``python`` that has
    cadquery installed (see :meth:`kimcad.config.Config.cadquery_interpreter`).
    """
    sanitized = sanitize_cadquery(code)
    if not sanitized.safe:
        raise BlockedCodeError(sanitized.blocked)

    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    script_path = out_dir / f"{basename}.cq.py"
    script_path.write_text(sanitized.code, encoding="utf-8")
    stl_path = out_dir / f"{basename}.stl"
    step_path = out_dir / f"{basename}.step" if emit_step else None
    result_path = out_dir / f"{basename}.cq-result.json"

    def _cleanup_outputs() -> None:
        stl_path.unlink(missing_ok=True)
        if step_path is not None:
            step_path.unlink(missing_ok=True)

    request = {
        "script_path": str(script_path),
        "stl_path": str(stl_path),
        "step_path": str(step_path) if step_path is not None else None,
        "result_path": str(result_path),
        "tessellation_mm": float(tessellation_mm),
    }

    started = time.monotonic()
    try:
        # ENG-002: run in the isolated out_dir with a secret-scrubbed env (mirrors the OpenSCAD
        # runner's isolation), so the worker never inherits the project cwd or any API key.
        proc = subprocess.run(
            [str(interpreter), str(WORKER_PATH)],
            input=json.dumps(request),
            capture_output=True,
            text=True,
            timeout=timeout_s,
            cwd=str(out_dir),
            env=_worker_env(),
        )
    except subprocess.TimeoutExpired as e:
        _cleanup_outputs()
        raise RenderTimeout(f"cadquery worker exceeded {timeout_s}s") from e
    duration = time.monotonic() - started

    result = _read_worker_result(result_path, proc)
    if not result.get("ok"):
        _cleanup_outputs()  # never leave a partial STL/STEP behind on a failure
        kind = str(result.get("kind", "exec"))
        error = str(result.get("error", "cadquery worker failed"))
        if kind == "blocked":
            # The static sanitizer should have caught this; treat a worker-side block as one too.
            raise BlockedCodeError([error])
        # exec/empty/export/protocol are re-promptable model/output errors.
        raise RenderFailed(proc.returncode, error, engine="cadquery")

    if not stl_path.exists():
        raise RenderFailed(
            proc.returncode, "worker reported success but wrote no STL", engine="cadquery"
        )
    size = stl_path.stat().st_size
    if size > max_output_bytes:
        _cleanup_outputs()
        raise OversizeOutput(f"cadquery produced {size} bytes (> {max_output_bytes} guard)")
    # ENG-006: the size guard covers the STEP too (it's read whole into memory to serve).
    if step_path is not None and step_path.exists() and step_path.stat().st_size > max_output_bytes:
        step_size = step_path.stat().st_size
        _cleanup_outputs()
        raise OversizeOutput(f"cadquery STEP is {step_size} bytes (> {max_output_bytes} guard)")

    have_step = step_path if (step_path is not None and step_path.exists()) else None
    return RenderResult(
        output_path=stl_path,
        output_format="stl",
        stdout=proc.stdout,
        stderr=proc.stderr,
        duration_s=duration,
        sanitize=sanitized,
        fell_back_to_stl=False,
        backend="cadquery",
        step_path=have_step,
    )


# The probe a candidate interpreter must pass: it can import cadquery (which implies a
# compatible Python, since cadquery ships no 3.14 wheels) and prints its own executable path,
# sentinel-delimited so a noisy interpreter (a startup banner / deprecation print) doesn't
# corrupt the parsed path (ENG-005).
_PROBE_SENTINEL = "__KIMCAD_CQ__"
_PROBE = (
    "import cadquery, sys; "
    f"sys.stdout.write('{_PROBE_SENTINEL}' + sys.executable + '{_PROBE_SENTINEL}')"
)


def find_cadquery_interpreter(
    candidates: Sequence[str | Path | Sequence[str]] = (),
    *,
    include_defaults: bool = True,
) -> Path | None:
    """Discover a Python interpreter that has CadQuery installed, or return None.

    Tries, in order: each ``candidates`` entry (a path, or an argv prefix like
    ``("py", "-3.13")`` — used for an explicit ``binaries.cadquery_python`` override), then —
    when ``include_defaults`` — the Windows ``py -3.13/-3.12/-3.11`` launcher and
    ``python3.13``/``…3.12``/``…3.11`` on PATH. The first candidate whose ``import cadquery``
    succeeds wins; its real ``sys.executable`` is returned (so a launcher resolves to a concrete
    ``python.exe``). Pass ``include_defaults=False`` to probe ONLY the given candidates (so an
    explicit config override is authoritative — a path without cadquery yields None, not a
    silent fall-through to some other interpreter). Never raises — a probe that errors is simply
    skipped, so a missing CadQuery just means the backend is unavailable (the same
    graceful-absence posture as the optional PrintProof3D engine)."""
    cmds: list[list[str]] = []
    for c in candidates:
        if isinstance(c, (str, Path)):
            cmds.append([str(c)])
        else:
            cmds.append([str(x) for x in c])
    if include_defaults:
        if sys.platform == "win32":
            # The documented repo-local worker venv wins over the global launcher probes.
            local_worker = PROJECT_ROOT / ".venv-cq313" / "Scripts" / "python.exe"
            cmds.append([str(local_worker)])
            cmds.extend([["py", f"-{v}"] for v in ("3.13", "3.12", "3.11")])
        cmds.extend([[n] for n in ("python3.13", "python3.12", "python3.11", "python3")])

    for cmd in cmds:
        try:
            # 20s is ample for an `import cadquery` probe (~3-4s warm) while bounding the
            # worst case if a candidate hangs; the Config layer caches the discovered result.
            # Scrub secrets from the probe env too (the probe needs none) — ENG-002.
            proc = subprocess.run(
                [*cmd, "-c", _PROBE], capture_output=True, text=True, timeout=20,
                env=_worker_env(),
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if proc.returncode != 0:
            continue
        # Parse the path from between the sentinels, so a startup banner before/after it doesn't
        # corrupt the result (ENG-005). Missing sentinels -> skip this candidate.
        parts = (proc.stdout or "").split(_PROBE_SENTINEL)
        if len(parts) >= 3:
            p = Path(parts[1])
            if p.exists():
                return p
    return None


def _read_worker_result(result_path: Path, proc: subprocess.CompletedProcess[str]) -> dict:
    """Read the worker's JSON result from its dedicated result file (so a script or OCCT
    writing to fd 1 can't corrupt it). If the file is missing/unparseable — the worker
    segfaulted or was killed before writing it — synthesize a clean failure from the captured
    stderr/stdout rather than raising."""
    try:
        data = json.loads(result_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (OSError, ValueError, TypeError):
        pass
    detail = (proc.stderr or proc.stdout or "no output").strip()[:500]
    return {"ok": False, "kind": "exec", "error": f"cadquery worker crashed: {detail}"}
