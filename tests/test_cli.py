from kimcad.cli import _normalize_argv, build_parser, main


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
