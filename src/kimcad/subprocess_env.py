"""Secret-scrubbed environments for KimCad's tool subprocesses (ENG-003, stage-C).

One source of truth for "what is a secret env var", shared by BOTH untrusted-code
runners — the CadQuery worker (which already scrubbed) and the OpenSCAD child (which
used to inherit everything). The children are pure geometry tools and need no
credentials, so withholding LLM/printer API keys bounds the blast radius if a
sanitizer layer is ever bypassed.

Matching is whole-NAME-segment, not substring, so look-alikes like ``TOKENIZER_PATH``
or ``PASSWORDLESS_MODE`` survive while ``OPENROUTER_API_KEY`` / ``SOME_TOKEN`` /
``DB_PASSWORD`` / ``AWS_SECRET_ACCESS_KEY`` are stripped (REAUDIT-N1). Run-together
forms (``OPENROUTERAPIKEY``, ``MYPRIVATEKEY``) are caught compactly.
"""

from __future__ import annotations

import os
import re

_SECRET_ENV_SEGMENTS = frozenset({
    "KEY", "APIKEY", "TOKEN", "SECRET", "PASSWORD", "PASSWD", "CREDENTIAL", "CREDENTIALS",
    "PRIVATEKEY",
    # ENG-104 (stage-BCD gate): common credential namings the original set missed —
    # npm_config__auth-style vars and SSH/GPG passphrases. Segment-exact, so AUTHOR
    # (no AUTH segment) and PASSPHRASES-as-substring look-alikes still survive.
    "AUTH", "PASSPHRASE",
})


def is_secret_env(name: str) -> bool:
    """True when the env-var NAME marks it as secret-bearing."""
    segments = re.split(r"[^A-Za-z0-9]+", name.upper())
    if any(seg in _SECRET_ENV_SEGMENTS for seg in segments):
        return True
    compact = "".join(segments)
    return "APIKEY" in compact or "PRIVATEKEY" in compact


def scrubbed_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """The parent environment minus secret-bearing variables, plus ``extra`` overlays."""
    env = {k: v for k, v in os.environ.items() if not is_secret_env(k)}
    if extra:
        env.update(extra)
    return env
