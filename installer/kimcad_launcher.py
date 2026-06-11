"""The installed app's entry point (Stage 11 Slice 11.5).

The Start-Menu shortcut runs ``{app}\\python\\pythonw.exe "{app}\\kimcad_launcher.py"``.
This file is what makes the install layout work, with no compiled launcher and no
``._pth`` surgery:

- it sets ``KIMCAD_INSTALL_ROOT`` (the paths seam's one switch) to its OWN directory,
  IN-PROCESS, before any kimcad import — satisfying the launcher contract paths.py states;
- it puts the staged ``site-packages`` on ``sys.path``;
- it dispatches to the normal CLI — ``shell`` by default (the windowed app), or whatever
  subcommand was passed (``kimcad_launcher.py web --demo`` works for verification).

Run with ``pythonw.exe`` for the windowed app (no console); ``python.exe`` for a console
surface (the verify script uses it).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ["KIMCAD_INSTALL_ROOT"] = str(ROOT)
sys.path.insert(0, str(ROOT / "site-packages"))


def main() -> int:
    from kimcad.cli import main as cli_main

    argv = sys.argv[1:] or ["shell"]
    return cli_main(argv)


if __name__ == "__main__":
    sys.exit(main())
