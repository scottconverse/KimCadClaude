"""CadQuery execution worker — runs OUT OF PROCESS in its own interpreter.

KimCad targets Python 3.13 and CadQuery runs on 3.13 too — the out-of-process split is a
SECURITY-ISOLATION choice (untrusted generated code stays in its own interpreter with
restricted builtins), not a version constraint; CadQuery is shelled out exactly the way
OpenSCAD and OrcaSlicer are (arm's-length subprocess; spec §6.4/§12).

This file is deliberately **stdlib + cadquery only** — it must import cleanly under the
worker interpreter (which has cadquery but not kimcad), so it NEVER imports ``kimcad``
or anything from the app venv. The in-process side (:mod:`kimcad.cadquery_runner`)
writes the sanitized script to a temp file and invokes::

    <py3.13> path/to/cadquery_worker.py   # request JSON on stdin, RESULT JSON to result_path

Protocol
--------
Request  (stdin, one JSON object):
    {"script_path": "...", "stl_path": "...", "step_path": "..."|null,
     "result_path": "...", "tessellation_mm": 0.1}
Result   (written to ``result_path`` as one JSON object — NOT stdout, see Security #3):
    {"ok": true,  "bbox_mm": [x, y, z], "stl_bytes": N, "step_bytes": N|null}
    {"ok": false, "kind": "blocked|exec|empty|export|protocol", "error": "..."}

Security (the generated CadQuery is untrusted LLM output)
--------------------------------------------------------
There are two layers, with an HONEST division of what each one independently guarantees:

1. **Static sanitizer (the PRIMARY layer)** — :func:`kimcad.cadquery_runner.sanitize_cadquery`
   rejects dangerous source before it reaches this worker: non-cadquery/math imports; banned
   names/attributes (``os``, ``open``, ``system`` …); ALL ``__dunder__`` names, attributes,
   and string-subscript keys; frame/function introspection attributes (``gi_frame``,
   ``f_builtins``, ``func_globals`` …); and ``str.format`` field pivots. This is the only layer
   that closes the introspection / ``__globals__`` escape class — see point 3.
2. **Worker runtime (the SECONDARY layer)** — the script runs with a **restricted
   ``__builtins__``** (no ``open``/``eval``/``exec``/``compile``/``input``; an ``__import__``
   that returns the cadquery FACADE for ``import cadquery``, the real ``math`` for ``import
   math``, and **raises ``ImportError`` for every other import**) against a **geometry-only
   facade** of cadquery — every top-level cadquery SUBMODULE (``exporters``, ``importers``,
   ``occ_impl`` …) is
   stripped, so no module object is in scope to pivot through to ``os`` (the ``cq.exporters.os``
   class). The script does **no file I/O at all**: it assigns a ``result`` object; this worker
   does every export. The JSON result is written to a dedicated ``result_path`` file (never
   stdout), so a native fd-1 write cannot corrupt the contract.

3. **What the worker layer canNOT independently do**, by design of CPython: a cadquery facade
   function still carries its real, unrestricted ``__builtins__`` inside ``__globals__``, so a
   script reaching ``some_func.__globals__["__builtins__"]`` would get full ``import`` power.
   Every such path needs a dunder or an introspection attribute, which the static sanitizer
   blocks — so that escape class is closed by layer 1, not layer 2. The durable, defence-in-depth
   answer (OS-level process confinement: no network, restricted working dir) is tracked as a
   later hardening; it is NOT yet implemented.

Net: this is sanitizer-anchored defence in depth, not a perfect in-process sandbox. The ultimate
boundary is that KimCad runs locally on the user's own machine — the same trust model as
executing generated OpenSCAD.
"""

from __future__ import annotations

# These are HARNESS-ONLY imports (file read, file-size lookup, the stdout fallback). They are
# never exposed to the executed script: the script runs against an explicit fresh namespace with
# `_safe_builtins` (no `os`/`sys`), not this module's globals (ENG-007).
import contextlib
import io
import json
import math
import os
import sys
import types


def _build_facade(cadquery: types.ModuleType) -> types.SimpleNamespace:
    """A geometry-only view of cadquery: every public CLASS/FUNCTION, but NO submodule.

    Stripping module objects (``exporters``, ``importers``, ``occ_impl``, ``selectors`` …)
    removes the only reliable path a dunder-free script has to reach ``os``/``subprocess``
    (``cq.exporters.os.system(...)``). The facade still exposes ``Workplane``, ``Sketch``,
    ``Assembly``, ``Vector``, ``Solid`` and the rest of the modelling surface."""
    facade = types.SimpleNamespace()
    for name, val in vars(cadquery).items():
        if name.startswith("_") or isinstance(val, types.ModuleType):
            continue
        setattr(facade, name, val)
    return facade


def _safe_import(facade: types.SimpleNamespace):
    """Return a locked-down ``__import__`` closed over the cadquery facade: a benign
    ``import cadquery as cq`` hands back the FACADE (not the real module), ``import math``
    hands back math, and everything else raises ImportError."""

    def _imp(name: str, *_args: object, **_kwargs: object) -> object:
        root = name.split(".", 1)[0]
        if root == "cadquery":
            return facade
        if root == "math":
            return math
        raise ImportError(f"import of '{name}' is not allowed in a CadQuery script")

    return _imp


def _safe_builtins(facade: types.SimpleNamespace) -> dict[str, object]:
    """A minimal builtins map: the names geometry code legitimately needs, and nothing that
    can open a file, evaluate a string, or escape the namespace. ``open``/``eval``/``exec``/
    ``compile``/``input``/``globals``/``vars``/``getattr``/``setattr``/the real ``__import__``
    are all withheld; a restricted ``__import__`` is supplied separately."""
    allowed = (
        "abs", "all", "any", "bool", "dict", "divmod", "enumerate", "filter", "float",
        "frozenset", "int", "len", "list", "map", "max", "min", "pow", "range", "reversed",
        "round", "set", "slice", "sorted", "str", "sum", "tuple", "zip",
        "True", "False", "None",
        "ValueError", "TypeError", "ZeroDivisionError", "ArithmeticError", "Exception",
    )
    src = __builtins__ if isinstance(__builtins__, dict) else vars(__builtins__)
    safe: dict[str, object] = {k: src[k] for k in allowed if k in src}
    safe["__import__"] = _safe_import(facade)
    return safe


def _run(request: dict[str, object]) -> dict[str, object]:
    script_path = request.get("script_path")
    stl_path = request.get("stl_path")
    step_path = request.get("step_path")
    tess = request.get("tessellation_mm", 0.1)
    if not isinstance(script_path, str) or not isinstance(stl_path, str):
        return {"ok": False, "kind": "protocol", "error": "script_path and stl_path required"}

    try:
        with open(script_path, encoding="utf-8") as f:
            code = f.read()
    except OSError as e:  # pragma: no cover - the runner just wrote this file
        return {"ok": False, "kind": "protocol", "error": f"cannot read script: {e}"}

    try:
        import cadquery as cq
        from cadquery import exporters
    except Exception as e:  # noqa: BLE001 - any import failure is reported, not raised
        return {"ok": False, "kind": "exec", "error": f"cadquery import failed: {e}"}

    facade = _build_facade(cq)
    namespace: dict[str, object] = {
        "__builtins__": _safe_builtins(facade),
        "cq": facade,
        "cadquery": facade,
        "math": math,
    }

    # Execute the (already statically-sanitized) script with the script's Python-level
    # stdout/stderr swallowed. The authoritative result goes to result_path, not stdout, so
    # even a native fd-1 write can't corrupt it; this just keeps stray prints out of the
    # captured diagnostic stream.
    try:
        compiled = compile(code, "<cadquery-script>", "exec")
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            exec(compiled, namespace)  # noqa: S102 - sandboxed builtins + facade; documented boundary
    except Exception as e:  # noqa: BLE001 - a model bug must surface as a clean error, not a crash
        return {"ok": False, "kind": "exec", "error": f"{type(e).__name__}: {e}"}

    result = namespace.get("result")
    if result is None:
        return {
            "ok": False,
            "kind": "empty",
            "error": "the script defined no `result` object to export",
        }

    # Measure the solid before export so an empty/degenerate result is caught here with a
    # clear message rather than as a downstream mesh-load failure.
    try:
        val = result.val() if hasattr(result, "val") else result
        bb = val.BoundingBox()
        bbox = [round(bb.xlen, 4), round(bb.ylen, 4), round(bb.zlen, 4)]
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "kind": "empty", "error": f"result has no measurable solid: {e}"}
    if min(bbox) <= 0.0:
        return {"ok": False, "kind": "empty", "error": f"result is degenerate (bbox {bbox})"}

    try:
        try:
            exporters.export(result, stl_path, tolerance=float(tess))
        except TypeError:  # pragma: no cover - older cadquery: no tolerance kwarg
            exporters.export(result, stl_path)
        step_bytes = None
        if isinstance(step_path, str):
            exporters.export(result, step_path)
            step_bytes = os.path.getsize(step_path)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "kind": "export", "error": f"export failed: {type(e).__name__}: {e}"}

    return {
        "ok": True,
        "bbox_mm": bbox,
        "stl_bytes": os.path.getsize(stl_path),
        "step_bytes": step_bytes,
    }


def _emit(result: dict[str, object], result_path: str | None) -> None:
    """Write the result JSON to the dedicated result file (never stdout). If no result_path
    was supplied (a malformed request), fall back to stdout so the failure is still visible."""
    payload = json.dumps(result)
    if result_path:
        try:
            with open(result_path, "w", encoding="utf-8") as f:
                f.write(payload)
            return
        except OSError:
            pass
    sys.stdout.write(payload)


def main() -> int:
    result_path: str | None = None
    try:
        request = json.loads(sys.stdin.read() or "{}")
        if not isinstance(request, dict):
            raise ValueError("request must be a JSON object")
        rp = request.get("result_path")
        result_path = rp if isinstance(rp, str) else None
    except (ValueError, TypeError) as e:
        _emit({"ok": False, "kind": "protocol", "error": str(e)}, result_path)
        return 0
    _emit(_run(request), result_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
