"""Typed, user-facing error classes shared across the CLI, pipeline, and web layer.

Stage A (first-run hardening): the most likely first-run failures — a tool binary that was
never fetched, a model server that was never started — must surface as ONE friendly,
actionable sentence in every surface, never a traceback (CLI) or a leaked exception class
(web 500). The CLI maps these in ``cli.main``; the web layer maps them in
``webapp._handle_design``. Both reuse the exact message carried here so the two surfaces
can never drift apart (QA-001/QA-003).
"""

from __future__ import annotations

from pathlib import Path


class ToolMissingError(RuntimeError):
    """A required external tool binary (OpenSCAD / OrcaSlicer) is not on disk.

    Raised *before* any subprocess spawn, so a skipped ``fetch_tools.py`` step can never
    surface as a raw ``FileNotFoundError: [WinError 2]`` mid-pipeline (QA-003). The message
    is written for the end user and includes the exact recovery command.
    """

    def __init__(self, tool: str, path: Path):
        self.tool = tool
        self.path = path
        super().__init__(
            f"{tool} isn't installed at {path}. "
            f"Run `python scripts/fetch_tools.py` to download it, "
            f"or point binaries.{tool.lower()} in config/local.yaml at your own copy."
        )
