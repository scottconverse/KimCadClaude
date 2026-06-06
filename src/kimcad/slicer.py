"""OrcaSlicer CLI integration (spec §6.9, §12).

OrcaSlicer is bundled and invoked as a subprocess to turn a validated mesh into a
sliced, G-code-bearing 3MF:

    orca-slicer --slice 1 \\
        --load-settings "machine.json;process.json" \\
        --load-filaments "filament.json" \\
        --allow-newer-file \\
        --export-3mf out.gcode.3mf  input.3mf

G-code is only ever produced after explicit printer confirmation — that gate lives
in the orchestrator (``Pipeline.run(confirm_print=...)``), not here.

PROFILE RESOLUTION (verified against the pinned shipped build): OrcaSlicer's CLI
``--load-settings`` / ``--load-filaments`` take *file paths* to profile JSON, while
the config references profiles by *name* (e.g. "Bambu Lab P2S 0.4 nozzle"). The
shipped build keeps those JSONs under ``<binary_dir>/resources/profiles/<Vendor>/
{machine,filament,process}/<name>.json``. :func:`resolve_slice_settings` maps a
configured :class:`~kimcad.config.Printer` + :class:`~kimcad.config.Material` to the
three on-disk JSONs :func:`slice_model` needs. The printer's per-material filament map is
the sole source of truth: a material with no entry is "not available" on that printer
(no cross-vendor generic fallback that could mis-slice on the wrong machine).
"""

from __future__ import annotations

import io
import re
import subprocess
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kimcad.config import Material, Printer

# A real motion line: G0/G1 (linear) or G2/G3 (arc), case-insensitive, with a word
# boundary so G10/G28/G92 etc. are not mistaken for moves.
_MOTION_RE = re.compile(r"^\s*G[0-3]\b", re.IGNORECASE)

# Estimate comment lines OrcaSlicer writes into the embedded G-code header/footer. The
# wording varies by vendor profile: Bambu writes "total estimated time:"; Elegoo (and
# upstream PrusaSlicer-derived profiles) write "estimated printing time (normal mode) =".
_EST_TIME_RE = re.compile(r"total estimated time:\s*(.+?)\s*(?:;|$)", re.IGNORECASE)
_EST_TIME_FALLBACK_RE = re.compile(
    r"(?:model printing time:|estimated printing time \(normal mode\)\s*=)\s*(.+?)\s*(?:;|$)",
    re.IGNORECASE,
)
_FIL_MM_RE = re.compile(r"filament used \[mm\]\s*=\s*([0-9.]+)", re.IGNORECASE)
_FIL_CM3_RE = re.compile(r"filament used \[cm3\]\s*=\s*([0-9.]+)", re.IGNORECASE)
# Filament *weight*. The slicer computes this from the chosen filament profile's real density,
# so it's the honest source for a "this print weighs ~X g" readout (no density guessing in KimCad).
# Wording varies: PrusaSlicer-derived profiles (incl. Elegoo) write "filament used [g] = N";
# Bambu writes "total filament weight [g] : N". Match either spelling.
_FIL_G_RE = re.compile(
    r"(?:filament used \[g\]\s*=|total filament weight \[g\]\s*:)\s*([0-9.]+)", re.IGNORECASE
)
_LAYERS_RE = re.compile(r"total layer number:\s*([0-9]+)", re.IGNORECASE)


class SliceError(Exception):
    """Base class for slicing failures."""


class OrcaProfileError(SliceError):
    """A configured OrcaSlicer profile name could not be resolved to a file on disk,
    or the printer lacks a profile required to slice (e.g. no process profile)."""


class SliceTimeout(SliceError):
    """OrcaSlicer exceeded the allotted wall-clock time."""


class SliceFailed(SliceError):
    """OrcaSlicer exited non-zero or produced no output."""

    def __init__(self, returncode: int, stderr: str):
        self.returncode = returncode
        self.stderr = stderr
        # QA-003: a Windows native exit code comes back unsigned (e.g. 4294967246); show its
        # signed value (-50) so the message reads sanely, and when the process left no stderr,
        # give a plain-English hint instead of a bare dangling colon.
        signed = returncode - 2**32 if returncode is not None and returncode > 2**31 else returncode
        detail = stderr.strip()[:500]
        if not detail:
            detail = (
                "no slicer output — the part may be too large or too solid for this "
                "printer/profile; try a smaller or thinner-walled part."
            )
        super().__init__(f"orca-slicer exited {signed}: {detail}")


class GcodeProofFailed(SliceFailed):
    """A slice wrote a file, but it carries no usable, motion-bearing G-code toolpath.

    Distinct from a slicer *process* failure: the slicer may have exited 0 (or never
    run at all), so the misleading "orca-slicer exited 0" framing of :class:`SliceFailed`
    is suppressed here in favor of the plain proof reason. Still a ``SliceFailed`` so
    existing ``except SliceFailed`` handlers keep working.
    """

    def __init__(self, message: str):
        SliceError.__init__(self, message)  # plain message; no "exited N" template
        self.returncode = None
        self.stderr = message


# Proof bounds (ENG-002): a sliced 3MF is the slicer's own output, but a pathological or
# zip-bomb archive must not be able to pin a core / exhaust memory during the proof. NOTE
# (ENG-004): this caps members for the zip-bomb guard, but the send path
# (`extract_single_plate_gcode`) accepts a SINGLE plate only — KimCad produces single-plate
# slices today, so a >1-plate archive would prove OK yet be refused at send. Keep the two
# layers aligned: if multi-plate slicing ever ships, teach the connectors to upload N files.
_MAX_GCODE_MEMBERS = 64
# ENG-002: a real 3MF has a handful of members; cap the TOTAL entry count before we even iterate the
# namelist, so a crafted archive with millions of (non-gcode) entries can't pin a core just being
# enumerated/filtered (the .gcode-subset cap below only kicks in after the full namelist walk).
_MAX_ZIP_ENTRIES = 4096
MAX_GCODE_MEMBER_BYTES = 512 * 1024 * 1024  # 512 MB uncompressed per .gcode member


@dataclass(frozen=True)
class SliceSettings:
    """Resolved on-disk profile JSONs for one slice job."""

    machine: Path
    process: Path
    filament: Path


@dataclass(frozen=True)
class GcodeProof:
    """Evidence that a sliced 3MF actually contains printable toolpaths, not just that
    a file was written, plus the slicer's own print estimate. ``entries`` are the
    in-archive ``.gcode`` member names."""

    entries: tuple[str, ...]
    line_count: int
    has_motion: bool
    # Slicer estimate parsed from the G-code header (None if the slicer didn't emit it).
    estimated_time: str | None = None
    layer_count: int | None = None
    filament_mm: float | None = None
    filament_cm3: float | None = None
    filament_g: float | None = None

    def estimate_summary(self) -> str:
        parts = []
        if self.estimated_time:
            parts.append(f"~{self.estimated_time}")
        if self.layer_count is not None:
            parts.append(f"{self.layer_count} layers")
        if self.filament_g is not None:
            parts.append(f"{self.filament_g:.1f} g filament")
        elif self.filament_cm3 is not None:
            parts.append(f"{self.filament_cm3:.2f} cm3 filament")
        elif self.filament_mm is not None:
            parts.append(f"{self.filament_mm:.0f} mm filament")
        return ", ".join(parts)

    def estimate_detail(self) -> dict[str, Any]:
        """The parsed estimate as structured fields, for a UI to lay out as a labeled
        breakout (time / layers / filament length / filament weight) rather than one blob.
        Every value may be None when the slicer's profile didn't emit that line."""
        return {
            "time": self.estimated_time,
            "layers": self.layer_count,
            "filament_mm": self.filament_mm,
            "filament_cm3": self.filament_cm3,
            "filament_g": self.filament_g,
        }


@dataclass
class SliceResult:
    gcode_path: Path
    stdout: str
    stderr: str
    duration_s: float
    gcode_proof: GcodeProof | None = None
    settings: SliceSettings | None = None


def slice_model(
    input_mesh: Path,
    *,
    binary: Path,
    out_dir: Path,
    settings: SliceSettings,
    basename: str = "part",
    timeout_s: int = 600,  # ENG-005: match the production/configured budget (was a dead 300 default)
    allow_newer: bool = True,
) -> SliceResult:
    """Slice ``input_mesh`` into a G-code-bearing 3MF in ``out_dir``.

    Raises :class:`SliceTimeout` or :class:`SliceFailed`. The caller is responsible
    for having obtained explicit printer confirmation before calling this.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    gcode_path = out_dir / f"{basename}.gcode.3mf"

    cmd = [
        str(binary),
        "--slice",
        "1",
        "--load-settings",
        f"{settings.machine};{settings.process}",
        "--load-filaments",
        str(settings.filament),
    ]
    if allow_newer:
        cmd.append("--allow-newer-file")
    cmd += ["--export-3mf", str(gcode_path), str(input_mesh)]

    started = time.monotonic()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired as e:
        raise SliceTimeout(f"orca-slicer exceeded {timeout_s}s") from e
    duration = time.monotonic() - started

    if proc.returncode != 0:
        # QA-504: OrcaSlicer logs an off-bed / can't-arrange failure to STDOUT (not stderr), so a
        # bare exit code otherwise falls through to the generic "too large or too solid" message
        # that contradicts a green "fits the build plate" gate. Detect the arrange signature and
        # give an honest, specific reason: the footprint exceeds the slicer's USABLE plate area
        # (auto-arrange reserves edge clearance, so it's smaller than the nominal bed).
        blob = f"{proc.stdout}\n{proc.stderr}"
        if any(
            s in blob
            for s in (
                "can not be arranged inside plate",
                "no object is fully inside the print volume",
                "Nothing to be sliced",
            )
        ):
            raise SliceFailed(
                proc.returncode,
                "the part's footprint is too large to fit the printer's usable plate area "
                "(the slicer reserves clearance around the bed edges) — reduce the width/depth.",
            )
        raise SliceFailed(proc.returncode, proc.stderr)
    if not gcode_path.exists():
        raise SliceFailed(proc.returncode, f"expected {gcode_path.name} was not written")

    # A zero exit + a written file is not proof of a usable slice: confirm the 3MF
    # really carries motion-bearing G-code before we hand it back as a print job.
    proof = prove_gcode_3mf(gcode_path)

    return SliceResult(
        gcode_path=gcode_path,
        stdout=proc.stdout,
        stderr=proc.stderr,
        duration_s=duration,
        gcode_proof=proof,
        settings=settings,
    )


def prove_gcode_3mf(path: Path) -> GcodeProof:
    """Verify that a sliced ``*.gcode.3mf`` contains real, motion-bearing toolpaths.

    OrcaSlicer embeds the per-plate G-code inside the 3MF (a zip) as
    ``Metadata/plate_*.gcode``. A zero exit code and a written file do not guarantee a
    usable slice — an empty or motion-free G-code stream would still print nothing — so
    this opens the archive, requires at least one ``.gcode`` member, and requires at
    least one G0/G1/G2/G3 move across those members.

    Raises :class:`GcodeProofFailed` if the file is not a zip, carries no G-code member,
    or the G-code has no motion command. Defensive bounds reject a pathological archive
    (too many members, or a member whose uncompressed size exceeds ``MAX_GCODE_MEMBER_BYTES``)
    so a malformed/zip-bomb 3MF can't pin a core during the proof.
    """
    if not zipfile.is_zipfile(path):
        raise GcodeProofFailed(f"{path.name} is not a valid 3MF (zip) container")
    with zipfile.ZipFile(path) as zf:
        all_names = zf.namelist()
        if len(all_names) > _MAX_ZIP_ENTRIES:  # ENG-002: bound the whole archive before filtering
            raise GcodeProofFailed(
                f"{path.name} has an implausible number of archive entries ({len(all_names)})"
            )
        entries = tuple(n for n in all_names if n.lower().endswith(".gcode"))
        if not entries:
            raise GcodeProofFailed(f"{path.name} contains no .gcode toolpath member")
        if len(entries) > _MAX_GCODE_MEMBERS:
            raise GcodeProofFailed(
                f"{path.name} has an implausible number of G-code members ({len(entries)})"
            )
        line_count = 0
        has_motion = False
        est: dict[str, Any] = {}
        # Stream each member line-by-line rather than reading whole G-code files into
        # memory — a real part's toolpath can be tens of MB, and the target box is
        # memory-constrained (32 GB, shared with the local model). Estimate fields are
        # only scanned on comment lines, and only until found, so the hot motion path is
        # untouched. G-code is ASCII; errors="replace" keeps the motion scan robust (a
        # replaced byte can't forge a G0-3 match) and only risks cosmetic mangling of a
        # localized estimate string.
        for name in entries:
            # Cheap pre-check on the zip-declared size, then a real bound on bytes actually
            # read — the declared file_size is forgeable, so the streaming loop below is the
            # authoritative cap against a crafted/zip-bomb member (RE-ENG-001).
            if zf.getinfo(name).file_size > MAX_GCODE_MEMBER_BYTES:
                raise GcodeProofFailed(
                    f"{path.name} member {name!r} is too large to proof "
                    f"({zf.getinfo(name).file_size} bytes)"
                )
            member_chars = 0
            with zf.open(name) as raw:
                for line in io.TextIOWrapper(raw, encoding="utf-8", errors="replace"):
                    member_chars += len(line)
                    if member_chars > MAX_GCODE_MEMBER_BYTES:
                        raise GcodeProofFailed(
                            f"{path.name} member {name!r} exceeds the {MAX_GCODE_MEMBER_BYTES}-byte "
                            "proof cap (decompressed)"
                        )
                    line_count += 1
                    if not has_motion and _MOTION_RE.match(line):
                        has_motion = True
                    elif line.lstrip().startswith(";"):
                        _scan_estimate(line, est)
    if not has_motion:
        raise GcodeProofFailed(f"{path.name} G-code has no motion (G0/G1/G2/G3) commands")
    return GcodeProof(
        entries=entries,
        line_count=line_count,
        has_motion=has_motion,
        estimated_time=est.get("time"),
        layer_count=est.get("layers"),
        filament_mm=est.get("fil_mm"),
        filament_cm3=est.get("fil_cm3"),
        filament_g=est.get("fil_g"),
    )


def _scan_estimate(line: str, est: dict[str, Any]) -> None:
    """Pull print-estimate fields from a G-code comment line into ``est`` (in place).
    Each field is captured once; later duplicates are ignored."""
    if "time" not in est:
        m = _EST_TIME_RE.search(line) or _EST_TIME_FALLBACK_RE.search(line)
        if m:
            est["time"] = m.group(1).strip()
    if "layers" not in est:
        m = _LAYERS_RE.search(line)
        if m:
            est["layers"] = int(m.group(1))
    if "fil_mm" not in est:
        m = _FIL_MM_RE.search(line)
        if m:
            est["fil_mm"] = float(m.group(1))
    if "fil_cm3" not in est:
        m = _FIL_CM3_RE.search(line)
        if m:
            est["fil_cm3"] = float(m.group(1))
    if "fil_g" not in est:
        m = _FIL_G_RE.search(line)
        if m:
            est["fil_g"] = float(m.group(1))


# --- profile name -> on-disk JSON resolution ----------------------------------


def _find_profile_json(root: Path, kind: str, name: str) -> Path:
    """Locate ``<name>.json`` of a given ``kind`` ('machine' | 'process' | 'filament')
    under ``root``. The shipped layout nests profiles as
    ``<root>/<Vendor>/<kind>/.../<name>.json``, so a match must have ``kind`` as the
    component immediately below the vendor (``rel.parts[1]``). Matching the exact
    position — rather than "kind appears anywhere in the path" — avoids mis-resolving
    a name that lives under a subdirectory that merely happens to share a kind's name.

    Raises :class:`OrcaProfileError` if no such file exists, OR if the name resolves to
    more than one file (e.g. the same profile name shipped under two vendor subtrees):
    silently taking the first sorted match could slice with the wrong-vendor profile —
    plausible-looking but wrong G-code — so ambiguity fails loud and the config must
    disambiguate. For the shipped tree every configured name is unique.
    """
    # Profile names contain spaces, '@', and parens but never glob metacharacters
    # ('*', '?', '['), so the name can be used in the glob pattern verbatim.
    matches = sorted(
        p
        for p in root.glob(f"**/{name}.json")
        if len(rel := p.relative_to(root).parts) >= 2 and rel[1] == kind
    )
    if not matches:
        raise OrcaProfileError(
            f"no {kind} profile named {name!r} found under {root}"
        )
    if len(matches) > 1:
        where = ", ".join(str(m.relative_to(root)) for m in matches)
        raise OrcaProfileError(
            f"ambiguous {kind} profile {name!r}: {len(matches)} matches under {root} "
            f"({where}); disambiguate the configured profile name"
        )
    return matches[0]


def resolve_slice_settings(
    profiles_root: Path, printer: Printer, material: Material
) -> SliceSettings:
    """Resolve a printer + material into the three on-disk profile JSONs OrcaSlicer
    needs, using the configured profile names and the shipped ``resources/profiles``
    tree at ``profiles_root``.

    Raises :class:`OrcaProfileError` when the printer is missing a machine or process
    profile, or when any configured name does not resolve to a file.
    """
    if not printer.orca_machine_profile:
        raise OrcaProfileError(
            f"printer {printer.key!r} ({printer.name}) has no OrcaSlicer machine "
            "profile configured"
        )
    if not printer.orca_process_profile:
        raise OrcaProfileError(
            f"printer {printer.key!r} ({printer.name}) has no OrcaSlicer process "
            "profile configured — slicing is not wired for this printer yet"
        )
    # The per-printer map is the sole source of truth: a material a printer can't print
    # (no compatible, verified filament profile) is honestly "not available" rather than
    # silently mapped to an incompatible vendor-neutral generic (which would slice plausible
    # but wrong G-code on the wrong machine). Each configured name is verified to live-slice.
    filament_name = printer.orca_filament_profiles.get(material.key)
    if not filament_name:
        raise OrcaProfileError(
            f"material {material.key!r} is not available on printer {printer.name!r} "
            f"({printer.key!r}): no filament profile is configured for it on this printer"
        )
    return SliceSettings(
        machine=_find_profile_json(profiles_root, "machine", printer.orca_machine_profile),
        process=_find_profile_json(profiles_root, "process", printer.orca_process_profile),
        filament=_find_profile_json(profiles_root, "filament", filament_name),
    )
