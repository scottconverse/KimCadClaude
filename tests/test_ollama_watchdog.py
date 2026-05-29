import importlib.util
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ollama_watchdog.py"
_spec = importlib.util.spec_from_file_location("kimcad_ollama_watchdog", _SCRIPT)
wd = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = wd
_spec.loader.exec_module(wd)


def test_is_up_false_when_unreachable(monkeypatch):
    def boom(*a, **k):
        raise OSError("connection refused")

    monkeypatch.setattr(wd.urllib.request, "urlopen", boom)
    assert wd.is_up(timeout=0.1) is False


def test_is_up_true_when_endpoint_responds(monkeypatch):
    monkeypatch.setattr(wd.urllib.request, "urlopen", lambda *a, **k: object())
    assert wd.is_up() is True


def test_ollama_path_returns_str_or_none():
    # Resolves an executable path or None — never raises.
    p = wd.ollama_path()
    assert p is None or isinstance(p, str)
