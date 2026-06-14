"""#22 — the printer catalog is broad, honestly structured, and every entry is usable.

Offline structural tests (no binary): they read the shipped config's Printer objects, not the
slicer, so they run everywhere. The build-volume-against-the-real-Orca-profile check lives in
test_config.test_configured_build_volumes_match_the_shipped_orca_profiles (KC-7, binary-gated),
and the live slice-proof lives in test_slicer.test_live_slice_box_produces_proven_gcode.
"""
from __future__ import annotations

from kimcad.config import Config

REFERENCE_PRINTERS = ("bambu_p2s", "bambu_a1", "elegoo_neptune_4_max")


def test_catalog_offers_a_broad_slice_proven_printer_set():
    """#22: the picker offers a meaningfully broad catalog — the 3 reference printers plus a
    curated set of popular current machines across the top makers — and EVERY entry is genuinely
    usable (a positive build volume + a machine + a process + at least PLA), never a name-only
    stub. The slice-proof itself is the live test; this guards the catalog's shape + breadth."""
    cfg = Config.load()
    keys = list(cfg.raw.get("printers", {}))
    assert len(keys) >= 25, f"catalog regressed to {len(keys)} printers"
    vendors = {k.split("_", 1)[0] for k in keys}
    assert len(vendors) >= 7, f"only {len(vendors)} vendor families: {sorted(vendors)}"
    for k in keys:
        p = cfg.printer(k)
        assert p.build_volume and all(v > 0 for v in p.build_volume), f"{k}: bad build_volume"
        assert p.orca_machine_profile, f"{k}: no machine profile"
        assert p.orca_process_profile, f"{k}: not sliceable (no process profile)"
        assert p.orca_filament_profiles, f"{k}: offers no material"
        # PLA is the universal floor — a catalogued printer that can't print PLA wouldn't have
        # cleared the slice bar (scripts/build_printer_catalog.py --verify requires it).
        assert "pla" in p.orca_filament_profiles, f"{k}: no PLA"


def test_reference_printers_are_intact_and_flagged():
    """The 3 reference printers (Kim's target hardware) survive the catalog expansion and keep
    their reference_hardware flag — the tier the docs + UI lean on to distinguish them from the
    broader curated catalog."""
    cfg = Config.load()
    keys = cfg.raw.get("printers", {})
    for k in REFERENCE_PRINTERS:
        assert k in keys, f"reference printer {k} missing"
        assert cfg.printer(k).reference_hardware is True, f"{k} lost reference_hardware"
    # The curated (non-reference) catalog is the bulk of the breadth.
    curated = [k for k in keys if not cfg.printer(k).reference_hardware]
    assert len(curated) >= 20, f"only {len(curated)} curated (non-reference) printers"


def test_no_material_is_offered_without_a_filament_profile():
    """Honest material lists: a printer offers exactly the materials it has a shipped filament
    profile for — orca_filament_profiles IS the offer (web_options reports its keys), so a
    material can never be advertised without a backing profile (e.g. the A1 mini has no ABS)."""
    cfg = Config.load()
    for k in cfg.raw.get("printers", {}):
        p = cfg.printer(k)
        for mat, profile in p.orca_filament_profiles.items():
            assert profile and isinstance(profile, str), f"{k}/{mat}: empty filament profile"
            assert mat in cfg.raw.get("materials", {}), f"{k}: offers unknown material {mat!r}"
