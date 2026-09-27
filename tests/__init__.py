"""Test package for the Kindergarten Health Monitor.

Ensures the repository root is importable so the data layer (database.py)
can be imported when the suite is discovered with
``python -m unittest discover -s tests`` run from the repository root.

All tests are headless (no tkinter / matplotlib / pandas required): they
exercise the data layer and pure helpers only.
"""
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
