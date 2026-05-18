import sqlite3
import os
from datetime import datetime, timedelta

def get_db_path():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, "database", "attendance_system.db")

def get_dashboard_stats(teacher_id):
    """Fetch quick statistics for the dashboard cards."""
    stats = {
        "total_subjects": 0,
        "total_students": 0,
        "today_attendance": "0/0",
        "last_session": "Yok"
    }
    
    try:
        with sqlite3.connect(get_db_path()) as conn:
            cursor = conn.cursor()
            
            # 1. Total Subjects
            cursor.execute("SELECT COUNT(*) FROM Subjects WHERE teacher_id = ?", (teacher_id,))
            stats["total_subjects"] = cursor.fetchone()[0]
            
            # 2. Total Students Enrolled across all subjects of this teacher
            cursor.execute('''
                SELECT COUNT(DISTINCT e.student_id) 
                FROM Enrollments e
                JOIN Subjects s ON e.subject_id = s.subject_id
                WHERE s.teacher_id = ?
            ''', (teacher_id,))
            stats["total_students"] = cursor.fetchone()[0]
            
            # 3. Today's Attendance (Present / Total expected for sessions held today)
            today = datetime.now().strftime("%Y-%m-%d")
            # First, find total enrolled students in subjects that had attendance taken today
            cursor.execute('''
                SELECT e.enrollment_id 
                FROM Attendance a
                JOIN Enrollments e ON a.enrollment_id = e.enrollment_id
                JOIN Subjects s ON e.subject_id = s.subject_id
                WHERE s.teacher_id = ? AND a.date = ?
            ''', (teacher_id, today))
            today_records = cursor.fetchall()
            
            if today_records:
                total_expected = len(today_records)
                # Now count how many were present
                cursor.execute('''
                    SELECT COUNT(*) 
                    FROM Attendance a
                    JOIN Enrollments e ON a.enrollment_id = e.enrollment_id
                    JOIN Subjects s ON e.subject_id = s.subject_id
                    WHERE s.teacher_id = ? AND a.date = ? AND a.status = 'Present'
                ''', (teacher_id, today))
                present_count = cursor.fetchone()[0]
                stats["today_attendance"] = f"{present_count}/{total_expected}"
            
            # 4. Last Session Date
            cursor.execute('''
                SELECT MAX(a.date) 
                FROM Attendance a
                JOIN Enrollments e ON a.enrollment_id = e.enrollment_id
                JOIN Subjects s ON e.subject_id = s.subject_id
                WHERE s.teacher_id = ?
            ''', (teacher_id,))
            last_date = cursor.fetchone()[0]
            if last_date:
                stats["last_session"] = last_date
                
    except Exception as e:
        print(f"Stats Error: {e}")
        
    return stats

def get_attendance_chart_data(teacher_id):
    """
    Fetch attendance rate for the last 4 weeks across the teacher's subjects.
    Returns: {"labels": ["Week X", ...], "rates": [85.5, ...]}
    """
    data = {"labels": [], "rates": []}
    
    try:
        with sqlite3.connect(get_db_path()) as conn:
            cursor = conn.cursor()
            
            # Get the distinct weeks where attendance was taken
            cursor.execute('''
                SELECT DISTINCT a.week_number
                FROM Attendance a
                JOIN Enrollments e ON a.enrollment_id = e.enrollment_id
                JOIN Subjects s ON e.subject_id = s.subject_id
                WHERE s.teacher_id = ?
                ORDER BY a.week_number DESC
                LIMIT 4
            ''', (teacher_id,))
            
            recent_weeks = [row[0] for row in cursor.fetchall()]
            recent_weeks.reverse() # Oldest to newest
            
            for week in recent_weeks:
                # Total records for this week
                cursor.execute('''
                    SELECT COUNT(*)
                    FROM Attendance a
                    JOIN Enrollments e ON a.enrollment_id = e.enrollment_id
                    JOIN Subjects s ON e.subject_id = s.subject_id
                    WHERE s.teacher_id = ? AND a.week_number = ?
                ''', (teacher_id, week))
                total = cursor.fetchone()[0]
                
                # Present records for this week
                cursor.execute('''
                    SELECT COUNT(*)
                    FROM Attendance a
                    JOIN Enrollments e ON a.enrollment_id = e.enrollment_id
                    JOIN Subjects s ON e.subject_id = s.subject_id
                    WHERE s.teacher_id = ? AND a.week_number = ? AND a.status = 'Present'
                ''', (teacher_id, week))
                present = cursor.fetchone()[0]
                
                rate = (present / total * 100) if total > 0 else 0
                data["labels"].append(f"{week}. Hafta")
                data["rates"].append(round(rate, 1))
                
    except Exception as e:
        print(f"Chart Data Error: {e}")
        
    return data


class LiveSessionStats:
    """
    Tracks and aggregates real-time statistics during a live attendance tracking session.
    Calculates FPS averages, recognition accuracy rates, attendee proportions, and elapsed duration.
    """
    def __init__(self, total_students):
        import time
        self.total_students = total_students
        self.start_time = time.time()
        self.attended_count = 0
        self.fps_list = []
        self.recognition_attempts = 0
        self.successful_recognitions = 0
        self.unknown_faces = 0

    def record_fps(self, fps):
        self.fps_list.append(fps)
        if len(self.fps_list) > 100:
            self.fps_list.pop(0)

    def record_recognition(self, success):
        self.recognition_attempts += 1
        if success:
            self.successful_recognitions += 1

    def record_unknown(self):
        self.unknown_faces += 1

    def record_attendance(self):
        self.attended_count += 1

    def get_current_stats(self):
        import time
        elapsed = time.time() - self.start_time
        accuracy = (self.successful_recognitions / self.recognition_attempts * 100) if self.recognition_attempts > 0 else 100.0
        attendance_rate = (self.attended_count / self.total_students * 100) if self.total_students > 0 else 0.0
        return {
            "attended": self.attended_count,
            "total": self.total_students,
            "recognition_accuracy": round(accuracy, 1),
            "unknown_faces": self.unknown_faces,
            "elapsed_seconds": elapsed,
            "attendance_rate": round(attendance_rate, 1)
        }

