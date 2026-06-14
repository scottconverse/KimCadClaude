# KC-20 (#25): makes tests/e2e a package so this subtree's conftest.py imports as `e2e.conftest`,
# not the top-level `conftest` module — otherwise it shadows tests/conftest.py and the existing
# suite's `from conftest import BAMBU, ...` breaks (pytest prepend import-mode module-name clash).
