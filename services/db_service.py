import sqlite3
import os
import pandas as pd

def get_db_path():
    """Returns the absolute path to the database file."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, "database", "attendance_system.db")

def get_subjects():
    """Fetch subjects from the database."""
    db_path = get_db_path()
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT subject_id, course_code, subject_name FROM Subjects")
        rows = cursor.fetchall()
    return rows

def get_subject_details(subject_id):
    """Fetch full details for a specific subject."""
    db_path = get_db_path()
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT subject_id, course_code, subject_name, academic_year FROM Subjects WHERE subject_id = ?", (subject_id,))
        return cursor.fetchone()

def search_student_global(query):
    """Search student by Name or ID in the global pool."""
    if not query.strip(): return []
    db_path = get_db_path()
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT student_id, university_id, name FROM Students WHERE name LIKE ? OR university_id LIKE ?", ('%'+query+'%', '%'+query+'%'))
        return cursor.fetchall()

def search_enrolled_students(subject_id, query):
    """STRICT SEARCH: Fetch only students enrolled in the specific subject."""
    if not query.strip(): return []
    db_path = get_db_path()
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT s.student_id, s.university_id, s.name 
            FROM Students s
            JOIN Enrollments e ON s.student_id = e.student_id
            WHERE e.subject_id = ? AND (s.name LIKE ? OR s.university_id LIKE ?)
        ''', (subject_id, '%'+query+'%', '%'+query+'%'))
        return cursor.fetchall()

def search_external_students(subject_id, query):
    """Search for students NOT yet enrolled in the specified subject."""
    if not query.strip(): return []
    db_path = get_db_path()
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT student_id, university_id, name FROM Students 
            WHERE (name LIKE ? OR university_id LIKE ?)
            AND student_id NOT IN (SELECT student_id FROM Enrollments WHERE subject_id = ?)
        ''', ('%'+query+'%', '%'+query+'%', subject_id))
        return cursor.fetchall()

def get_students_by_subject(subject_id):
    """Fetch students enrolled in a specific subject."""
    db_path = get_db_path()
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT Students.student_id, Students.university_id, Students.name 
            FROM Students 
            JOIN Enrollments ON Students.student_id = Enrollments.student_id 
            WHERE Enrollments.subject_id = ?
        ''', (subject_id,))
        return cursor.fetchall()

def get_student_status(student_db_id, subject_id):
    db_path = get_db_path()
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT face_encoding_path FROM Students WHERE student_id = ?", (student_db_id,))
        res = cursor.fetchone()
        has_face = bool(res and res[0])
        cursor.execute("SELECT * FROM Enrollments WHERE student_id = ? AND subject_id = ?", (student_db_id, subject_id))
        is_enrolled = cursor.fetchone() is not None
    return has_face, is_enrolled

def enroll_student(student_db_id, subject_id):
    db_path = get_db_path()
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO Enrollments (student_id, subject_id) VALUES (?, ?)", (student_db_id, subject_id))
        conn.commit()

def update_student_face_path(student_db_id, uni_id):
    face_path = f"dataset/User.{uni_id}"
    db_path = get_db_path()
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE Students SET face_encoding_path = ? WHERE student_id = ?", (face_path, student_db_id))
        conn.commit()

def process_excel_upload(file_path, subject_id):
    if file_path.endswith('.csv'): df = pd.read_csv(file_path)
    else: df = pd.read_excel(file_path)
    df = df.dropna(subset=[df.columns[0], df.columns[1]])
    new_s, enr_s = 0, 0
    db_path = get_db_path()
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        for _, row in df.iterrows():
            try:
                uid = int(row.iloc[0])
                name = str(row.iloc[1]).strip()
            except: continue
            cursor.execute("SELECT student_id FROM Students WHERE university_id = ?", (uid,))
            res = cursor.fetchone()
            if res: s_db_id = res[0]
            else:
                cursor.execute("INSERT INTO Students (university_id, name) VALUES (?, ?)", (uid, name))
                s_db_id = cursor.lastrowid
                new_s += 1
            cursor.execute("SELECT * FROM Enrollments WHERE student_id = ? AND subject_id = ?", (s_db_id, subject_id))
            if not cursor.fetchone():
                cursor.execute("INSERT INTO Enrollments (student_id, subject_id) VALUES (?, ?)", (s_db_id, subject_id))
                enr_s += 1
        conn.commit()
    return new_s, enr_s

def get_enrolled_university_ids(subject_id):
    db_path = get_db_path()
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT Students.university_id FROM Enrollments 
            JOIN Students ON Enrollments.student_id = Students.student_id 
            WHERE Enrollments.subject_id = ?
        ''', (subject_id,))
        return {int(row[0]) for row in cursor.fetchall()}