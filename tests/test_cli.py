import io

import kimcad.cli as cli
from kimcad.cli import _force_utf8_output, _normalize_argv, build_parser, main

from conftest import BAMBU, PLA, FakeProvider
from conftest import box_renderer, make_plan


def test_normalize_bare_prompt_becomes_design():
    assert _normalize_argv(["a 20mm block"]) == ["design", "a 20mm block"]


def test_normalize_leaves_subcommands_alone():
    assert _normalize_argv(["design", "x"]) == ["design", "x"]
    assert _normalize_argv(["bench"]) == ["bench"]
    assert _normalize_argv(["--help"]) == ["--help"]


def test_normalize_guards_against_typod_subcommand():
    # QA-004: a single bare word that's a near-miss of a subcommand is left as-is so
    # argparse rejects it with the valid choices — not silently run as a design prompt.
    assert _normalize_argv(["benhc"]) == ["benhc"]  # ~ bench
    assert _normalize_argv(["wbe"]) == ["wbe"]  # ~ web
    assert _normalize_argv(["desgin"]) == ["desgin"]  # ~ design
    # a genuine one-word prompt that isn't close to any subcommand still routes to design
    assert _normalize_argv(["hook"]) == ["design", "hook"]


def test_typod_subcommand_exits_2_not_a_long_run():
    import pytest

    with pytest.raises(SystemExit) as exc:
        main(["benhc"])
    assert exc.value.code == 2  # argparse invalid-choice exit, no pipeline run


def test_parser_design_requires_prompt():
    parser = build_parser()
    args = parser.parse_args(["design", "a block"])
    assert args.command == "design"
    assert args.prompt == "a block"


def test_bench_missing_prompts_file_is_graceful(tmp_path, capsys):
    code = main(["bench", "--prompts", str(tmp_path / "nope.yaml")])
    assert code == 2
    assert "No benchmark prompts" in capsys.readouterr().out


def test_design_missing_backend_key_is_graceful(monkeypatch, capsys):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    code = main(["design", "a block", "--backend", "cloud_deepseek"])
    assert code == 2
    assert "Error" in capsys.readouterr().err


def test_force_utf8_output_prevents_glyph_crash():
    # On a cp1252 stream, report glyphs (×, ³, °) and the >= verdict would crash;
    # after reconfigure they must pass through as UTF-8 bytes.
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding="cp1252")
    _force_utf8_output(stream)
    print("verdict >= 80%: 20.0 × 20.0 × 20.0 mm, 7576 mm³ @ 55°", file=stream)
    stream.flush()
    assert "×".encode() in raw.getvalue()


def test_force_utf8_output_tolerates_streams_without_reconfigure():
    # pytest's capture object and other wrapped streams lack reconfigure();
    # the helper must be a silent no-op rather than raising.
    class _NoReconfigure:
        pass

    _force_utf8_output(_NoReconfigure())  # must not raise


# --- TEST-002: design exit-code contract --------------------------------------
#
# main(["design", ...]) must map each PipelineStatus to a stable exit code:
#   completed -> 0, clarification_needed -> 3, render_failed -> 4, gate_failed -> 5.
# A fake provider + stub box renderer drive real geometry without an LLM or binary;
# cli._build_pipeline is monkeypatched to inject the fakes so main()'s own status->code
# wiring (and report-printing) is what's under test.


def _patch_pipeline(monkeypatch, provider, *, extents=(20, 20, 20), **pipeline_kw):
    from kimcad.config import Config
    from kimcad.pipeline import Pipeline

    renderer, _state = box_renderer(extents)

    def _fake_build(config, args):
        return Pipeline(Config.load(), BAMBU, PLA, provider, renderer=renderer, **pipeline_kw)

    monkeypatch.setattr(cli, "_build_pipeline", _fake_build)


def test_design_completed_exit_0_prints_report(monkeypatch, capsys, tmp_path):
    _patch_pipeline(monkeypatch, FakeProvider(make_plan([20, 20, 20])))
    code = main(["design", "a 20mm block", "--out", str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 0
    assert "Gate: PASS" in out  # the report was printed
    assert "Mesh:" in out  # and the mesh path line


def test_design_clarification_exit_3(monkeypatch, capsys, tmp_path):
    provider = FakeProvider(make_plan(None, open_questions=["What overall size?"]))
    _patch_pipeline(monkeypatch, provider)
    code = main(["design", "a block", "--out", str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 3
    assert "What overall size?" in out


def test_design_render_failed_exit_4_no_report_crash(monkeypatch, capsys, tmp_path):
    # Renderer always fails -> render_failed, which carries NO report; main()'s
    # `if result.report is not None` guard must hold and not crash.
    from kimcad.config import Config
    from kimcad.pipeline import Pipeline

    provider = FakeProvider(make_plan([20, 20, 20]))
    renderer, _state = box_renderer((20, 20, 20), fail_times=99)

    def _fake_build(config, args):
        return Pipeline(
            Config.load(), BAMBU, PLA, provider, renderer=renderer, max_render_retries=1
        )

    monkeypatch.setattr(cli, "_build_pipeline", _fake_build)
    code = main(["design", "a block", "--out", str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 4
    assert "Could not produce a valid model" in out


def test_design_gate_failed_exit_5_prints_report(monkeypatch, capsys, tmp_path):
    # Plan claims 50mm; render is 20mm -> dimensional mismatch FAIL -> gate_failed.
    provider = FakeProvider(make_plan([50, 50, 50]))
    _patch_pipeline(monkeypatch, provider)
    code = main(["design", "a block", "--out", str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 5
    assert "Gate: FAIL" in out  # report still printed for the user
    assert "Printability Gate FAILED" in out
