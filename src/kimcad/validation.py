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
    errors: list[str] = field(default_factory=list)


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
    ("filled 2 small holes")."""
    repairs: list[str] = []
    errors: list[str] = []

    if not mesh.is_watertight:
        before_holes = _open_boundary_count(mesh)
        mesh.process(validate=True)
        trimesh.repair.fix_normals(mesh)
        trimesh.repair.fix_winding(mesh)
        filled = mesh.fill_holes()
        if filled:
            repairs.append(f"filled holes (was {before_holes} open boundary loops)")
        trimesh.repair.fix_inversion(mesh)
        if not mesh.is_watertight:
            errors.append("mesh is not watertight after repair")

    extents = mesh.extents if mesh.extents is not None else np.zeros(3)
    bbox = (float(extents[0]), float(extents[1]), float(extents[2]))

    try:
        volume = float(abs(mesh.volume))
    except Exception:  # pragma: no cover - degenerate mesh
        volume = 0.0
        errors.append("volume could not be computed")

    return mesh, MeshReport(
        watertight=bool(mesh.is_watertight),
        repaired=bool(repairs),
        repairs=repairs,
        vertices=int(len(mesh.vertices)),
        faces=int(len(mesh.faces)),
        volume_mm3=volume,
        bounding_box_mm=bbox,
        n_bodies=_body_count(mesh),
        errors=errors,
    )


def _open_boundary_count(mesh: trimesh.Trimesh) -> int:
    # edges referenced by exactly one face are open boundary edges
    try:
        return int(len(mesh.edges_unique) - len(mesh.face_adjacency_edges))
    except Exception:  # pragma: no cover
        return 0


def _body_count(mesh: trimesh.Trimesh) -> int:
    try:
        return int(mesh.body_count)
    except Exception:  # pragma: no cover
        return 1
