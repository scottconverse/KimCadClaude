"""Pre-slice mesh hardening via Manifold3D (spec §6.8).

Trimesh's ``is_watertight`` is a necessary check, not a sufficient one: a mesh can be
watertight yet still carry non-manifold edges, duplicated/degenerate triangles, or
self-intersections that make a slicer mis-toolpath or silently auto-"repair" it in ways
the user never sees. Before a part is sliced (or exported as the download fallback), we
run it through Manifold3D, whose data model is a *guaranteed* 2-manifold: building a
``Manifold`` from the mesh merges coincident vertices, drops degenerate triangles, and
either yields a clean manifold or reports precisely why it could not.

Manifold3D is a HARD dependency (pinned in pyproject.toml: ``manifold3d>=3.0``). The import
guard below is DEFENSIVE, not an "optional feature" switch: if the package is somehow absent
(a broken/partial install), hardening degrades to a no-op pass-through and says so in the report
rather than crashing — the mesh has already passed the Printability Gate's watertight check, so
slicing still proceeds on the validated mesh. (ENG-007: the comment is reconciled with the hard
pin — install the project and it's always present; the fallback exists only for resilience.)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class HardenReport:
    """Outcome of the pre-slice hardening pass."""

    engine: str  # "manifold3d" or "skipped"
    ok: bool  # a clean manifold was produced
    status: str  # engine status string (e.g. "Error.NoError")
    genus: int | None  # topological genus, when known
    changed: bool  # vertex/face count differed after hardening (a real repair)
    before: tuple[int, int]  # (vertices, faces) in
    after: tuple[int, int]  # (vertices, faces) out
    note: str = ""

    def summary(self) -> str:
        if self.engine == "skipped":
            return f"hardening skipped ({self.note or 'manifold3d unavailable'})"
        if not self.ok:
            return f"hardening could not build a manifold ({self.status}); kept validated mesh"
        detail = f"genus {self.genus}" if self.genus is not None else self.status
        return f"hardened via manifold3d ({detail})" + (", repaired" if self.changed else "")


def harden_mesh(mesh: Any) -> tuple[Any, HardenReport]:
    """Return ``(hardened_mesh, report)``.

    On any problem — Manifold3D absent, or it rejects the mesh — the original
    (already gate-validated) mesh is returned unchanged, with the reason recorded.
    Never raises: hardening is a best-effort robustness pass, not a gate.
    """
    before = (len(mesh.vertices), len(mesh.faces))
    try:
        import manifold3d as m3d
        import numpy as np
        import trimesh
    except ImportError as e:  # pragma: no cover - exercised via monkeypatch
        return mesh, HardenReport(
            engine="skipped", ok=False, status="ImportError", genus=None,
            changed=False, before=before, after=before,
            note=f"manifold3d unavailable ({e})",
        )

    try:
        # ENG-006: Manifold3D's mesh is float32 vertices / uint32 faces, so the hardened
        # mesh is float32-derived — every vertex is perturbed to ~7 significant digits
        # (sub-micron at print scale, far below the gate's 0.5 mm tolerance). This is why
        # the pipeline re-derives the report's facts from the hardened mesh when it
        # actually changed (ENG-001), rather than assuming a bit-identical round-trip.
        mesh_in = m3d.Mesh(
            vert_properties=np.asarray(mesh.vertices, dtype=np.float32),
            tri_verts=np.asarray(mesh.faces, dtype=np.uint32),
        )
        man = m3d.Manifold(mesh_in)
        status = str(man.status())
        if man.status() != m3d.Error.NoError or man.is_empty():
            return mesh, HardenReport(
                engine="manifold3d", ok=False, status=status, genus=None,
                changed=False, before=before, after=before,
                note="manifold3d could not build a manifold; kept the validated mesh",
            )
        out = man.to_mesh()
        verts = np.asarray(out.vert_properties)[:, :3]
        faces = np.asarray(out.tri_verts)
        hardened = trimesh.Trimesh(vertices=verts, faces=faces, process=False)
    except Exception as e:  # never let hardening break a validated part
        return mesh, HardenReport(
            engine="manifold3d", ok=False, status=f"{type(e).__name__}: {e}", genus=None,
            changed=False, before=before, after=before,
            note="hardening raised; kept the validated mesh",
        )

    after = (len(hardened.vertices), len(hardened.faces))
    return hardened, HardenReport(
        engine="manifold3d", ok=True, status=status, genus=man.genus(),
        changed=(after != before), before=before, after=after,
    )
