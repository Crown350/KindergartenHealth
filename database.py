import sqlite3
import shutil
import os
import tempfile
from datetime import datetime, timedelta

import paths

# Canonical "no group filter" sentinel. The data layer owns this value so that
# filtering semantics are defined in exactly one place; the GUI must import it
# instead of hardcoding its own copy.
ALL_GROUPS = "Все"

# Schema version of the database layout this build knows how to produce.
#
# Version 1 is the baseline: the six-table schema created by
# ``Database._init_schema``. The number is stored on disk via
# ``PRAGMA user_version`` so the data layer can tell what a file holds instead
# of guessing from ``CREATE TABLE IF NOT EXISTS``. Bump it ONLY together with
# an entry in ``Database.MIGRATIONS``.
SCHEMA_VERSION = 1


class SchemaError(Exception):
    """Raised when the on-disk schema version is not compatible with this
    build (for example a file written by a NEWER application)."""


def _silent_remove(path):
    """Remove ``path`` if it exists, ignoring errors.

    Used only for cleanup of a temporary backup artifact: a failure to remove
    it must never mask the original error.
    """
    try:
        os.remove(path)
    except OSError:
        pass


def group_filter_choices(groups):
    """Build the sidebar group-combo choices: the all-groups sentinel first,
    followed by the real group names.

    Pure function: takes the rows returned by Database.get_groups() (or any
    iterable of mapping-like objects exposing ``['name']``) and returns a new
    list, never mutating the input.
    """
    return [ALL_GROUPS] + [g["name"] for g in groups]


class Database:
    """
    Handles SQLite database interactions for the Kindergarten Health Monitor.
    """

    # Forward-only migration registry, keyed by the TARGET schema version.
    #
    # Maps ``target_version -> callable(cursor)``. The callable receives one
    # cursor and must make its schema/data changes through it. Migrations run
    # sequentially and transactionally; ``user_version`` advances only after a
    # step succeeds.
    #
    # Starts EMPTY: the baseline schema is created by ``_init_schema`` and no
    # real schema change exists yet. Add an entry here only when a genuine
    # change to the six-table schema ships.
    MIGRATIONS = {}

    def __init__(self, db_file=None):
        # The default database lives in the ignored runtime directory
        # (paths.DB_PATH); passing an explicit path overrides it, which is what
        # tests and populate_db --db do. The parent directory is created here
        # (lazily, only for the file actually requested) so a clean first
        # launch can create a fresh schema without the caller preparing the
        # directory tree.
        if db_file is None:
            db_file = paths.DB_PATH
        os.makedirs(os.path.dirname(os.path.abspath(db_file)), exist_ok=True)
        self.db_file = db_file
        self.conn = sqlite3.connect(db_file)
        self.conn.row_factory = sqlite3.Row  # Allows accessing columns by name
        self.cursor = self.conn.cursor()
        self._init_schema()
        self._check_schema_version()

    def _init_schema(self):
        """Initializes the database schema."""
        self.cursor.executescript('''
            CREATE TABLE IF NOT EXISTS groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                name TEXT NOT NULL UNIQUE
            );
            
            CREATE TABLE IF NOT EXISTS children (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                full_name TEXT NOT NULL, 
                birth_date DATE NOT NULL, 
                group_id INTEGER, 
                photo_path TEXT,
                allergies TEXT,
                FOREIGN KEY (group_id) REFERENCES groups (id)
            );
            
            CREATE TABLE IF NOT EXISTS parents (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                child_id INTEGER, 
                full_name TEXT NOT NULL, 
                phone TEXT, 
                FOREIGN KEY (child_id) REFERENCES children (id)
            );
            
            CREATE TABLE IF NOT EXISTS health_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                child_id INTEGER, 
                record_date DATE NOT NULL, 
                record_type TEXT NOT NULL, 
                description TEXT, 
                height REAL, 
                weight REAL, 
                diagnosis TEXT, 
                FOREIGN KEY (child_id) REFERENCES children (id)
            );
            
            CREATE TABLE IF NOT EXISTS vaccinations (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                child_id INTEGER, 
                vaccine_name TEXT NOT NULL, 
                date_administered DATE NOT NULL, 
                status TEXT, 
                FOREIGN KEY (child_id) REFERENCES children (id)
            );
            
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                child_id INTEGER,
                date DATE NOT NULL,
                status TEXT NOT NULL,
                FOREIGN KEY (child_id) REFERENCES children (id),
                UNIQUE(child_id, date)
            );
        ''')
        self.conn.commit()

    # --- Schema versioning -------------------------------------------------
    def _check_schema_version(self):
        """Adopt or migrate the on-disk schema to ``SCHEMA_VERSION``.

        Three cases:

        * ``user_version == 0``: a database written by a pre-versioning build
          (or a freshly created file). The six-table schema is already the
          current one, so the file is simply ADOPTED as the baseline by
          recording the version. No table is dropped or recreated and no row
          is ever deleted.
        * ``0 < user_version < SCHEMA_VERSION``: an older but versioned
          database. Pending migrations are applied in ascending order.
        * ``user_version > SCHEMA_VERSION``: the file was written by a NEWER
          build. Never silently downgrade or rewrite it -- refuse loudly so
          the user learns to upgrade the application instead of having data
          mangled by older code.
        """
        current = self.cursor.execute("PRAGMA user_version").fetchone()[0]

        if current > SCHEMA_VERSION:
            raise SchemaError(
                "Database schema version {} is newer than the version {} "
                "supported by this application. Upgrade the application before "
                "using this database.".format(current, SCHEMA_VERSION)
            )

        if current == 0:
            # Baseline adoption. The schema is created by _init_schema above
            # (idempotent), so only the version bookkeeping is missing.
            self.cursor.execute("PRAGMA user_version = %d" % SCHEMA_VERSION)
            self.conn.commit()
            return

        if current < SCHEMA_VERSION:
            self._migrate(current)

    def _migrate(self, from_version):
        """Apply pending forward migrations from ``from_version`` upward.

        Each step runs inside an explicitly opened SQLite transaction and
        bumps ``user_version`` only after it succeeds, so a failed migration
        leaves the recorded version unchanged and its schema/data changes are
        rolled back. SQLite supports transactional DDL, so a plain ``CREATE``
        or ``ALTER`` inside the transaction is undone together with any row
        changes when the step raises.
        """
        version = from_version
        while version < SCHEMA_VERSION:
            target = version + 1
            migrate = self.MIGRATIONS.get(target)
            if migrate is None:
                raise SchemaError(
                    "No migration is registered to reach schema version {} "
                    "(current {}).".format(target, version)
                )
            # Open the transaction explicitly: the module's implicit
            # transaction handling does not wrap DDL, so relying on it would
            # let a half-applied schema change commit itself. On failure the
            # version is deliberately left at ``version`` and the original
            # error is surfaced to the caller.
            if not self.conn.in_transaction:
                self.conn.execute("BEGIN")
            try:
                migrate(self.cursor)
                self.cursor.execute("PRAGMA user_version = %d" % target)
                self.conn.execute("COMMIT")
            except Exception:
                self.conn.rollback()
                raise
            version = target

    # --- Group Management ---
    def add_group(self, name):
        try:
            self.cursor.execute("INSERT INTO groups (name) VALUES (?)", (name,))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_groups(self):
        self.cursor.execute("SELECT id, name FROM groups ORDER BY name")
        return self.cursor.fetchall()

    def update_group(self, group_id, name):
        try:
            self.cursor.execute("UPDATE groups SET name = ? WHERE id = ?", (name, group_id))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def delete_group(self, group_id):
        # Prevent deletion if group has children
        self.cursor.execute("SELECT 1 FROM children WHERE group_id = ?", (group_id,))
        if self.cursor.fetchone():
            return False
        
        self.cursor.execute("DELETE FROM groups WHERE id = ?", (group_id,))
        self.conn.commit()
        return True

    # --- Child Management ---
    def add_child(self, full_name, birth_date, group_id, photo_path=None, allergies=None):
        self.cursor.execute(
            "INSERT INTO children (full_name, birth_date, group_id, photo_path, allergies) VALUES (?, ?, ?, ?, ?)",
            (full_name, birth_date, group_id, photo_path, allergies)
        )
        self.conn.commit()
        return self.cursor.lastrowid

    def update_child(self, child_id, full_name, birth_date, group_id, photo_path=None, allergies=None):
        self.cursor.execute(
            "UPDATE children SET full_name = ?, birth_date = ?, group_id = ?, photo_path = ?, allergies = ? WHERE id = ?",
            (full_name, birth_date, group_id, photo_path, allergies, child_id)
        )
        self.conn.commit()

    def delete_child(self, child_id):
        # Clean up external resources (photos)
        self.cursor.execute("SELECT photo_path FROM children WHERE id = ?", (child_id,))
        row = self.cursor.fetchone()
        if row and row['photo_path'] and os.path.exists(row['photo_path']):
            try:
                os.remove(row['photo_path'])
            except OSError:
                pass # Log this in a real app

        # Cascade delete (manually since SQLite FK cascade might not be enabled)
        tables = ['parents', 'health_records', 'vaccinations', 'attendance']
        for table in tables:
            self.cursor.execute(f"DELETE FROM {table} WHERE child_id = ?", (child_id,))
            
        self.cursor.execute("DELETE FROM children WHERE id = ?", (child_id,))
        self.conn.commit()

    def get_children_summary(self, search_query="", group_filter=ALL_GROUPS):
        """Return child summary rows, optionally filtered by free-text name
        search and/or group.

        ``group_filter`` is treated as "no filter" for None, "", the canonical
        sentinel ALL_GROUPS and the legacy English "All" (kept for backwards
        compatibility with any persisted state).

        Name matching is performed in Python with str.casefold() because
        SQLite LIKE only case-folds ASCII, leaving Cyrillic case-sensitive.
        The user-supplied search term is NEVER concatenated into SQL.
        """
        query = '''
            SELECT c.id, c.full_name, g.name as group_name, c.allergies
            FROM children c
            LEFT JOIN groups g ON c.group_id = g.id
            WHERE 1=1
        '''
        params = []
        if group_filter and group_filter not in (ALL_GROUPS, "All"):
            query += " AND g.name = ?"
            params.append(group_filter)

        query += " ORDER BY c.full_name"
        self.cursor.execute(query, params)
        rows = self.cursor.fetchall()

        if search_query:
            needle = search_query.casefold()
            rows = [r for r in rows if needle in r["full_name"].casefold()]

        return rows

    def get_child_full_info(self, child_id):
        """Returns tuple: (child_info, parents, health_records, vaccinations)"""
        self.cursor.execute("""
            SELECT c.*, g.name as group_name 
            FROM children c 
            LEFT JOIN groups g ON c.group_id = g.id 
            WHERE c.id=?
        """, (child_id,))
        child = self.cursor.fetchone()
        
        self.cursor.execute("SELECT * FROM parents WHERE child_id=? ORDER BY full_name", (child_id,))
        parents = self.cursor.fetchall()
        
        self.cursor.execute("SELECT * FROM health_records WHERE child_id=? ORDER BY record_date DESC", (child_id,))
        health = self.cursor.fetchall()
        
        self.cursor.execute("SELECT * FROM vaccinations WHERE child_id=? ORDER BY date_administered DESC", (child_id,))
        vaccinations = self.cursor.fetchall()
        
        return child, parents, health, vaccinations

    # --- Parent Management ---
    def add_parent(self, child_id, full_name, phone):
        self.cursor.execute("INSERT INTO parents (child_id, full_name, phone) VALUES (?, ?, ?)", (child_id, full_name, phone))
        self.conn.commit()

    def delete_parent(self, parent_id):
        self.cursor.execute("DELETE FROM parents WHERE id = ?", (parent_id,))
        self.conn.commit()

    # --- Health Records ---
    def add_health_record(self, child_id, date, r_type, desc, height, weight, diagnosis):
        self.cursor.execute(
            "INSERT INTO health_records (child_id, record_date, record_type, description, height, weight, diagnosis) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (child_id, date, r_type, desc, height, weight, diagnosis)
        )
        self.conn.commit()

    def delete_health_record(self, record_id):
        self.cursor.execute("DELETE FROM health_records WHERE id = ?", (record_id,))
        self.conn.commit()

    # --- Vaccinations ---
    def add_vaccination(self, child_id, name, date, status):
        self.cursor.execute(
            "INSERT INTO vaccinations (child_id, vaccine_name, date_administered, status) VALUES (?, ?, ?, ?)",
            (child_id, name, date, status)
        )
        self.conn.commit()

    def delete_vaccination(self, vac_id):
        self.cursor.execute("DELETE FROM vaccinations WHERE id = ?", (vac_id,))
        self.conn.commit()

    # --- Attendance ---
    def mark_attendance(self, child_id, date, status):
        self.cursor.execute(
            "INSERT OR REPLACE INTO attendance (child_id, date, status) VALUES (?, ?, ?)",
            (child_id, date, status)
        )
        self.conn.commit()

    def get_group_attendance(self, group_id, date):
        self.cursor.execute('''
            SELECT c.id, c.full_name, a.status
            FROM children c
            LEFT JOIN attendance a ON c.id = a.child_id AND a.date = ?
            WHERE c.group_id = ?
            ORDER BY c.full_name
        ''', (date, group_id))
        return self.cursor.fetchall()

    # --- Analytics & Utils ---
    def backup_db(self, backup_path):
        """Back up the database file to ``backup_path`` atomically.

        Returns True on success, False on any failure.

        The destination is written via a temporary file created in the SAME
        directory as the destination and then swapped into place with
        ``os.replace``. Keeping the temp file on the destination filesystem
        makes the final rename atomic, so a crash or a full disk can never
        replace the user's existing backup with a half-written file.

        Guardrails:
        * pending writes are committed before the copy, so the backup is a
          consistent database and not a partial journal state;
        * backing the database up onto itself is rejected (paths are compared
          after normalization/resolution so case and separator differences on
          Windows cannot fool the check);
        * the destination directory must already exist -- arbitrary directory
          trees are never created silently;
        * on any failure the source database and any pre-existing destination
          are left untouched and the temporary partial file is removed.
        """
        try:
            self.conn.commit()
        except sqlite3.Error:
            return False

        # os.path.normcase handles Windows case-insensitivity and separator
        # differences; abspath resolves relative paths against the CWD.
        source = os.path.normcase(os.path.abspath(self.db_file))
        dest = os.path.normcase(os.path.abspath(backup_path))
        if source == dest:
            return False

        dest_dir = os.path.dirname(dest)
        if not dest_dir or not os.path.isdir(dest_dir):
            # Explicit failure instead of silently creating a directory tree.
            return False

        # Create the temp file, then immediately close its handle. Leaving a
        # NamedTemporaryFile open would make shutil.copy2 fail on Windows
        # because the file could not be reopened for writing.
        try:
            temp_fd, temp_path = tempfile.mkstemp(
                prefix=".kgh_backup_", suffix=".tmp", dir=dest_dir
            )
        except OSError:
            return False
        os.close(temp_fd)

        try:
            try:
                shutil.copy2(self.db_file, temp_path)
            except OSError:
                _silent_remove(temp_path)
                return False
            try:
                os.replace(temp_path, dest)
            except OSError:
                _silent_remove(temp_path)
                return False
        except Exception:
            # Defensive catch-all: never leave a temp file behind, and never
            # mask the source DB on an unexpected error path.
            _silent_remove(temp_path)
            return False
        return True

    def get_dashboard_stats(self):
        stats = {}
        
        # Children distribution
        self.cursor.execute("SELECT g.name, COUNT(c.id) FROM groups g LEFT JOIN children c ON g.id = c.group_id GROUP BY g.name")
        stats['children_per_group'] = self.cursor.fetchall()
        
        # Top diagnoses
        self.cursor.execute("""
            SELECT diagnosis, COUNT(*) as cnt 
            FROM health_records 
            WHERE diagnosis IS NOT NULL AND diagnosis != '' 
            GROUP BY diagnosis 
            ORDER BY cnt DESC LIMIT 5
        """)
        stats['top_diagnoses'] = self.cursor.fetchall()
        
        return stats

    def get_vaccine_reminders(self):
        """
        Identify children who need the 6-year-old Measles (Корь) booster.
        Logic: Children between 6 and 7 years old who haven't had a Measles shot in the last 2 years.
        """
        reminders = []
        today = datetime.now()
        date_6yo = (today - timedelta(days=365*6)).strftime('%Y-%m-%d')
        date_7yo = (today - timedelta(days=365*7)).strftime('%Y-%m-%d')
        
        # Find 6-year-olds
        self.cursor.execute('''
            SELECT id, full_name, birth_date
            FROM children
            WHERE birth_date <= ? AND birth_date >= ?
        ''', (date_6yo, date_7yo))
        
        candidates = self.cursor.fetchall()
        
        for child in candidates:
            # Check for recent measles vaccine (last 2 years).
            check_date = (today - timedelta(days=365*2)).strftime('%Y-%m-%d')
            self.cursor.execute('''
                SELECT vaccine_name FROM vaccinations
                WHERE child_id = ? AND date_administered > ?
            ''', (child['id'], check_date))
            # Match the vaccine name case-insensitively in Python: SQLite LIKE
            # only case-folds ASCII, so a Cyrillic name stored as 'корь' would
            # never match a '%Корь%' pattern.
            has_recent_measles = any(
                'корь' in (row['vaccine_name'] or '').casefold()
                for row in self.cursor.fetchall()
            )
            
            if not has_recent_measles:
                reminders.append(f"Ревакцинация от кори (6 лет): {child['full_name']}")

        return reminders

    def close(self):
        self.conn.close()
