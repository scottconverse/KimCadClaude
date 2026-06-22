"""#22 — generate KimCad printer-catalog candidates from the shipped OrcaSlicer profile tree.

For a curated set of popular current machines, this resolves each machine's build volume
(printable_area/printable_height through the ``inherits`` chain — the same recipe KC-7's
test_configured_build_volumes_match verifies) and proposes the OrcaSlicer process + per-material
filament profile names the tree marks (or names) compatible. The proposals are *candidates*: the
authoritative proof a printer is usable is a live slice (Orca rejects an incompatible combo at
slice time), done by tests/test_printer_catalog live-slice smoke and recorded per entry.

Usage:
    python scripts/build_printer_catalog.py            # print candidate YAML blocks
    python scripts/build_printer_catalog.py --keys     # just the curated keys it resolved

This is a build/maintenance tool (not shipped at runtime); re-run it when the bundled Orca
profile tree is updated to refresh candidates, then hand-review into config/default.yaml.
"""
from __future__ import annotations

import argparse
import json
import re
from collections.abc import Iterable
from pathlib import Path

def _resolve_profiles_root() -> Path:
    """The OrcaSlicer profile tree to index. Prefer the bundled location (tools/orcaslicer/...),
    but fall back to wherever config actually points the slicer (config/local.yaml may install
    OrcaSlicer system-wide, e.g. under ..\\_tools\\...). Without this fallback the candidate
    builder finds nothing on a box that uses a non-bundled slicer, so --verify would write a
    vacuous 0/0 proof-of-record."""
    bundled = Path(__file__).resolve().parent.parent / "tools" / "orcaslicer" / "resources" / "profiles"
    if bundled.exists():
        return bundled
    try:
        import sys

        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
        from kimcad.config import Config

        configured = Config.load().orca_profiles_root()
        if configured.exists():
            return configured
    except Exception:  # noqa: BLE001 — fall back to the bundled path's (non-existent) default
        pass
    return bundled


ROOT = _resolve_profiles_root()

# name -> (path, data) for every profile in the tree (machine, process, filament). Built once.
_BY_NAME: dict[str, tuple[Path, dict]] = {}


def _index() -> None:
    if _BY_NAME:
        return
    for f in ROOT.rglob("*.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        nm = d.get("name") or f.stem
        _BY_NAME.setdefault(nm, (f, d))


def _get(name: str | None, key: str, seen: set | None = None):
    """Read ``key`` from a profile, walking its ``inherits`` chain (KC-7's resolver)."""
    seen = seen or set()
    if not name or name in seen or name not in _BY_NAME:
        return None
    seen.add(name)
    _, d = _BY_NAME[name]
    if key in d:
        return d[key]
    return _get(d.get("inherits"), key, seen)


def build_volume(machine: str) -> list[int] | None:
    area, height = _get(machine, "printable_area"), _get(machine, "printable_height")
    if not area or height is None:
        return None
    try:
        xs = [float(c.split("x")[0]) for c in area]
        ys = [float(c.split("x")[1]) for c in area]
        return [round(max(xs)), round(max(ys)), round(float(height))]
    except (ValueError, AttributeError, TypeError):
        return None


def _pick_machine(hits: list[str]) -> str:
    """Among machine profiles matching a model pattern, prefer one whose build volume RESOLVES
    (a bare base profile often inherits geometry it doesn't carry) and that is the 0.4-nozzle
    variant, then the shorter name."""
    def score(m: str):
        return (1 if build_volume(m) else 0, 1 if re.search(r"0\.4 nozzle", m) else 0, -len(m))
    return sorted(hits, key=score, reverse=True)[0]


def _nozzle(machine: str) -> float:
    """The nozzle in mm. Common templates inherit a multi-value like '0.2;0.4;0.6;0.8'; every
    curated entry is a 0.4-nozzle machine variant, so prefer 0.4 when it's offered, else the
    first listed, else 0.4."""
    raw = _get(machine, "nozzle_diameter")
    if isinstance(raw, list):
        raw = ";".join(str(x) for x in raw)
    if isinstance(raw, str):
        opts = [o.strip() for o in raw.replace(",", ";").split(";") if o.strip()]
        raw = "0.4" if "0.4" in opts else (opts[0] if opts else "0.4")
    try:
        return float(raw)
    except (ValueError, TypeError):
        return 0.4


def _vendor_dir(name: str) -> Path | None:
    hit = _BY_NAME.get(name)
    if not hit:
        return None
    # .../<Vendor>/<machine|process|filament>[/<sub>]/<name>.json  -> the <Vendor> dir
    p = hit[0]
    for parent in p.parents:
        if parent.parent == ROOT:
            return parent
    return None


def _profiles_in(vendor_dir: Path, kind: str) -> list[str]:
    d = vendor_dir / kind
    out = []
    if d.is_dir():
        for f in d.rglob("*.json"):
            try:
                out.append(json.loads(f.read_text(encoding="utf-8")).get("name") or f.stem)
            except (ValueError, OSError):
                continue
    return out


def _machines_for(profile_name: str) -> list[str]:
    """The machine names a process/filament profile lists in compatible_printers (own or inherited)."""
    cps = _get(profile_name, "compatible_printers")
    return cps if isinstance(cps, list) else []


def _stem(name: str) -> str:
    """The FILENAME stem of a profile (what _find_profile_json / KC-7 resolve by), not its
    `name` field — they can differ (e.g. a process file '... K1C 0.4 nozzle.json' whose name is
    '... K1C'). Falls back to the name if it isn't a unique indexed file."""
    hit = _BY_NAME.get(name)
    return hit[0].stem if hit else name


_BAD_PROCESS = re.compile(r"SOLUBLE|MMU|SUPPORT|INTERFACE|ABRASIVE|Draft|Fine", re.I)


def pick_process(machine: str, vendor_dir: Path | None) -> str | None:
    # 1) profiles that explicitly list this machine as compatible
    listed = [n for n, (f, _) in _BY_NAME.items()
              if f.parent.name == "process" or f.parent.parent.name == "process"]
    cands = [n for n in listed if machine in _machines_for(n)]
    # 2) fallback (condition-based vendors expose no explicit list): same-vendor process profiles
    if not cands and vendor_dir is not None:
        cands = _profiles_in(vendor_dir, "process")
    cands = [c for c in cands if not _BAD_PROCESS.search(c)]
    if not cands:
        return None

    def rank(name: str):
        # prefer 0.20mm Standard/Quality/Normal/SPEED, then a 0.4-nozzle-specific file, then shorter
        std = bool(re.search(r"0\.2(0)?mm.*(Standard|Quality|Normal|SPEED|STRUCTURAL)", name, re.I))
        is020 = bool(re.search(r"0\.2(0)?mm", name))
        n04 = bool(re.search(r"0\.4", name))
        return (is020, std, n04, -len(name))

    return _stem(sorted(cands, key=rank, reverse=True)[0])


# Skip experimental ('BETA'/'COEX'), specialty (silk/CF/wood/…), and non-0.4 nozzle filaments —
# the catalog wants the canonical everyday profile for each material.
_BAD_FIL = re.compile(
    r"\bBETA\b|\bCOEX\b|Silk|Matte|Marble|Wood|Glow|Luminous|Sparkle|Galaxy|\bCF\b|\bGF\b|"
    r"Support|Dynamic|@base|0\.[268] nozzle|High Speed|HighSpeed|@HS", re.I)


def pick_filaments(machine: str, vendor_dir: Path | None) -> dict[str, str]:
    listed = [n for n, (f, _) in _BY_NAME.items()
              if f.parent.name == "filament" or f.parent.parent.name == "filament"]
    explicit = [n for n in listed if machine in _machines_for(n)]
    fallback = _profiles_in(vendor_dir, "filament") if vendor_dir is not None else []
    wants = {
        "pla": ["PLA Basic", "PLA", "Generic PLA"],
        "petg": ["PETG Basic", "PETG", "Generic PETG"],
        "tpu": ["TPU 95A", "TPU", "Generic TPU"],
        "abs": ["ABS", "ASA", "Generic ABS"],
    }
    out: dict[str, str] = {}
    for mat, prefs in wants.items():
        pool = [c for c in (explicit or fallback) if not _BAD_FIL.search(c)]
        for pref in prefs:
            hit = [c for c in pool if pref.lower() in c.lower()]
            if hit:
                # canonical pick: an unambiguous '@'-suffixed name first, a vendor brand over a bare
                # 'Generic', then the shorter (less special-cased) name.
                hit.sort(key=lambda c: ("@" not in c, c.lower().startswith("generic"), len(c)))
                out[mat] = _stem(hit[0])
                break
    return out


# Curated popular-current machines: key -> (display name, machine-profile regex). 0.4 nozzle preferred.
CURATED: dict[str, tuple[str, str]] = {
    "bambu_p1p": ("Bambu Lab P1P", r"^Bambu Lab P1P 0\.4 nozzle$"),
    "bambu_p1s": ("Bambu Lab P1S", r"^Bambu Lab P1S 0\.4 nozzle$"),
    "bambu_x1c": ("Bambu Lab X1 Carbon", r"^Bambu Lab X1 Carbon 0\.4 nozzle$"),
    "bambu_x1e": ("Bambu Lab X1E", r"^Bambu Lab X1E 0\.4 nozzle$"),
    "bambu_a1_mini": ("Bambu Lab A1 mini", r"^Bambu Lab A1 mini 0\.4 nozzle$"),
    "bambu_h2d": ("Bambu Lab H2D", r"^Bambu Lab H2D 0\.4 nozzle$"),
    "creality_k1": ("Creality K1", r"^Creality K1 \(0\.4 nozzle\)$"),
    "creality_k1_max": ("Creality K1 Max", r"^Creality K1 Max \(0\.4 nozzle\)$"),
    "creality_k1c": ("Creality K1C", r"^Creality K1C 0\.4 nozzle$"),
    "creality_k2_plus": ("Creality K2 Plus", r"^Creality K2 Plus 0\.4 nozzle$"),
    "creality_ender3_v3": ("Creality Ender-3 V3", r"^Creality Ender-3 V3 0\.4 nozzle$"),
    "creality_ender3_v3_ke": ("Creality Ender-3 V3 KE", r"^Creality Ender-3 V3 KE 0\.4 nozzle$"),
    "creality_ender3_v3_se": ("Creality Ender-3 V3 SE", r"^Creality Ender-3 V3 SE"),
    "creality_ender5_s1": ("Creality Ender-5 S1", r"^Creality Ender-5 S1 0\.4 nozzle$"),
    "creality_cr10_se": ("Creality CR-10 SE", r"^Creality CR-10 SE 0\.4 nozzle$"),
    "prusa_mk4s": ("Prusa MK4S", r"^Prusa MK4S 0\.4 nozzle$"),
    "prusa_mk4": ("Prusa MK4", r"^Prusa MK4 0\.4 nozzle$"),
    "prusa_mini": ("Prusa MINI", r"^Prusa MINI"),
    "prusa_core_one": ("Prusa CORE One", r"^Prusa CORE One 0\.4 nozzle$"),
    "prusa_xl": ("Prusa XL", r"^Prusa XL.*0\.4 nozzle$"),
    "anycubic_kobra2": ("Anycubic Kobra 2", r"^Anycubic Kobra 2 0\.4 nozzle$"),
    "anycubic_kobra2_max": ("Anycubic Kobra 2 Max", r"^Anycubic Kobra 2 Max"),
    "anycubic_kobra3": ("Anycubic Kobra 3", r"^Anycubic Kobra 3 0\.4 nozzle$"),
    "anycubic_kobra_s1": ("Anycubic Kobra S1", r"^Anycubic Kobra S1"),
    # OrcaSlicer 2.4.0 renamed the Neptune 4 machine profiles to drop the parenthesized "(0.4
    # nozzle)" in favor of " 0.4 nozzle" (matches the shipped tree + config/default.yaml).
    "elegoo_neptune4": ("Elegoo Neptune 4", r"^Elegoo Neptune 4 0\.4 nozzle$"),
    "elegoo_neptune4_pro": ("Elegoo Neptune 4 Pro", r"^Elegoo Neptune 4 Pro 0\.4 nozzle$"),
    "elegoo_neptune4_plus": ("Elegoo Neptune 4 Plus", r"^Elegoo Neptune 4 Plus 0\.4 nozzle$"),
    "qidi_q1_pro": ("Qidi Q1 Pro", r"^Qidi Q1 Pro 0\.4 nozzle$"),
    "qidi_xmax3": ("Qidi X-Max 3", r"^Qidi X-Max 3 0\.4 nozzle$"),
    "qidi_xplus3": ("Qidi X-Plus 3", r"^Qidi X-Plus 3 0\.4 nozzle$"),
    "sovol_sv06": ("Sovol SV06", r"^Sovol SV06 0\.4 nozzle$"),
    "sovol_sv07": ("Sovol SV07", r"^Sovol SV07 0\.4 nozzle$"),
    "sovol_sv08": ("Sovol SV08", r"^Sovol SV08 0\.4 nozzle$"),
    "voron_24_350": ("Voron 2.4 350", r"^Voron 2\.4 350 0\.4 nozzle$"),
    "flashforge_ad5m": ("Flashforge Adventurer 5M", r"^Flashforge Adventurer 5M 0\.4 nozzle$|^Flashforge Adventurer 5M$"),
    "flashforge_ad5m_pro": ("Flashforge Adventurer 5M Pro", r"^Flashforge Adventurer 5M Pro"),
    "anker_m5": ("AnkerMake M5", r"^Anker M5 0\.4 nozzle$|^Anker M5$"),
    "anker_m5c": ("AnkerMake M5C", r"^Anker M5C 0\.4 nozzle$|^Anker M5C$"),
}


def resolve_candidates() -> dict[str, dict]:
    _index()
    machine_names = [n for n, (f, _) in _BY_NAME.items() if "machine" in f.parts[len(ROOT.parts):]]
    out: dict[str, dict] = {}
    for key, (display, pat) in CURATED.items():
        hits = [m for m in machine_names if re.search(pat, m)]
        if not hits:
            out[key] = {"display": display, "error": f"no machine matches /{pat}/"}
            continue
        machine = _pick_machine(hits)
        bv = build_volume(machine)
        vd = _vendor_dir(machine)
        out[key] = {
            "display": display, "machine": machine, "build_volume": bv,
            "nozzle": _nozzle(machine),
            "process": pick_process(machine, vd),
            "filaments": pick_filaments(machine, vd),
        }
    return out


def _emit_yaml(key: str, c: dict) -> str:
    if "error" in c:
        return f"  # {key}: {c['error']}"
    fils = "\n".join(f"      {m}: \"{p}\"" for m, p in c["filaments"].items())
    return (
        f"  {key}:\n"
        f"    name: \"{c['display']}\"\n"
        f"    build_volume: {c['build_volume']}\n"
        f"    nozzle_diameter: {c['nozzle']}\n"
        f"    orca_machine_profile: \"{c['machine']}\"\n"
        f"    orca_process_profile: \"{c['process']}\"\n"
        f"    orca_filament_profiles:\n{fils}"
    )


def _slice_ok(root, binary, printer, material) -> bool:
    """True iff the 20 mm box slices to a real motion-bearing toolpath for this printer+material."""
    import tempfile

    import trimesh

    from kimcad.slicer import resolve_slice_settings, slice_model
    try:
        settings = resolve_slice_settings(root, printer, material)
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            stl = tdp / "box.stl"
            trimesh.creation.box(extents=[20, 20, 20]).export(str(stl))
            res = slice_model(stl, binary=binary, out_dir=tdp, settings=settings, basename="box", timeout_s=300)
            pr = res.gcode_proof
            return bool(pr and pr.has_motion and pr.line_count > 100 and pr.layer_count and pr.layer_count >= 80)
    except Exception:  # noqa: BLE001 - an incompatible combo is a clean 'no', not a crash
        return False


def verify_slices(cands: dict[str, dict]) -> dict[str, dict]:
    """Live-slice a 20 mm box for EACH candidate and EACH proposed material (the existing 'proven
    to slice' bar). Orca rejects an incompatible machine/process/filament combo, so a clean slice
    IS the compatibility proof. A printer is kept only if PLA slices; each non-PLA material is kept
    only if it slices too (honest per-material list). Prints the verified catalog YAML at the end."""
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
    from kimcad.config import Config, Printer

    cfg = Config.load()
    root, binary = cfg.orca_profiles_root(), cfg.binary_path("orcaslicer")
    mats = {m: cfg.material(m) for m in ("pla", "petg", "tpu", "abs")}
    verified: dict[str, dict] = {}
    for key, c in cands.items():
        if "error" in c or not c.get("build_volume") or "pla" not in c.get("filaments", {}):
            print(f"  SKIP (unresolved)                              {key}", flush=True)
            continue
        proven: dict[str, str] = {}
        for mat, fil in c["filaments"].items():
            if mat not in mats:
                continue
            printer = Printer(
                key=key, name=c["display"], build_volume=tuple(c["build_volume"]),
                nozzle_diameter=c["nozzle"], orca_machine_profile=c["machine"],
                orca_process_profile=c["process"], orca_filament_profiles={mat: fil},
            )
            if _slice_ok(root, binary, printer, mats[mat]):
                proven[mat] = fil
        if "pla" in proven:
            verified[key] = {**c, "filaments": proven}
            print(f"  OK  [{''.join(m[0].upper() if m in proven else '-' for m in ('pla','petg','tpu','abs'))}]  {key:26} <- {c['machine']}", flush=True)
        else:
            print(f"  FAIL (PLA won't slice)                         {key:26} <- {c['machine']}", flush=True)
    print(f"\n# slice-proven printers: {len(verified)}/{sum(1 for c in cands.values() if 'error' not in c and c.get('build_volume'))}\n")
    print("# ---- verified catalog YAML (paste into config/default.yaml under printers:) ----")
    for key, c in verified.items():
        print(_emit_yaml(key, c))
    # TEST-103 (audit-team-b4): write a proof-of-record so the catalog-freshness hygiene test
    # (tests/test_printer_catalog.py::test_catalog_was_reverified_after_its_last_edit) can assert
    # the all-printer slice proof is newer than the catalog YAML. Real slices back this record —
    # verify_slices only reaches here after live-slicing every kept printer. Records the catalog
    # hash too, so a later edit that changes the printers block is detectable beyond mtime.
    import hashlib
    import json as _json
    from datetime import datetime, timezone

    rec_path = Path(__file__).resolve().parent.parent / "config" / "printer_catalog.verified.json"
    catalog_blob = _json.dumps(cfg.raw.get("printers", {}), sort_keys=True).encode("utf-8")
    rec_path.write_text(
        _json.dumps(
            {
                "verified_at": datetime.now(timezone.utc).isoformat(),
                "catalog_sha256": hashlib.sha256(catalog_blob).hexdigest(),
                "slice_proven_printers": sorted(verified),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"# wrote proof-of-record -> {rec_path}")
    return verified


def main(argv: Iterable[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--keys", action="store_true", help="print resolved keys + a readiness summary only")
    ap.add_argument("--verify", action="store_true", help="live-slice each candidate (PLA) to prove it")
    args = ap.parse_args(list(argv) if argv is not None else None)
    cands = resolve_candidates()
    if args.verify:
        verify_slices(cands)
        return 0
    ready = sum(1 for c in cands.values() if c.get("build_volume") and c.get("process") and c.get("filaments", {}).get("pla"))
    if args.keys:
        for key, c in cands.items():
            if "error" in c:
                print(f"  MISS {key:26} {c['error']}")
            else:
                fl = "".join(m[0].upper() if m in c["filaments"] else "-" for m in ("pla", "petg", "tpu", "abs"))
                print(f"  {'OK  ' if c.get('process') and c['filaments'].get('pla') else '??  '}{key:26}"
                      f" {str(c['build_volume']):16} proc={'Y' if c['process'] else '-'} fil[{fl}] <- {c['machine']}")
    else:
        for key, c in cands.items():
            print(_emit_yaml(key, c))
    print(f"\n# catalog-ready (vol+process+PLA): {ready}/{len(cands)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
