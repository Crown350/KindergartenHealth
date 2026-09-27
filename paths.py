"""Centralized runtime paths for the application.

All writable application state (the SQLite database, child photos, generated
backups) lives under a single runtime directory which is ignored by git.
Production code resolves its default locations from here so runtime data is
never written into the tracked source tree.

The development runtime directory is ``.runtime`` beside this file. A packaged
Windows build can later point these at a user-writable location (e.g.
LOCALAPPDATA) without touching the modules that consume them.

Tests ALWAYS pass their own explicit tempfile paths/directories (see
tests/db_fixtures.py) and never touch this directory.
"""

import os
import sys


def _writable_root():
    """Where the application should keep its writable state.

    * Development: the directory this file lives in, so runtime data lands in
      the git-ignored ``<repo>/.runtime`` folder.
    * Frozen (PyInstaller): a per-user folder under LOCALAPPDATA. The bundle's
      own directory may be read-only (e.g. Program Files) and a ``--onefile``
      bundle extracts itself to ``sys._MEIPASS``, which is DELETED on exit, so
      neither can hold the database/photos across runs. LOCALAPPDATA is always
      writable for the current user.
    """
    if getattr(sys, "frozen", False):
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return os.path.join(base, "KindergartenHealth")
    return os.path.dirname(os.path.abspath(__file__))


PROJECT_ROOT = _writable_root()

# Single ignored root for every file the application writes at runtime.
RUNTIME_DIR = os.path.join(PROJECT_ROOT, ".runtime")

# Default SQLite database location for the running application.
DB_PATH = os.path.join(RUNTIME_DIR, "kindergarten.db")

# Child photos (see photos.py).
PHOTOS_DIR = os.path.join(RUNTIME_DIR, "photos")

# Default location for generated backups.
BACKUPS_DIR = os.path.join(RUNTIME_DIR, "backups")


def ensure_runtime_dirs():
    """Create the runtime directories (idempotent; safe to call repeatedly).

    Returns RUNTIME_DIR. Callers that only need one artifact may simply create
    the relevant parent directory themselves with os.makedirs(exist_ok=True).
    """
    for path in (RUNTIME_DIR, PHOTOS_DIR, BACKUPS_DIR):
        os.makedirs(path, exist_ok=True)
    return RUNTIME_DIR
