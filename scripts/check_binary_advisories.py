"""KC-5 (#10) — CVE/advisory status for the pinned third-party binaries.

``pip-audit`` (CI workflow) covers the Python dependency tree; this covers the BINARIES the
installer bundles: OpenSCAD and OrcaSlicer (PrintProof3D is first-party; Ollama is
installed/updated in user space by its own installer, not pinned by KimCad).

The check is a curated, reviewed table — not a live feed — so the gate stays offline and
deterministic. **The bump process** (documented here, referenced from CONTRIBUTING):

1. When changing a pin in ``scripts/fetch_tools.py``, search NVD + GitHub Security
   Advisories for the tool at the new version.
2. Record every advisory that exists for (or before) the pinned version in the table
   below, with an exposure assessment for HOW KIMCAD USES THE TOOL.
3. ``blocking=True`` for any advisory whose vulnerable surface KimCad actually exposes —
   the gate then fails until the pin is bumped or the exposure is closed.
4. Update ``reviewed`` to the review date. The gate fails when a pinned version has no
   review entry at all, so a silent bump can't skip the process.

Run: ``python scripts/check_binary_advisories.py`` (wired into scripts/ci.sh).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Advisory:
    id: str
    summary: str
    assessment: str  # how the vulnerable surface maps onto KimCad's actual use
    blocking: bool   # True => the gate fails until resolved


@dataclass(frozen=True)
class BinaryReview:
    name: str
    pinned_version: str  # must appear in fetch_tools.py's pin URL (drift detector)
    reviewed: str        # date of the last advisory review (YYYY-MM-DD)
    advisories: tuple[Advisory, ...] = field(default_factory=tuple)


REVIEWS: tuple[BinaryReview, ...] = (
    BinaryReview(
        name="OpenSCAD",
        pinned_version="2021.01",
        reviewed="2026-06-11",
        advisories=(
            Advisory(
                id="CVE-2022-0496",
                summary="Out-of-bounds memory access parsing a crafted STL import",
                assessment=(
                    "Not exposed: KimCad never feeds STL INTO OpenSCAD — OpenSCAD only "
                    "RENDERS .scad source (template-emitted or sanitizer-gated) to STL "
                    "output. The vulnerable import path is unreachable from any KimCad "
                    "surface. Re-assess if an import<stl> feature is ever added."
                ),
                blocking=False,
            ),
            Advisory(
                id="CVE-2022-0497",
                summary="Out-of-bounds read parsing a crafted STL import",
                assessment="Same import-path surface as CVE-2022-0496 — not reachable.",
                blocking=False,
            ),
        ),
    ),
    BinaryReview(
        name="OrcaSlicer",
        pinned_version="2.4.0-alpha",
        reviewed="2026-06-11",
        advisories=(),  # no published CVE/GHSA for the pinned version at review time
    ),
)


def _pin_urls() -> str:
    return (ROOT / "scripts" / "fetch_tools.py").read_text(encoding="utf-8")


def main() -> int:
    pins_src = _pin_urls()
    failures: list[str] = []
    print("[binary-advisories] curated CVE/advisory review of the pinned binaries:")
    for review in REVIEWS:
        # Drift detector: the reviewed version must still BE the pinned version.
        pattern = re.escape(review.pinned_version)
        if not re.search(pattern, pins_src, flags=re.IGNORECASE):
            failures.append(
                f"{review.name}: reviewed version {review.pinned_version!r} no longer "
                f"appears in fetch_tools.py — the pin changed without an advisory review "
                f"(see the bump process in this script's docstring)."
            )
            continue
        if not review.advisories:
            print(f"  {review.name} {review.pinned_version}: no known advisories "
                  f"(reviewed {review.reviewed})")
        for adv in review.advisories:
            status = "BLOCKING" if adv.blocking else "assessed: not exposed"
            print(f"  {review.name} {review.pinned_version}: {adv.id} — {status} "
                  f"(reviewed {review.reviewed})")
            if adv.blocking:
                failures.append(f"{review.name} {review.pinned_version}: {adv.id} — "
                                f"{adv.summary}. {adv.assessment}")
    if failures:
        print("\n[binary-advisories] FAIL:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("[binary-advisories] OK — every pinned binary reviewed; no blocking advisory.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
