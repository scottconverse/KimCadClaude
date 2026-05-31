"""Reconcile a configured printer against a connector's reported capabilities (Stage 2).

A printer's physical fields (build volume, nozzle diameter) can be left blank in config and
filled from what the printer actually reports — and where config DID set a value, this checks
it against the printer's ground truth and flags any mismatch. That second part is the direct
lesson from the Elegoo miss: a config value is only trustworthy if something backs it.

:func:`reconcile` is a pure function — it queries nothing itself; the caller passes the
:class:`~kimcad.printer_connector.PrinterCapabilities` it got from a connector.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from enum import Enum

from kimcad.config import Printer
from kimcad.printer_connector import PrinterCapabilities

_BV_TOL_MM = 1.0  # build-volume axes within 1 mm are "matching"
_NOZZLE_TOL_MM = 0.001


class NoteKind(str, Enum):
    filled = "filled"  # config was blank; filled from the printer
    matches = "matches"  # config matches what the printer reports
    mismatch = "mismatch"  # config disagrees with the printer (config kept, flagged)
    unknown = "unknown"  # neither config nor the printer provides the value


@dataclass(frozen=True)
class ReconcileNote:
    field: str  # "build_volume" | "nozzle_diameter"
    kind: NoteKind
    message: str


@dataclass(frozen=True)
class ReconcileResult:
    """The effective printer (blanks filled from capabilities) plus per-field notes.
    A *mismatch* keeps the configured value (config is authoritative) but flags it."""

    printer: Printer
    notes: tuple[ReconcileNote, ...]

    @property
    def has_mismatch(self) -> bool:
        return any(n.kind is NoteKind.mismatch for n in self.notes)

    def note_for(self, field: str) -> ReconcileNote | None:
        return next((n for n in self.notes if n.field == field), None)


def _bv_close(a: tuple[float, float, float], b: tuple[float, float, float]) -> bool:
    return all(abs(x - y) <= _BV_TOL_MM for x, y in zip(a, b))


def reconcile(printer: Printer, caps: PrinterCapabilities) -> ReconcileResult:
    """Merge ``caps`` into ``printer``: fill blank fields, verify set ones, collect notes."""
    notes: list[ReconcileNote] = []

    build_volume = printer.build_volume
    reported_bv = caps.build_volume_mm
    if reported_bv is not None:
        if build_volume is None:
            build_volume = reported_bv
            notes.append(
                ReconcileNote(
                    "build_volume", NoteKind.filled,
                    f"Filled build volume from {caps.name}: "
                    f"{reported_bv[0]:.0f} × {reported_bv[1]:.0f} × {reported_bv[2]:.0f} mm.",
                )
            )
        elif _bv_close(build_volume, reported_bv):
            notes.append(
                ReconcileNote(
                    "build_volume", NoteKind.matches,
                    f"Build volume matches the printer (config "
                    f"{tuple(round(v) for v in build_volume)} ≈ reported "
                    f"{tuple(round(v) for v in reported_bv)} mm).",
                )
            )
        else:
            notes.append(
                ReconcileNote(
                    "build_volume", NoteKind.mismatch,
                    f"Configured build volume {tuple(round(v) for v in build_volume)} mm "
                    f"disagrees with the printer's reported "
                    f"{tuple(round(v) for v in reported_bv)} mm — verify against the real machine.",
                )
            )
    elif build_volume is None:
        notes.append(
            ReconcileNote(
                "build_volume", NoteKind.unknown,
                "Build volume is neither configured nor reported by the printer.",
            )
        )

    nozzle = printer.nozzle_diameter
    reported_nozzle = caps.nozzle_diameter_mm
    if reported_nozzle is not None:
        if nozzle is None:
            nozzle = reported_nozzle
            notes.append(
                ReconcileNote(
                    "nozzle_diameter", NoteKind.filled,
                    f"Filled nozzle diameter from {caps.name}: {reported_nozzle:.2f} mm.",
                )
            )
        elif abs(nozzle - reported_nozzle) <= _NOZZLE_TOL_MM:
            notes.append(
                ReconcileNote(
                    "nozzle_diameter", NoteKind.matches,
                    f"Nozzle diameter matches the printer ({nozzle:.2f} mm).",
                )
            )
        else:
            notes.append(
                ReconcileNote(
                    "nozzle_diameter", NoteKind.mismatch,
                    f"Configured nozzle {nozzle:.2f} mm disagrees with the printer's reported "
                    f"{reported_nozzle:.2f} mm — verify against the real machine.",
                )
            )
    elif nozzle is None:
        notes.append(
            ReconcileNote(
                "nozzle_diameter", NoteKind.unknown,
                "Nozzle diameter is neither configured nor reported by the printer.",
            )
        )

    effective = dataclasses.replace(printer, build_volume=build_volume, nozzle_diameter=nozzle)
    return ReconcileResult(printer=effective, notes=tuple(notes))
