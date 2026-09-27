"""Managed photo lifecycle for child photos (stdlib only).

Every child photo lives inside one managed directory. Filenames are built from
the child id (never from free-text names), preserving the real source
extension, so a PNG stays a PNG and a JPEG stays a .jpg. Destination paths are
constructed by this module and can never escape the managed directory.
Deletion is restricted to files inside the managed directory.

The stored photo_path value is the RELATIVE path "<MANAGED_DIR>/<file>" so it
stays portable and continues to match the values already in the database.
"""

import os
import shutil
from datetime import datetime

import paths

# Managed photos live under the centralized runtime photos directory. The value
# is the path RELATIVE to the project root, because that relative form is what
# gets stored in the database and displayed by the GUI; an absolute directory
# would break the stored-path contract.
MANAGED_DIR = os.path.relpath(paths.PHOTOS_DIR, paths.PROJECT_ROOT)

_PNG = ".png"
_JPEG = {".jpg", ".jpeg"}
# Image formats the application offers in its file dialog. Anything else is
# rejected so a non-image file can never become a child photo path.
SUPPORTED_EXTENSIONS = _JPEG | {_PNG}


def _managed_dir(base):
    """Absolute path of the managed directory.

    ``base`` defaults to the project root (not the process CWD) so photos
    always land in the centralized runtime location regardless of where the
    application was launched from. Tests pass an explicit ``base`` so they
    never touch the project's own runtime directory.
    """
    if not base:
        base = paths.PROJECT_ROOT
    return os.path.abspath(os.path.join(base, MANAGED_DIR))


def ensure_managed_dir(base=None):
    """Create (if needed) and return the absolute managed directory path."""
    path = _managed_dir(base)
    os.makedirs(path, exist_ok=True)
    return path


def normalize_extension(ext):
    """Canonical safe image extension for ``ext``.

    Returns ``".png"`` for PNG, ``".jpg"`` for JPG/JPEG (case-insensitive) and
    ``None`` for anything that is not a supported image extension.
    """
    if not ext:
        return None
    ext = ext.strip().lower()
    if not ext.startswith("."):
        ext = "." + ext
    if ext == _PNG:
        return _PNG
    if ext in _JPEG:
        return ".jpg"
    return None


def _safe_child_id(child_id):
    """Filename-safe child identifier.

    Child ids come from the database primary key, but this guard guarantees
    that no path separator or traversal sequence can ever reach a filename.
    Raises ValueError when the id contains no usable character at all.
    """
    safe = "".join(ch for ch in str(child_id) if ch.isalnum() or ch in "-_")
    if not safe:
        raise ValueError("child_id must contain filename-safe characters")
    return safe


def destination_for(source, child_id, base=None):
    """Safe RELATIVE destination path inside the managed directory.

    Only the EXTENSION is taken from ``source``; the name is always
    ``<child_id>_<timestamp><ext>``, so a hostile or free-text source filename
    cannot influence the destination. Returns None for unsupported extensions.
    """
    ext = normalize_extension(os.path.splitext(source)[1])
    if ext is None:
        return None
    name = f"{_safe_child_id(child_id)}_{datetime.now().timestamp()}{ext}"
    return os.path.join(MANAGED_DIR, name)


def is_within(path, base=None):
    """True iff ``path`` is the managed directory or lives inside it.

    Never raises: paths on a different Windows drive are simply rejected.
    """
    if not path:
        return False
    root = _managed_dir(base)
    target = os.path.abspath(os.path.join(base or paths.PROJECT_ROOT, path))
    try:
        return os.path.commonpath([root, target]) == root
    except ValueError:
        # different Windows drives (or mixed/absolute forms) -> not inside
        return False


def import_photo(source, child_id, base=None):
    """Copy ``source`` into the managed directory.

    Returns the relative managed path on success, or None when the source is
    missing or has an unsupported extension (nothing is written). The result
    is always inside the managed directory; a copy that somehow lands outside
    is removed and rejected.
    """
    if not source or not os.path.isfile(source):
        return None
    rel = destination_for(source, child_id, base)
    if rel is None:
        return None
    dest = os.path.join(ensure_managed_dir(base), os.path.basename(rel))
    try:
        shutil.copy2(source, dest)
    except OSError:
        return None
    if not (os.path.isfile(dest) and is_within(dest, base)):
        try:
            os.remove(dest)
        except OSError:
            pass
        return None
    return rel


def delete_photo(path, base=None):
    """Delete ``path`` only when it is a file inside the managed directory.

    Returns True when a file was deleted, False otherwise (outside the managed
    directory, missing, or a directory such as the managed directory itself).
    """
    if not path or not is_within(path, base):
        return False
    target = os.path.abspath(os.path.join(base or paths.PROJECT_ROOT, path))
    if not os.path.isfile(target):
        return False
    try:
        os.remove(target)
    except OSError:
        return False
    return True


def commit_photo_update(old_path, stored_path, imported_path, commit, base=None):
    """Persist a photo change in the failure-safe order.

    ``commit(stored_path)`` must store ``stored_path`` as the child's
    photo_path and return True, or return False / raise on failure.

    * success  -> the PREVIOUS managed photo (``old_path``) is released, but
      only when it is a different file inside the managed directory;
    * failure  -> ``old_path`` is left completely untouched and the freshly
      imported copy (``imported_path``) is removed, so no orphan is left
      behind and the database keeps pointing at a photo that still exists.

    ``imported_path`` is the only path that may be deleted on failure; it must
    be None when nothing new was imported (e.g. an already-managed photo was
    re-selected), so a file owned by another record is never removed.

    Returns True when ``stored_path`` is now authoritative, False when the old
    state must be kept.
    """
    try:
        ok = commit(stored_path)
    except Exception:
        ok = False
    if ok:
        if old_path and old_path != stored_path:
            delete_photo(old_path, base)
        return True
    if imported_path and imported_path != old_path:
        delete_photo(imported_path, base)
    return False
