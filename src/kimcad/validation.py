"""Mesh validation pipeline (spec §6.5).

Load a rendered mesh, check watertightness, attempt conservative repairs, and report
geometric stats (volume, bounding box, body count). The bounding box computed here
feeds the Printability Gate's dimensional assertion (§6.6).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import trimesh


@dataclass
class MeshReport:
    watertight: bool
    repaired: bool
    repairs: list[str]
    vertices: int
    faces: int
    volume_mm3: float
    bounding_box_mm: tuple[float, float, float]
    n_bodies: int
    # Connected components whose bounding box is NOT nested inside another
    # component's — i.e. genuinely stray solids sitting apart from the main body,
    # as opposed to a sealed cavity surface (the inner skin of a hollow container,
    # which trimesh counts as a separate body but is not a mistake). The gate warns
    # on strays, not on plain hollow containers. See validate_mesh / _stray_body_count.
    #
    # Default: max(0, n_bodies - 1). validate_mesh always supplies the true
    # nested-vs-stray split from geometry; the default only applies to MeshReports
    # built by hand (e.g. in tests) that have a body count but no geometry to analyse,
    # so a hand-built multi-body report still reads as "all extra bodies are stray"
    # and warns, preserving the pre-existing behaviour.
    stray_bodies: int = -1
    errors: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.stray_bodies < 0:
            self.stray_bodies = max(0, self.n_bodies - 1)


def load_mesh(path: str | Path) -> trimesh.Trimesh:
    """Load a mesh file, flattening a multi-part Scene into one Trimesh."""
    loaded = trimesh.load(str(path), force="mesh")
    if isinstance(loaded, trimesh.Scene):
        loaded = loaded.dump(concatenate=True)
    if not isinstance(loaded, trimesh.Trimesh):
        raise ValueError(f"loaded geometry is not a triangle mesh: {type(loaded)!r}")
    return loaded


def validate_mesh(mesh: trimesh.Trimesh) -> tuple[trimesh.Trimesh, MeshReport]:
    """Validate and conservatively repair a mesh. Returns the (possibly repaired)
    mesh plus a report. Repairs are recorded so the UI can surface them
    ("filled 2 small holes").

    Measurement contract (ENG-005): when the input is not watertight it is repaired
    *in place*, and the bounding box and volume below are deliberately measured on the
    repaired mesh. That repaired mesh is the object returned from this function and the
    one the pipeline goes on to slice, so the report must describe the geometry that
    actually proceeds downstream — not the pre-repair input. The ``repaired`` /
    ``watertight`` flags record whether repair was needed and whether it succeeded, so
    a caller can still tell the part had a defect even though the stats reflect the
    post-repair shape.
    """
    repairs: list[str] = []
    errors: list[str] = []

    if not mesh.is_watertight:
        before_holes = _open_boundary_count(mesh)
        mesh.process(validate=True)
        trimesh.repair.fix_normals(mesh)
        trimesh.repair.fix_winding(mesh)
        filled = mesh.fill_holes()
        if filled:
            repairs.append(f"filled holes (was {before_holes} open boundary edges)")
        trimesh.repair.fix_inversion(mesh)
        if not mesh.is_watertight:
            errors.append("mesh is not watertight after repair")

    # Measured on the (possibly repaired) mesh that will be sliced — see contract above.
    extents = mesh.extents if mesh.extents is not None else np.zeros(3)
    bbox = (float(extents[0]), float(extents[1]), float(extents[2]))
    # ENG-001: a degenerate mesh can yield NaN/inf extents. IEEE NaN compares False against every
    # tolerance, so a non-finite bbox would SILENTLY PASS the dimension + build-volume gates. Record
    # it as an error here; the printability gate fails closed on it (see _check_finite_extents).
    if not bool(np.all(np.isfinite(extents))):
        errors.append("non-finite bounding box (degenerate geometry)")

    try:
        volume = float(abs(mesh.volume))
    except ValueError:  # pragma: no cover - degenerate mesh
        volume = 0.0
        errors.append("volume could not be computed")

    n_bodies = _body_count(mesh, errors)
    stray_bodies = _stray_body_count(mesh, errors)

    return mesh, MeshReport(
        watertight=bool(mesh.is_watertight),
        repaired=bool(repairs),
        repairs=repairs,
        vertices=int(len(mesh.vertices)),
        faces=int(len(mesh.faces)),
        volume_mm3=volume,
        bounding_box_mm=bbox,
        n_bodies=n_bodies,
        stray_bodies=stray_bodies,
        errors=errors,
    )


def _open_boundary_count(mesh: trimesh.Trimesh) -> int:
    # edges referenced by exactly one face are open boundary edges
    try:
        return int(len(mesh.edges_unique) - len(mesh.face_adjacency_edges))
    except (ValueError, AttributeError, TypeError):  # pragma: no cover
        return 0


def _body_count(mesh: trimesh.Trimesh, errors: list[str]) -> int:
    try:
        return int(mesh.body_count)
    except (ValueError, AttributeError, TypeError, ImportError) as exc:  # pragma: no cover
        # A degenerate mesh that can't be split is reported as a single body, but the
        # failure is recorded rather than swallowed so the gate doesn't silently treat
        # an unanalysable mesh as a clean single solid. ImportError covers trimesh's
        # optional scipy backend being absent (connected-component split needs it).
        errors.append(f"body count could not be computed ({exc})")
        return 1


def _stray_body_count(mesh: trimesh.Trimesh, errors: list[str]) -> int:
    """Count connected components that are NOT nested inside another component.

    A fully-sealed hollow container is one watertight solid, but trimesh sees two
    surface shells (outer skin + inner cavity skin) and reports ``body_count == 2``.
    The inner skin's axis-aligned bounding box is strictly contained within the outer
    skin's, so it is a *nested cavity*, not a *stray* body. Two solids sitting side by
    side have disjoint (non-contained) bounding boxes and ARE stray. We return the
    number of components whose bbox is not contained within any other component's, so
    a plain hollow box reports 0 strays while genuine loose geometry reports >= 1.
    """
    try:
        parts = mesh.split(only_watertight=False)
    except (ValueError, AttributeError, TypeError, ImportError) as exc:  # pragma: no cover
        # ImportError: trimesh's split needs the optional scipy backend; absent it we
        # can't analyse components, so report 0 strays (don't warn on what we can't see).
        errors.append(f"stray-body analysis could not be computed ({exc})")
        return 0
    if len(parts) <= 1:
        return 0

    boxes = [(np.asarray(p.bounds[0]), np.asarray(p.bounds[1])) for p in parts]

    # The "main" body is the component with the largest bounding box. For a hollow
    # container that is the OUTER shell, whose bbox contains the inner-cavity shell. A
    # component is *stray* only if it is neither the main body nor nested inside it — i.e.
    # it sits apart from the main solid. (The earlier version counted the outer shell as
    # stray because it isn't nested in anything, which false-flagged every hollow box.)
    def _bbox_volume(lo: np.ndarray, hi: np.ndarray) -> float:
        return float(np.prod(np.maximum(hi - lo, 0.0)))

    main = max(range(len(boxes)), key=lambda k: _bbox_volume(*boxes[k]))
    lo_m, hi_m = boxes[main]
    stray = 0
    for i, (lo_i, hi_i) in enumerate(boxes):
        if i != main and not _bbox_contains(lo_m, hi_m, lo_i, hi_i):
            stray += 1
    return int(stray)


def _bbox_contains(
    outer_lo: np.ndarray,
    outer_hi: np.ndarray,
    inner_lo: np.ndarray,
    inner_hi: np.ndarray,
    tol: float = 1e-6,
) -> bool:
    """True when the inner axis-aligned bbox sits inside the outer one (with tolerance):
    inner.min >= outer.min and inner.max <= outer.max on every axis."""
    return bool(
        np.all(inner_lo >= outer_lo - tol) and np.all(inner_hi <= outer_hi + tol)
    )
