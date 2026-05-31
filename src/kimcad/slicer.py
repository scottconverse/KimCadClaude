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
three on-disk JSONs :func:`slice_model` needs, falling back to the generic
``Generic <MATERIAL>`` filament when a printer has no material-specific entry.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from kimcad.config import Material, Printer


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
        super().__init__(f"orca-slicer exited {returncode}: {stderr.strip()[:500]}")


@dataclass(frozen=True)
class SliceSettings:
    """Resolved on-disk profile JSONs for one slice job."""

    machine: Path
    process: Path
    filament: Path


@dataclass
class SliceResult:
    gcode_path: Path
    stdout: str
    stderr: str
    duration_s: float


def slice_model(
    input_mesh: Path,
    *,
    binary: Path,
    out_dir: Path,
    settings: SliceSettings,
    basename: str = "part",
    timeout_s: int = 300,
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
        raise SliceFailed(proc.returncode, proc.stderr)
    if not gcode_path.exists():
        raise SliceFailed(proc.returncode, f"expected {gcode_path.name} was not written")

    return SliceResult(
        gcode_path=gcode_path,
        stdout=proc.stdout,
        stderr=proc.stderr,
        duration_s=duration,
    )


# --- profile name -> on-disk JSON resolution ----------------------------------

# Materials with no printer-specific filament entry fall back to the shipped
# vendor-neutral generic for that material. Keys match config material keys.
_GENERIC_FILAMENT = {
    "pla": "Generic PLA",
    "petg": "Generic PETG",
    "tpu": "Generic TPU",
    "abs": "Generic ABS",
}


def _find_profile_json(root: Path, kind: str, name: str) -> Path:
    """Locate ``<name>.json`` of a given ``kind`` ('machine' | 'process' | 'filament')
    under ``root``. The shipped layout nests profiles as
    ``<root>/<Vendor>/<kind>/.../<name>.json``, so a match must have ``kind`` as the
    component immediately below the vendor (``rel.parts[1]``). Matching the exact
    position — rather than "kind appears anywhere in the path" — avoids mis-resolving
    a name that lives under a subdirectory that merely happens to share a kind's name.

    Raises :class:`OrcaProfileError` if no such file exists.
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
    filament_name = printer.orca_filament_profiles.get(material.key) or _GENERIC_FILAMENT.get(
        material.key
    )
    if not filament_name:
        raise OrcaProfileError(
            f"no filament profile configured for material {material.key!r} on printer "
            f"{printer.key!r}, and no generic fallback is known"
        )
    return SliceSettings(
        machine=_find_profile_json(profiles_root, "machine", printer.orca_machine_profile),
        process=_find_profile_json(profiles_root, "process", printer.orca_process_profile),
        filament=_find_profile_json(profiles_root, "filament", filament_name),
    )
