"""Stage 7 — the Smart Mesh learning store (spec §6.12).

Smart Mesh's *history* layer: a local-first record of the parts this install has built, used to add
an honest "compared to your past prints" line to the readiness card. The store is plain local JSON
and entirely **best-effort** — a missing or corrupt file degrades to *no* history (the card simply
omits the comparison), and a write failure never breaks a build. Nothing ever leaves the machine.

The comparison is deliberately **factual, not flattering**: it states how this part's readiness
score ranks against prior prints ("Stronger than 7 of your 9 past prints"), and only claims a
personal best when the score strictly beats every prior one. With no prior history it returns
``None`` — the card shows nothing rather than inventing a baseline.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

# Keep the store bounded; once it passes this, the oldest records are dropped on the next write.
_MAX_RECORDS = 500
# Need at least this many same-type prints before narrowing the comparison to that type; otherwise
# compare against all prints (and say so), so a brand-new type isn't judged against one prior.
_MIN_SAME_TYPE = 3


@dataclass(frozen=True)
class PrintRecord:
    """One built part, as remembered for the learning comparison. Coarse on purpose — a readiness
    score, the gate verdict, the material, and the largest dimension (a cheap "ambition" handle);
    no geometry, no prompt, nothing identifying."""

    object_type: str
    score: int  # the readiness score 0-100
    gate_status: str  # "pass" | "warn" | "fail"
    material: str
    max_dim_mm: float  # the largest bounding-box dimension — a coarse size handle
    created_at: str | None = None  # ISO-8601 if the caller stamps it; optional


def compare_phrase(object_type: str, score: int, prior: list[PrintRecord]) -> str | None:
    """A factual one-liner ranking ``score`` against ``prior`` parts, or ``None`` with no history.
    Pure — no I/O — so it's fully unit-tested. Narrows to same-type parts once there are enough of
    them, else compares against all parts and names that scope honestly. The wording never
    overstates: "a personal best" needs a strict beat of every prior, "below all" needs every
    prior strictly higher, and a part that only *ties* its predecessors reads "on par" — not
    "below". "Parts" (not "prints") because the store holds designed parts, some gate-failed and
    none necessarily printed."""
    if not prior:
        return None
    same = [r for r in prior if r.object_type == object_type]
    if len(same) >= _MIN_SAME_TYPE:
        pool, scope = same, f"{object_type} parts"
    else:
        pool, scope = prior, "parts"
    scores = [r.score for r in pool]
    n = len(scores)
    ahead = sum(1 for s in scores if s < score)  # priors this part strictly beats
    behind = sum(1 for s in scores if s > score)  # priors that strictly beat this part
    if ahead == n:  # beats every prior
        return f"A personal best — ahead of all {n} of your past {scope}."
    if behind == n:  # every prior is strictly higher
        return f"Below all {n} of your past {scope} — worth a closer look before printing."
    if ahead == 0:  # beats none, but ties at least one (not strictly below all)
        return f"On par with your {n} past {scope}."
    return f"Stronger than {ahead} of your {n} past {scope}."


class HistoryStore:
    """A local JSON record of built parts. All methods are best-effort and never raise."""

    def __init__(self, path: Path):
        self.path = path

    def load(self) -> list[PrintRecord]:
        """Read the store, skipping any malformed record. Returns ``[]`` when the file is absent,
        unreadable, not a JSON list, or empty — never raises."""
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        if not isinstance(raw, list):
            return []
        out: list[PrintRecord] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            try:
                out.append(
                    PrintRecord(
                        object_type=str(item["object_type"]),
                        score=int(item["score"]),
                        gate_status=str(item.get("gate_status", "")),
                        material=str(item.get("material", "")),
                        max_dim_mm=float(item.get("max_dim_mm", 0.0)),
                        created_at=item.get("created_at"),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue  # one bad record doesn't poison the rest
        return out

    def record(self, rec: PrintRecord) -> None:
        """Append ``rec`` and persist (keeping the most recent ``_MAX_RECORDS``). Best-effort: a
        read/write/serialize failure is swallowed so a logging miss never breaks a build."""
        try:
            existing = self.load()
            existing.append(rec)
            existing = existing[-_MAX_RECORDS:]
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps([asdict(r) for r in existing], indent=2), encoding="utf-8"
            )
        except OSError:
            return  # best-effort persistence

    def comparison(self, *, object_type: str, score: int) -> str | None:
        """The factual comparison line for a part of ``object_type`` scoring ``score`` against the
        PRIOR records in the store, or ``None`` when there's no prior history."""
        return compare_phrase(object_type, score, self.load())
