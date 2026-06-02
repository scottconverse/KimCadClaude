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


# --- Stage 1 Slice 3a: --slice confirmation -----------------------------------


def test_parser_design_slice_flag_defaults_off():
    parser = build_parser()
    assert parser.parse_args(["design", "x"]).do_slice is False
    assert parser.parse_args(["design", "x", "--slice"]).do_slice is True


def test_design_slice_flag_confirms_and_reports(monkeypatch, capsys, tmp_path):
    """--slice is the explicit print confirmation: it announces the printer + material
    + resolved profiles up front, slices, and the report shows the proven G-code."""
    from pathlib import Path

    from kimcad.slicer import GcodeProof, SliceResult, SliceSettings

    def fake_slicer(mesh_path, out_dir, basename):
        gp = out_dir / f"{basename}.gcode.3mf"
        gp.write_bytes(b"PK\x03\x04")
        return SliceResult(
            gcode_path=gp,
            stdout="",
            stderr="",
            duration_s=0.1,
            gcode_proof=GcodeProof(
                entries=("Metadata/plate_1.gcode",), line_count=18000, has_motion=True,
                estimated_time="14m 45s", layer_count=100, filament_cm3=6.21,
            ),
            settings=SliceSettings(
                machine=Path("Bambu Lab P2S 0.4 nozzle.json"),
                process=Path("0.20mm Standard @BBL P2S.json"),
                filament=Path("Bambu PLA Basic @BBL P2S.json"),
            ),
        )

    _patch_pipeline(monkeypatch, FakeProvider(make_plan([20, 20, 20])), slicer=fake_slicer)
    code = main(["design", "a 20mm block", "--out", str(tmp_path), "--slice"])
    out = capsys.readouterr().out
    assert code == 0
    assert "slice for Bambu Lab P2S" in out  # up-front confirmation/intent line
    assert "G-code produced" in out
    assert "18000 G-code lines" in out
    assert "0.20mm Standard @BBL P2S" in out  # resolved process profile surfaced


def test_design_without_slice_flag_does_not_slice(monkeypatch, capsys, tmp_path):
    sliced = {"n": 0}

    def fake_slicer(mesh_path, out_dir, basename):
        sliced["n"] += 1
        return "x"

    _patch_pipeline(monkeypatch, FakeProvider(make_plan([20, 20, 20])), slicer=fake_slicer)
    code = main(["design", "a 20mm block", "--out", str(tmp_path)])
    assert code == 0
    assert sliced["n"] == 0  # no confirmation -> no G-code
    assert "G-code produced" not in capsys.readouterr().out


# --- Stage 2 Slice 4: --send -------------------------------------------------


def _real_gcode_slicer():
    """A fake slicer that writes a genuinely-proveable .gcode.3mf so a connector's send
    (which proves the file) accepts it."""
    import zipfile

    from kimcad.slicer import GcodeProof, SliceResult, SliceSettings

    def fake_slicer(mesh_path, out_dir, basename):
        from pathlib import Path

        gp = out_dir / f"{basename}.gcode.3mf"
        with zipfile.ZipFile(gp, "w") as zf:
            zf.writestr("3D/3dmodel.model", "<model/>")
            zf.writestr("Metadata/plate_1.gcode", "G28\nG1 X10 Y10 E1\nG1 X20 Y20 E2\n")
        return SliceResult(
            gcode_path=gp, stdout="", stderr="", duration_s=0.1,
            gcode_proof=GcodeProof(
                entries=("Metadata/plate_1.gcode",), line_count=3, has_motion=True
            ),
            settings=SliceSettings(
                machine=Path("m.json"), process=Path("p.json"), filament=Path("f.json")
            ),
        )

    return fake_slicer


def test_design_send_to_mock_connector(monkeypatch, capsys, tmp_path):
    """--send slices then sends to the named connector; 'mock' is the built-in loopback."""
    _patch_pipeline(
        monkeypatch, FakeProvider(make_plan([20, 20, 20])), slicer=_real_gcode_slicer()
    )
    code = main(["design", "a 20mm block", "--out", str(tmp_path), "--send", "mock"])
    out = capsys.readouterr().out
    assert code == 0
    assert "G-code produced" in out  # --send implied slicing
    # 'mock' is a simulation, so the copy must NOT claim a real print (UX-001).
    assert "Simulated send to mock" in out
    assert "mock-1 (queued)" in out
    assert "no real printer was used" in out.lower()
    assert "Printer:" in out


def test_gate_failed_part_is_never_sent(monkeypatch, capsys, tmp_path):
    """The stage's headline safety property: a part that FAILS the gate must not be sent,
    even with --send (the slicer is never invoked, the connector never built)."""
    sliced = {"n": 0}

    def counting_slicer(mesh_path, out_dir, basename):
        sliced["n"] += 1
        return "should-not-happen"

    # plan claims 50mm, render is 20mm -> dim mismatch -> gate FAIL
    _patch_pipeline(monkeypatch, FakeProvider(make_plan([50, 50, 50])), slicer=counting_slicer)
    code = main(["design", "a block", "--out", str(tmp_path), "--send", "mock"])
    out = capsys.readouterr().out
    assert code == 5
    assert sliced["n"] == 0
    assert "Sent to" not in out


def test_gate_failed_part_not_sent_even_with_proceed_anyway(monkeypatch, capsys, tmp_path):
    """ENG-201: --proceed-anyway lets a gate-FAILED part be sliced for export/inspection,
    but a part the printability gate rejected is never dispatched to a printer."""
    # plan claims 50mm, render is 20mm -> dim mismatch -> gate FAIL; the slicer still runs
    # under --proceed-anyway so the part can be exported.
    _patch_pipeline(monkeypatch, FakeProvider(make_plan([50, 50, 50])), slicer=_real_gcode_slicer())
    code = main(
        ["design", "a block", "--out", str(tmp_path), "--send", "mock", "--proceed-anyway"]
    )
    out = capsys.readouterr().out
    assert code == 0  # the run completes (the part was exported), but...
    assert "FAILED the printability gate" in out  # ...it is explicitly NOT sent
    assert "Sent to" not in out
    assert "Simulated send" not in out


def test_send_with_no_gcode_says_nothing_to_send(monkeypatch, capsys, tmp_path):
    # --send on a passing part whose slicer produced no real SliceResult -> nothing to send.
    def no_gcode_slicer(mesh_path, out_dir, basename):
        return "not-a-slice-result"

    _patch_pipeline(monkeypatch, FakeProvider(make_plan([20, 20, 20])), slicer=no_gcode_slicer)
    code = main(["design", "a 20mm block", "--out", str(tmp_path), "--send", "mock"])
    out = capsys.readouterr().out
    assert code == 0
    assert "Nothing to send to mock" in out
    assert "Sent to" not in out


def test_design_send_unknown_connector_fails_fast(capsys):
    # Validated before any pipeline run -> exit 2, no LLM/slicer invoked.
    code = main(["design", "a block", "--send", "no_such_connector"])
    out = capsys.readouterr().out
    assert code == 2
    assert "Unknown connector 'no_such_connector'" in out


def test_send_print_job_offline_falls_back_to_disk(capsys, tmp_path):
    # An offline OctoPrint connector reports cleanly and points at the on-disk G-code.
    import os
    import zipfile

    from kimcad.cli import _send_print_job
    from kimcad.config import Config

    g = tmp_path / "part.gcode.3mf"
    with zipfile.ZipFile(g, "w") as zf:
        zf.writestr("Metadata/plate_1.gcode", "G28\nG1 X1 Y1 E1\n")
    os.environ["OCTO_OFFLINE_KEY"] = "k"
    cfg = Config(
        {
            "binaries": {"openscad": "x", "orcaslicer": "y"},
            "defaults": {"printer": "p", "material": "pla"},
            "printers": {"p": {"name": "P"}},
            "materials": {"pla": {"name": "PLA", "nozzle_temp": 210, "bed_temp": 55,
                                  "wall_multiplier": 2.0, "shrinkage": 0.002}},
            "connectors": {
                "octo": {"type": "octoprint", "base_url": "http://127.0.0.1:1",
                         "api_key_env": "OCTO_OFFLINE_KEY"}
            },
            "limits": {},
        }
    )
    _send_print_job(cfg, "octo", str(g))
    out = capsys.readouterr().out
    assert "Not sent to octo" in out
    assert str(g) in out  # download fallback: the G-code is still on disk


def test_models_command_prints_hardware_and_recommendation(monkeypatch, capsys):
    # Stage 6: `kimcad models` probes the machine + installed models and prints a
    # recommendation. Monkeypatch the I/O probes so the test is deterministic; the real
    # (pure) recommend() runs end to end.
    import kimcad.model_advisor as adv

    monkeypatch.setattr(
        adv, "probe_hardware",
        lambda: adv.HardwareProfile(os_label="Windows 11", cpu_count=16, ram_gb=32.0),
    )
    monkeypatch.setattr(
        adv, "probe_installed_models",
        lambda base_url, **k: [adv.InstalledModel("gemma4:e4b", 9.6)],
    )
    code = main(["models"])
    out = capsys.readouterr().out
    assert code == 0
    assert "Hardware" in out and "32 GB RAM" in out
    assert "gemma4:e4b" in out
    assert "Recommendation" in out
    assert "never hardwired" in out  # the choosability reminder


def test_models_command_handles_no_ollama(monkeypatch, capsys):
    import kimcad.model_advisor as adv

    monkeypatch.setattr(
        adv, "probe_hardware",
        lambda: adv.HardwareProfile(os_label="Linux 6", cpu_count=4, ram_gb=8.0),
    )
    monkeypatch.setattr(adv, "probe_installed_models", lambda base_url, **k: [])
    code = main(["models"])
    out = capsys.readouterr().out
    assert code == 0
    assert "none detected" in out
