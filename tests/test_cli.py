import io

from kimcad.cli import _force_utf8_output, _normalize_argv, build_parser, main


def test_normalize_bare_prompt_becomes_design():
    assert _normalize_argv(["a 20mm block"]) == ["design", "a 20mm block"]


def test_normalize_leaves_subcommands_alone():
    assert _normalize_argv(["design", "x"]) == ["design", "x"]
    assert _normalize_argv(["bench"]) == ["bench"]
    assert _normalize_argv(["--help"]) == ["--help"]


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
