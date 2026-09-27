"""Repository hygiene tests (Tier 0 + an optional git-backed tier).

The ignore POLICY is asserted in two independent ways:

1. .gitignore content: the required patterns are present as literal lines
   (always runs; no git, no shell, no platform dependency).
2. git-backed (skipped unless git is available): the runtime artifacts are
   actually reported as ignored and the sensitive files are no longer tracked
   in the index. Concrete paths are used (never trailing-slash forms, which
   returned spurious results on this git/Windows combination).
"""

import os
import shutil
import subprocess
import unittest

import paths

# Patterns that MUST appear as literal (non-comment) lines in .gitignore.
REQUIRED_PATTERNS = [
    ".runtime/",
    "*.db",
    "*.db-journal",
    "*.db-wal",
    "*.db-shm",
    "photos/",
    "backups/",
    "*.pdf",
    "*.xlsx",
    ".serena/",
    "__pycache__/",
    "build/",
    "dist/",
]

# The tracked PyInstaller spec must stay committable, so the ignore list must
# NOT contain a blanket *.spec pattern.
MUST_NOT_IGNORE = ["KindergartenHealth.spec"]

# Files that must never be tracked in the index (verified with git ls-files).
MUST_NOT_BE_TRACKED = [
    "kindergarten.db",
    "123.db",
    "photos/123_1772096116.964602.jpg",
    "photos/123_1772096373.268721.jpg",
]

# The repository's single initial commit. It must always remain an ancestor of
# HEAD: that is how the hygiene work proves it never rewrote history.
INITIAL_COMMIT = "38b58dcc972daf1d32de00c26264f25ec6393400"


def _git_available():
    return shutil.which("git") is not None


def _git(args):
    """Run git in the project root; returns (ok, stdout)."""
    try:
        proc = subprocess.run(
            ["git"] + args,
            cwd=paths.PROJECT_ROOT,
            capture_output=True,
            text=True,
            shell=False,
        )
    except OSError:
        return False, ""
    return proc.returncode == 0, proc.stdout


class TestIgnorePolicyFile(unittest.TestCase):
    """The ignore policy is readable straight from .gitignore (no git needed)."""

    @classmethod
    def setUpClass(cls):
        with open(
            os.path.join(paths.PROJECT_ROOT, ".gitignore"), encoding="utf-8"
        ) as f:
            cls.lines = [
                ln.strip()
                for ln in f.read().splitlines()
                if ln.strip() and not ln.strip().startswith("#")
            ]

    def test_required_patterns_present(self):
        missing = [p for p in REQUIRED_PATTERNS if p not in self.lines]
        self.assertEqual(missing, [], f".gitignore is missing patterns: {missing}")

    def test_no_blanket_spec_ignore(self):
        # A blanket "*.spec" would ignore the project's own tracked spec.
        self.assertNotIn("*.spec", self.lines)
        for pat in MUST_NOT_IGNORE:
            self.assertNotIn(pat, self.lines)


@unittest.skipUnless(_git_available(), "git not available")
class TestIgnorePolicyGit(unittest.TestCase):
    """The policy is what git actually reports, not just what the file says."""

    def _ignored(self, relpath):
        ok, out = _git(["check-ignore", "-v", relpath])
        # exit 0 + output => ignored; exit 1 => not ignored
        return ok and out.strip() != ""

    def test_runtime_artifacts_are_ignored(self):
        for rel in (
            ".runtime/kindergarten.db",
            ".runtime/photos/1.png",
            ".runtime/backups/backup.db",
            "photos/anything.jpg",
            "backups/anything.db",
            "report.pdf",
            "export.xlsx",
            "new_runtime.db",
        ):
            self.assertTrue(self._ignored(rel), f"NOT ignored: {rel}")

    def test_sensitive_runtime_files_no_longer_tracked(self):
        ok, out = _git(["ls-files"])
        self.assertTrue(ok, "git ls-files failed")
        tracked = {ln for ln in out.splitlines() if ln}
        for rel in MUST_NOT_BE_TRACKED:
            self.assertNotIn(rel, tracked, f"still tracked in the index: {rel}")

    def test_history_was_never_rewritten(self):
        # The audit tripwire originally pinned HEAD to the initial commit to
        # catch accidental commits during the hygiene work. Once the intended
        # final commit lands, HEAD legitimately moves past it, so the lasting
        # invariant is that the initial commit stayed an ancestor of HEAD
        # (i.e. history was rewritten never, only appended to).
        ok, _ = _git(["merge-base", "--is-ancestor", INITIAL_COMMIT, "HEAD"])
        self.assertTrue(ok, "initial commit is not an ancestor of HEAD")
        ok, out = _git(["rev-parse", "HEAD"])
        self.assertTrue(ok, "git rev-parse HEAD failed")
        self.assertNotEqual(
            out.strip(),
            INITIAL_COMMIT,
            "HEAD is still the initial commit; expected the final commit",
        )


if __name__ == "__main__":
    unittest.main()
