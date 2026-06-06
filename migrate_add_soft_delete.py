"""
Migration Script: Add Soft Delete & File Views Support
======================================================
This script safely adds the new columns and table to an EXISTING database
without destroying any existing data. It uses ALTER TABLE for SQLite.

Usage:
    python migrate_add_soft_delete.py

NOTE: If you are starting fresh (no existing data), you do NOT need this
script. Simply run `python run.py` and SQLAlchemy's db.create_all() will
create all tables including the new columns and file_views table.

This script is IDEMPOTENT -- it checks if columns/tables already exist
before attempting to add them, so it is safe to run multiple times.
"""

import os
import sqlite3
import sys


def get_db_path():
    """Determine the path to the SQLite database file."""
    base_dir = os.path.abspath(os.path.dirname(__file__))
    db_path = os.path.join(base_dir, 'instance', 'app.db')
    
    if not os.path.exists(db_path):
        print(f"[ERROR] Database not found at: {db_path}")
        print("        Run 'python run.py' first to create the database.")
        sys.exit(1)
    
    return db_path


def column_exists(cursor, table_name, column_name):
    """Check if a column already exists in a table."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns


def table_exists(cursor, table_name):
    """Check if a table already exists in the database."""
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    return cursor.fetchone() is not None


def migrate(db_path):
    """Run all migration steps."""
    print(f"[INFO] Connecting to database: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    changes_made = False
    
    # ------------------------------------------------------------------
    # Step 1: Add 'deleted' column to 'files' table (Boolean, default 0)
    # ------------------------------------------------------------------
    if not column_exists(cursor, 'files', 'deleted'):
        print("[MIGRATE] Adding 'deleted' column to 'files' table...")
        cursor.execute(
            "ALTER TABLE files ADD COLUMN deleted BOOLEAN NOT NULL DEFAULT 0"
        )
        changes_made = True
        print("          OK: 'deleted' column added.")
    else:
        print("[SKIP]    'deleted' column already exists in 'files' table.")
    
    # ------------------------------------------------------------------
    # Step 2: Add 'deleted_at' column to 'files' table (DateTime, nullable)
    # ------------------------------------------------------------------
    if not column_exists(cursor, 'files', 'deleted_at'):
        print("[MIGRATE] Adding 'deleted_at' column to 'files' table...")
        cursor.execute(
            "ALTER TABLE files ADD COLUMN deleted_at DATETIME"
        )
        changes_made = True
        print("          OK: 'deleted_at' column added.")
    else:
        print("[SKIP]    'deleted_at' column already exists in 'files' table.")
    
    # ------------------------------------------------------------------
    # Step 3: Add 'deleted_by' column to 'files' table (Integer FK, nullable)
    # ------------------------------------------------------------------
    if not column_exists(cursor, 'files', 'deleted_by'):
        print("[MIGRATE] Adding 'deleted_by' column to 'files' table...")
        cursor.execute(
            "ALTER TABLE files ADD COLUMN deleted_by INTEGER REFERENCES users(id)"
        )
        changes_made = True
        print("          OK: 'deleted_by' column added.")
    else:
        print("[SKIP]    'deleted_by' column already exists in 'files' table.")
    
    # ------------------------------------------------------------------
    # Step 4: Create 'file_views' table if it doesn't exist
    # ------------------------------------------------------------------
    if not table_exists(cursor, 'file_views'):
        print("[MIGRATE] Creating 'file_views' table...")
        cursor.execute("""
            CREATE TABLE file_views (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER NOT NULL REFERENCES files(id),
                user_id INTEGER NOT NULL REFERENCES users(id),
                viewed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(file_id, user_id)
            )
        """)
        changes_made = True
        print("          OK: 'file_views' table created.")
    else:
        print("[SKIP]    'file_views' table already exists.")
    
    # ------------------------------------------------------------------
    # Step 5: Create trash/ directory if it doesn't exist
    # ------------------------------------------------------------------
    base_dir = os.path.abspath(os.path.dirname(__file__))
    trash_dir = os.path.join(base_dir, 'trash')
    if not os.path.exists(trash_dir):
        os.makedirs(trash_dir)
        print(f"[MIGRATE] Created trash directory: {trash_dir}")
        changes_made = True
    else:
        print(f"[SKIP]    Trash directory already exists: {trash_dir}")
    
    # Commit and close
    if changes_made:
        conn.commit()
        print("\n[SUCCESS] Migration completed. All changes committed.")
    else:
        print("\n[INFO]    No changes needed -- database is already up to date.")
    
    conn.close()


if __name__ == '__main__':
    print("=" * 60)
    print("  Soft Delete & File Views Migration Script")
    print("=" * 60)
    print()
    
    db_path = get_db_path()
    migrate(db_path)
    
    print()
    print("Next steps:")
    print("  1. Run the application:  python run.py")
    print("  2. Test file viewing -> Delete button appears after view")
    print("  3. Test soft delete -> File moves to trash/")
    print("  4. Test admin trash -> Restore and permanent delete")
    print()
