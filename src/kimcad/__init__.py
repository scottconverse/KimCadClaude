"""KimCad — AI-assisted parametric design for functional 3D prints."""

# Stage 11 Slice 11.3: the version is SINGLE-SOURCED from package metadata (pyproject's
# `version`). Every surface — CLI --version, /api/health, Settings' About, the installer —
# reads this attribute; no file carries a literal copy (test_version_single_source.py).
# The fallback covers a source tree that was never `pip install -e`'d: visibly a dev
# build, never mistakable for a release.
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

try:
    __version__ = _pkg_version("kimcad")
except PackageNotFoundError:  # pragma: no cover - running from a bare source tree
    __version__ = "0.0.0.dev0"
