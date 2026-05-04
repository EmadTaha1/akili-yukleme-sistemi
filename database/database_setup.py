import sqlite3
import os

def setup_database():
    """
    Initializes the relational database for the Attendance System.
    WARNING: This will delete the existing database to apply the new schema.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, "attendance_system.db")
    
    # Remove old database to prevent schema conflicts
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"[INFO] Old database removed at {db_path}. Building new schema...")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. Teachers Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Teachers (
            teacher_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    ''')
    
    # Insert a default teacher for testing
    cursor.execute('''
        INSERT OR IGNORE INTO Teachers (teacher_id, name, email, password_hash)
        VALUES (1, 'Admin Teacher', 'admin@university.edu', 'hashed_password_here')
    ''')

    # 2. Subjects Table (UPDATED: Added course_code and study_year)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Subjects (
            subject_id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_code TEXT NOT NULL,
            subject_name TEXT NOT NULL,
            study_year TEXT NOT NULL,
            academic_year TEXT NOT NULL,
            major TEXT NOT NULL,
            teacher_id INTEGER,
            FOREIGN KEY(teacher_id) REFERENCES Teachers(teacher_id)
        )
    ''')

    # 3. Students Table (Global pool of students)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Students (
            student_id INTEGER PRIMARY KEY AUTOINCREMENT,
            university_id INTEGER UNIQUE NOT NULL,
            name TEXT NOT NULL,
            face_encoding_path TEXT
        )
    ''')

    # 4. Enrollments Table (Links Students to Subjects)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Enrollments (
            enrollment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            subject_id INTEGER,
            FOREIGN KEY(student_id) REFERENCES Students(student_id),
            FOREIGN KEY(subject_id) REFERENCES Subjects(subject_id)
        )
    ''')

    # 5. Attendance Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Attendance (
            attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
            enrollment_id INTEGER,
            date TEXT NOT NULL,
            week_number INTEGER,
            status TEXT NOT NULL,
            FOREIGN KEY(enrollment_id) REFERENCES Enrollments(enrollment_id)
        )
    ''')

    conn.commit()
    conn.close()
    print("[SUCCESS] New Relational database initialized successfully.")

if __name__ == "__main__":
    setup_database()