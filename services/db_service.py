import sqlite3
import os
import pandas as pd

def get_db_path():
    """Returns the absolute path to the database file."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, "database", "attendance_system.db")

def get_subjects(teacher_id=None):
    """Fetch subjects from the database."""
    db_path = get_db_path()
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        if teacher_id is not None:
            cursor.execute("SELECT subject_id, course_code, subject_name FROM Subjects WHERE teacher_id = ?", (teacher_id,))
        else:
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
    db_path = get_db_path()
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        if not query.strip():
            cursor.execute('''
                SELECT s.student_id, s.university_id, s.name 
                FROM Students s
                JOIN Enrollments e ON s.student_id = e.student_id
                WHERE e.subject_id = ?
            ''', (subject_id,))
        else:
            cursor.execute('''
                SELECT s.student_id, s.university_id, s.name 
                FROM Students s
                JOIN Enrollments e ON s.student_id = e.student_id
                WHERE e.subject_id = ? AND (s.name LIKE ? OR CAST(s.university_id AS TEXT) LIKE ?)
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

def update_student_face_path(student_db_id, face_id):
    face_path = f"dataset/User.{face_id}"
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
                email = str(row.iloc[2]).strip() if len(row) > 2 and pd.notna(row.iloc[2]) else None
            except: continue
            cursor.execute("SELECT student_id FROM Students WHERE university_id = ?", (uid,))
            res = cursor.fetchone()
            if res: s_db_id = res[0]
            else:
                cursor.execute("INSERT INTO Students (university_id, name, email) VALUES (?, ?, ?)", (uid, name, email))
                s_db_id = cursor.lastrowid
                new_s += 1
            cursor.execute("SELECT * FROM Enrollments WHERE student_id = ? AND subject_id = ?", (s_db_id, subject_id))
            if not cursor.fetchone():
                cursor.execute("INSERT INTO Enrollments (student_id, subject_id) VALUES (?, ?)", (s_db_id, subject_id))
                enr_s += 1
        conn.commit()
    return new_s, enr_s

def get_enrolled_student_ids(subject_id):
    db_path = get_db_path()
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT Students.student_id FROM Enrollments 
            JOIN Students ON Enrollments.student_id = Students.student_id 
            WHERE Enrollments.subject_id = ?
        ''', (subject_id,))
        return {int(row[0]) for row in cursor.fetchall()}

def add_student_manual(uid, name, email, subject_id):
    db_path = get_db_path()
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT student_id FROM Students WHERE university_id = ?", (uid,))
        res = cursor.fetchone()
        if res:
            s_db_id = res[0]
            if email:  # Update email if provided
                cursor.execute("UPDATE Students SET email = ? WHERE student_id = ?", (email, s_db_id))
        else:
            cursor.execute("INSERT INTO Students (university_id, name, email) VALUES (?, ?, ?)", (uid, name, email))
            s_db_id = cursor.lastrowid
            
        cursor.execute("SELECT * FROM Enrollments WHERE student_id = ? AND subject_id = ?", (s_db_id, subject_id))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO Enrollments (student_id, subject_id) VALUES (?, ?)", (s_db_id, subject_id))
            return True # Newly enrolled
        return False # Already enrolled

def delete_student_completely(student_db_id):
    """
    Deletes all traces of a student from the database and dataset.
    This includes: Attendance records, Enrollments, the Student record, and all dataset images.
    Returns the list of subject_ids they were enrolled in so the models can be re-trained.
    """
    import glob
    db_path = get_db_path()
    subject_ids = []
    
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        # Find which subjects they were in (to trigger retrain later)
        cursor.execute("SELECT subject_id FROM Enrollments WHERE student_id = ?", (student_db_id,))
        subject_ids = [row[0] for row in cursor.fetchall()]
        
        # 1. Delete Attendance
        cursor.execute('''
            DELETE FROM Attendance 
            WHERE enrollment_id IN (SELECT enrollment_id FROM Enrollments WHERE student_id = ?)
        ''', (student_db_id,))
        
        # 2. Delete Enrollments
        cursor.execute("DELETE FROM Enrollments WHERE student_id = ?", (student_db_id,))
        
        # 3. Delete Student Record
        cursor.execute("DELETE FROM Students WHERE student_id = ?", (student_db_id,))
        
        conn.commit()

    # 4. Delete physical images
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dataset_dir = os.path.join(base_dir, "dataset")
    pattern = os.path.join(dataset_dir, f"User.{student_db_id}.*.jpg")
    for file_path in glob.glob(pattern):
        try:
            os.remove(file_path)
        except Exception as e:
            print(f"Failed to delete {file_path}: {e}")

    return subject_ids

def delete_subject(subject_id):
    """
    Deletes a subject and its related records (Enrollments, Attendance).
    Also deletes the trained model for the subject.
    """
    import glob
    db_path = get_db_path()
    
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        # 1. Delete Attendance for all enrollments in this subject
        cursor.execute('''
            DELETE FROM Attendance 
            WHERE enrollment_id IN (SELECT enrollment_id FROM Enrollments WHERE subject_id = ?)
        ''', (subject_id,))
        
        # 2. Delete Enrollments
        cursor.execute("DELETE FROM Enrollments WHERE subject_id = ?", (subject_id,))
        
        # 3. Delete Subject
        cursor.execute("DELETE FROM Subjects WHERE subject_id = ?", (subject_id,))
        
        conn.commit()

    # 4. Delete trained model for this subject
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    models_dir = os.path.join(base_dir, "models")
    pattern = os.path.join(models_dir, f"trainer_ID{subject_id}_*.pkl")
    for file_path in glob.glob(pattern):
        try:
            os.remove(file_path)
        except Exception as e:
            print(f"Failed to delete model {file_path}: {e}")