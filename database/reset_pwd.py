import sqlite3
import hashlib
import os

db_path = os.path.join(os.path.dirname(__file__), 'attendance_system.db')
new_pwd = hashlib.sha256('123456'.encode('utf-8')).hexdigest()

try:
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        # Get emails to show the user
        cursor.execute("SELECT email FROM Teachers WHERE teacher_id != 1")
        users = cursor.fetchall()
        
        # Update passwords
        cursor.execute("UPDATE Teachers SET password_hash = ? WHERE teacher_id != 1", (new_pwd,))
        conn.commit()

    print(f"Success! Reset {len(users)} accounts.")
    print("---------------------------------")
    for u in users:
        print(f"Email: {u[0]}")
        print(f"New Password: 123456")
        print("---------------------------------")
        
except Exception as e:
    print(f"Error: {e}")
