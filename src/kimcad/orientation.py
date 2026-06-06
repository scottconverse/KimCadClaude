"""Auto-orientation (spec §6.7).

OpenSCAD emits geometry in whatever orientation the math dictates; FDM needs the part
flat on the plate. Compute stable resting poses (via the convex hull) and rotate the
part so the most probable resting face sits at Z = 0. The chosen orientation is
surfaced in the preview/report and can be overridden by the user.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import trimesh


@dataclass
class Orientation:
    transform: np.ndarray  # 4x4 homogeneous matrix applied to the mesh
    description: str
    stability: float  # probability of this resting pose (0..1), 1.0 if heuristic


def auto_orient(mesh: trimesh.Trimesh) -> tuple[trimesh.Trimesh, Orientation]:
    """Return a copy of the mesh rotated to its most stable resting pose, sitting on
    the bed (min Z = 0)."""
    oriented = mesh.copy()
    transform, stability, description = _best_pose(oriented)
    oriented.apply_transform(transform)
    drop = _drop_to_bed(oriented)
    full = drop @ transform
    return oriented, Orientation(transform=full, description=description, stability=stability)


def _best_pose(mesh: trimesh.Trimesh) -> tuple[np.ndarray, float, str]:
    try:
        transforms, probs = mesh.compute_stable_poses()
    except Exception:  # noqa: BLE001 - orientation is best-effort and must never break the build
        transforms, probs = [], []
    if len(transforms) > 0:
        idx = int(np.argmax(probs))
        return transforms[idx], float(probs[idx]), "rests on most stable facet"
    # ENG-004: no pose could be computed (or the call failed) — report 0.0 stability, NOT 1.0. The
    # part is left as-is, but that's the LEAST-certain orientation, not maximum confidence.
    return np.eye(4), 0.0, "no stable pose found; left as-is"


def _drop_to_bed(mesh: trimesh.Trimesh) -> np.ndarray:
    """Translation that moves the mesh so its lowest point sits at Z = 0."""
    t = np.eye(4)
    t[2, 3] = -float(mesh.bounds[0][2])
    return t
