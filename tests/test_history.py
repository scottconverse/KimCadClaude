"""Stage 7 Slice 5 — the Smart Mesh learning store.

The store is local JSON and best-effort; `compare_phrase` is pure. These cover the comparison
wording (factual, never flattering), same-type narrowing, the record/load round-trip, and every
degrade path (missing / corrupt / non-list / malformed-record / unwritable) — none of which may
raise, because a logging miss must never break a build.
"""

from __future__ import annotations

import json
from pathlib import Path

from kimcad.history import HistoryStore, PrintRecord, compare_phrase


def _rec(object_type: str, score: int, **kw) -> PrintRecord:
    return PrintRecord(
        object_type=object_type,
        score=score,
        gate_status=kw.get("gate_status", "pass"),
        material=kw.get("material", "PLA"),
        max_dim_mm=kw.get("max_dim_mm", 80.0),
        created_at=kw.get("created_at"),
    )


# --- compare_phrase: factual ranking --------------------------------------------------------

def test_compare_phrase_returns_none_with_no_history():
    assert compare_phrase("box", 90, []) is None


def test_compare_phrase_calls_out_a_personal_best_only_when_it_beats_all():
    prior = [_rec("box", 60), _rec("box", 70), _rec("box", 80)]
    phrase = compare_phrase("box", 95, prior)
    assert phrase is not None and "personal best" in phrase
    assert "all 3" in phrase
    # A tie with the best is NOT a personal best (it didn't beat it).
    tie = compare_phrase("box", 80, prior)
    assert "personal best" not in tie
    assert "Stronger than 2 of your 3" in tie


def test_compare_phrase_is_honest_about_a_low_score():
    prior = [_rec("box", 60), _rec("box", 70), _rec("box", 80)]
    phrase = compare_phrase("box", 40, prior)
    assert "Below all 3" in phrase
    assert "closer look" in phrase


def test_compare_phrase_says_on_par_when_it_ties_priors_without_beating_any():
    # SLICE5-001: a tie is NOT "below all" — building the same part again at the same score reads
    # "on par", never "below" (which would falsely tell the user it got worse).
    prior = [_rec("box", 92), _rec("box", 92), _rec("box", 92)]
    phrase = compare_phrase("box", 92, prior)
    assert "On par" in phrase
    assert "Below all" not in phrase
    assert "personal best" not in phrase


def test_compare_phrase_narrows_to_same_type_once_there_are_enough():
    prior = [
        _rec("box", 50), _rec("box", 55), _rec("box", 60),  # 3 boxes
        _rec("bracket", 99),  # a different type with a high score
    ]
    # 3 same-type parts -> compare against boxes only, and say so.
    phrase = compare_phrase("box", 90, prior)
    assert "box parts" in phrase
    assert "ahead of all 3 of your past box parts" in phrase  # the bracket isn't counted


def test_compare_phrase_falls_back_to_all_parts_when_too_few_same_type():
    prior = [_rec("box", 50), _rec("bracket", 60), _rec("bracket", 70)]  # only 1 box
    phrase = compare_phrase("box", 90, prior)
    assert "past parts" in phrase  # not "box parts"
    assert "all 3" in phrase  # compared against all 3 records


def test_compare_phrase_at_two_same_type_still_falls_back_to_all_parts():
    # TEST-S7-003: the boundary one below _MIN_SAME_TYPE (=3) — exactly 2 same-type parts must
    # still compare against ALL parts ("parts"), not narrow to "box parts" (guards the >= bound).
    prior = [_rec("box", 50), _rec("box", 60), _rec("bracket", 70)]  # 2 boxes (one below threshold)
    phrase = compare_phrase("box", 90, prior)
    assert "box parts" not in phrase
    assert "past parts" in phrase
    assert "all 3" in phrase  # ranked against all 3, not just the 2 boxes


# --- HistoryStore: round-trip + every degrade path ------------------------------------------

def test_record_and_load_round_trip(tmp_path):
    store = HistoryStore(tmp_path / "h.json")
    store.record(_rec("box", 88, created_at="2026-06-02T00:00:00+00:00"))
    store.record(_rec("bracket", 72))
    loaded = store.load()
    assert [r.object_type for r in loaded] == ["box", "bracket"]
    assert loaded[0].score == 88
    assert loaded[0].created_at == "2026-06-02T00:00:00+00:00"


def test_load_is_empty_when_the_file_is_absent():
    assert HistoryStore(Path("nope/does-not-exist.json")).load() == []


def test_load_degrades_on_corrupt_or_non_list_json(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert HistoryStore(bad).load() == []
    notlist = tmp_path / "obj.json"
    notlist.write_text(json.dumps({"object_type": "box"}), encoding="utf-8")
    assert HistoryStore(notlist).load() == []


def test_load_skips_a_malformed_record_but_keeps_the_rest(tmp_path):
    p = tmp_path / "mixed.json"
    p.write_text(
        json.dumps([
            {"object_type": "box", "score": 80, "gate_status": "pass"},
            {"object_type": "broken"},  # missing required 'score' -> skipped
            "not even a dict",  # skipped
            {"object_type": "tube", "score": 65, "gate_status": "warn"},
        ]),
        encoding="utf-8",
    )
    loaded = HistoryStore(p).load()
    assert [r.object_type for r in loaded] == ["box", "tube"]


def test_record_caps_at_the_max(tmp_path, monkeypatch):
    import kimcad.history as h

    monkeypatch.setattr(h, "_MAX_RECORDS", 3)
    store = HistoryStore(tmp_path / "cap.json")
    for i in range(6):
        store.record(_rec("box", 50 + i))
    loaded = store.load()
    assert len(loaded) == 3
    assert [r.score for r in loaded] == [53, 54, 55]  # the most recent 3


def test_record_is_best_effort_on_an_unwritable_path(tmp_path):
    # Parent is a FILE, so mkdir/write fail -> record must swallow, not raise.
    afile = tmp_path / "afile"
    afile.write_text("x", encoding="utf-8")
    store = HistoryStore(afile / "history.json")
    store.record(_rec("box", 90))  # must not raise
    assert store.load() == []


def test_record_is_thread_safe_under_concurrency(tmp_path):
    # ENG-701: the threaded web server can service designs on many threads at once. Without the
    # process-wide lock + atomic write, concurrent records race on the read-modify-write and lose
    # most of the store (reproduced: 40 writers collapsed to ~1). With the fix, all 40 survive.
    import threading

    store = HistoryStore(tmp_path / "concurrent.json")

    def worker(i: int) -> None:
        store.record(_rec("box", 50 + i))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(40)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(store.load()) == 40  # no record lost to a torn read-modify-write


def test_comparison_uses_prior_records(tmp_path):
    store = HistoryStore(tmp_path / "c.json")
    assert store.comparison(object_type="box", score=90) is None  # no history yet
    store.record(_rec("box", 60))
    store.record(_rec("box", 70))
    # Only 2 same-type parts (< the same-type threshold), so it compares against all parts.
    assert "Stronger than 1 of your 2 past parts" in store.comparison(object_type="box", score=65)
    assert "personal best" in store.comparison(object_type="box", score=95)  # beats both
