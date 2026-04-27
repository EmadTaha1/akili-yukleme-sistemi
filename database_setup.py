import sqlite3

def setup_database():
    # الاتصال بقاعدة البيانات (سيقوم بإنشائها إذا لم تكن موجودة)
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()

    # إنشاء جدول الطلاب
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Students (
            student_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            total_absences INTEGER DEFAULT 0,
            status TEXT DEFAULT 'Active'
        )
    ''')

    # إنشاء جدول سجل الحضور
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Attendance_Log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            status TEXT NOT NULL,
            FOREIGN KEY (student_id) REFERENCES Students (student_id)
        )
    ''')

    conn.commit()
    conn.close()
    print("Database and tables created successfully.")

if __name__ == "__main__":
    setup_database()