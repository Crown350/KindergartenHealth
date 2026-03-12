import sqlite3
import shutil
import os
from datetime import datetime, timedelta

class Database:
    """
    Handles SQLite database interactions for the Kindergarten Health Monitor.
    """
    
    def __init__(self, db_file="kindergarten.db"):
        self.db_file = db_file
        self.conn = sqlite3.connect(db_file)
        self.conn.row_factory = sqlite3.Row  # Allows accessing columns by name
        self.cursor = self.conn.cursor()
        self._init_schema()

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

    def get_children_summary(self, search_query="", group_filter="All"):
        query = '''
            SELECT c.id, c.full_name, g.name as group_name, c.allergies
            FROM children c
            LEFT JOIN groups g ON c.group_id = g.id
            WHERE 1=1
        '''
        params = []
        if search_query:
            query += " AND c.full_name LIKE ?"
            params.append(f"%{search_query}%")
        
        if group_filter and group_filter != "All":
            query += " AND g.name = ?"
            params.append(group_filter)
            
        query += " ORDER BY c.full_name"
        self.cursor.execute(query, params)
        return self.cursor.fetchall()

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
        try:
            self.conn.commit()
            shutil.copy2(self.db_file, backup_path)
            return True
        except IOError:
            return False

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
            # Check for recent measles vaccine (last 2 years)
            check_date = (today - timedelta(days=365*2)).strftime('%Y-%m-%d')
            self.cursor.execute('''
                SELECT 1 FROM vaccinations 
                WHERE child_id = ? AND vaccine_name LIKE '%Корь%' AND date_administered > ?
            ''', (child['id'], check_date))
            
            if not self.cursor.fetchone():
                reminders.append(f"Ревакцинация от кори (6 лет): {child['full_name']}")

        return reminders

    def close(self):
        self.conn.close()
