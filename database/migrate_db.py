import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'attendance_system.db')

try:
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("ALTER TABLE Students ADD COLUMN email TEXT")
        conn.commit()
    print("Migration successful: Added 'email' column to Students table.")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        print("Column 'email' already exists. Database is up to date.")
    else:
        print(f"Error: {e}")
