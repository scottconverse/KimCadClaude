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

KNOWN UNKNOWN (resolve during binary verification, task #2/#11): OrcaSlicer's CLI
``--load-settings`` takes *file paths* to exported profile JSON, while the config
references profiles by *name* (e.g. "Bambu Lab P2S 0.4 nozzle"). Whether the shipped
OrcaSlicer even ships a P2S profile, and where its built-in profile JSONs live on
disk, can only be confirmed against the real binary. :func:`slice_model` therefore
takes explicit JSON paths; mapping config profile names → those paths is a
verification step once the binary is in ``tools/``.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


class SliceError(Exception):
    """Base class for slicing failures."""


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
