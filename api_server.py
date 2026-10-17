"""
Flask REST API Server
=====================
Provides endpoints for the Flutter mobile teacher app.
Run alongside the desktop app: python api_server.py
"""

import sys
import os
import json
import hashlib
from datetime import datetime

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from flask import Flask, request, jsonify
from flask_cors import CORS

from services import auth_service, db_service, stats_service

app = Flask(__name__)
CORS(app)  # Allow mobile app requests from any origin

# ─────────────────────────────────────────────
# Simple in-memory session store (token → teacher_id)
# ─────────────────────────────────────────────
_sessions: dict[str, dict] = {}


def _make_token(teacher_id: int) -> str:
    """Generate a simple session token."""
    raw = f"{teacher_id}-{datetime.now().isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _get_teacher(request) -> dict | None:
    """Extract and validate the auth token from request headers."""
    token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    return _sessions.get(token)


def ok(data: dict = None, message: str = "success") -> tuple:
    """Standard success response."""
    resp = {"status": "ok", "message": message}
    if data is not None:
        resp.update(data)
    return jsonify(resp), 200


def err(message: str, code: int = 400) -> tuple:
    """Standard error response."""
    return jsonify({"status": "error", "message": message}), code


# ══════════════════════════════════════════════
# AUTH ENDPOINTS
# ══════════════════════════════════════════════

@app.route("/api/login", methods=["POST"])
def login():
    """
    Teacher login.
    Body: { "email": "...", "password": "..." }
    Returns: { "token": "...", "teacher": { "id", "name", "email" } }
    """
    body = request.get_json(silent=True) or {}
    email = body.get("email", "").strip()
    password = body.get("password", "").strip()

    if not email or not password:
        return err("Email and password are required")

    teacher = auth_service.verify_login(email, password)
    if not teacher:
        return err("Invalid email or password", 401)

    token = _make_token(teacher["teacher_id"])
    _sessions[token] = teacher

    return ok({
        "token": token,
        "teacher": {
            "id": teacher["teacher_id"],
            "name": teacher["name"],
            "email": teacher["email"]
        }
    }, "Login successful")


@app.route("/api/logout", methods=["POST"])
def logout():
    """Invalidate session token."""
    token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    _sessions.pop(token, None)
    return ok(message="Logged out")


@app.route("/api/me", methods=["GET"])
def me():
    """Return current teacher info."""
    teacher = _get_teacher(request)
    if not teacher:
        return err("Unauthorized", 401)
    details = auth_service.get_teacher_details(teacher["teacher_id"])
    if not details:
        return err("Teacher not found", 404)
    return ok({"teacher": {
        "id": teacher["teacher_id"],
        "name": details["name"],
        "email": details["email"]
    }})


# ══════════════════════════════════════════════
# DASHBOARD ENDPOINTS
# ══════════════════════════════════════════════

@app.route("/api/dashboard/stats", methods=["GET"])
def dashboard_stats():
    """
    Returns quick statistics for the dashboard:
    total_subjects, total_students, today_attendance, last_session
    """
    teacher = _get_teacher(request)
    if not teacher:
        return err("Unauthorized", 401)

    stats = stats_service.get_dashboard_stats(teacher["teacher_id"])
    chart = stats_service.get_attendance_chart_data(teacher["teacher_id"])

    return ok({"stats": stats, "chart": chart})


# ══════════════════════════════════════════════
# SUBJECTS ENDPOINTS
# ══════════════════════════════════════════════

@app.route("/api/subjects", methods=["GET"])
def get_subjects():
    """
    Returns list of subjects assigned to the logged-in teacher.
    Each subject includes: subject_id, course_code, subject_name
    """
    teacher = _get_teacher(request)
    if not teacher:
        return err("Unauthorized", 401)

    rows = db_service.get_subjects(teacher_id=teacher["teacher_id"])
    subjects = [
        {"id": r[0], "code": r[1], "name": r[2]}
        for r in rows
    ]
    return ok({"subjects": subjects})


@app.route("/api/subjects/<int:subject_id>", methods=["GET"])
def get_subject_detail(subject_id):
    """Returns full details for a specific subject."""
    teacher = _get_teacher(request)
    if not teacher:
        return err("Unauthorized", 401)

    row = db_service.get_subject_details(subject_id)
    if not row:
        return err("Subject not found", 404)

    return ok({"subject": {
        "id": row[0],
        "code": row[1],
        "name": row[2],
        "academic_year": row[3]
    }})


# ══════════════════════════════════════════════
# STUDENTS ENDPOINTS
# ══════════════════════════════════════════════

@app.route("/api/subjects/<int:subject_id>/students", methods=["GET"])
def get_students(subject_id):
    """
    Returns list of students enrolled in a subject.
    Each student: student_id, university_id, name, has_face
    """
    teacher = _get_teacher(request)
    if not teacher:
        return err("Unauthorized", 401)

    rows = db_service.get_students_by_subject(subject_id)
    students = []
    for r in rows:
        has_face, _ = db_service.get_student_status(r[0], subject_id)
        students.append({
            "id": r[0],
            "university_id": r[1],
            "name": r[2],
            "has_face": has_face
        })

    return ok({"students": students, "total": len(students)})


# ══════════════════════════════════════════════
# ATTENDANCE ENDPOINTS
# ══════════════════════════════════════════════

@app.route("/api/subjects/<int:subject_id>/attendance", methods=["GET"])
def get_attendance(subject_id):
    """
    Returns attendance records for a subject.
    Optional query param: ?date=YYYY-MM-DD
    """
    teacher = _get_teacher(request)
    if not teacher:
        return err("Unauthorized", 401)

    date_filter = request.args.get("date")

    import sqlite3
    db_path = db_service.get_db_path()
    records = []

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            if date_filter:
                cursor.execute('''
                    SELECT s.name, s.university_id, a.status, a.date, a.week_number
                    FROM Attendance a
                    JOIN Enrollments e ON a.enrollment_id = e.enrollment_id
                    JOIN Students s ON e.student_id = s.student_id
                    WHERE e.subject_id = ? AND a.date = ?
                    ORDER BY s.name
                ''', (subject_id, date_filter))
            else:
                cursor.execute('''
                    SELECT s.name, s.university_id, a.status, a.date, a.week_number
                    FROM Attendance a
                    JOIN Enrollments e ON a.enrollment_id = e.enrollment_id
                    JOIN Students s ON e.student_id = s.student_id
                    WHERE e.subject_id = ?
                    ORDER BY a.date DESC, s.name
                ''', (subject_id,))

            for row in cursor.fetchall():
                records.append({
                    "student_name": row[0],
                    "university_id": row[1],
                    "status": row[2],
                    "date": row[3],
                    "week": row[4]
                })
    except Exception as e:
        return err(f"Database error: {e}", 500)

    return ok({"records": records, "total": len(records)})


@app.route("/api/subjects/<int:subject_id>/report", methods=["GET"])
def get_subject_report(subject_id):
    """
    Returns attendance summary per student for a subject:
    present count, absent count, attendance rate.
    """
    teacher = _get_teacher(request)
    if not teacher:
        return err("Unauthorized", 401)

    import sqlite3
    db_path = db_service.get_db_path()
    report = []

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT s.name, s.university_id,
                    SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) as present,
                    SUM(CASE WHEN a.status = 'Absent'  THEN 1 ELSE 0 END) as absent,
                    COUNT(*) as total
                FROM Attendance a
                JOIN Enrollments e ON a.enrollment_id = e.enrollment_id
                JOIN Students s ON e.student_id = s.student_id
                WHERE e.subject_id = ?
                GROUP BY s.student_id
                ORDER BY s.name
            ''', (subject_id,))

            for row in cursor.fetchall():
                total = row[4] or 1
                rate = round((row[2] / total) * 100, 1)
                report.append({
                    "student_name": row[0],
                    "university_id": row[1],
                    "present": row[2],
                    "absent": row[3],
                    "total_sessions": total,
                    "attendance_rate": rate
                })
    except Exception as e:
        return err(f"Database error: {e}", 500)

    return ok({"report": report})


# ══════════════════════════════════════════════
# LIVE SESSION STATUS
# ══════════════════════════════════════════════

# Shared dict: the desktop app writes here, mobile app reads
_live_session: dict = {"active": False}


def update_live_session(data: dict):
    """Called by the desktop app to update live session state."""
    global _live_session
    _live_session = data


@app.route("/api/session/status", methods=["GET"])
def session_status():
    """Returns current live session state (read by mobile app)."""
    teacher = _get_teacher(request)
    if not teacher:
        return err("Unauthorized", 401)
    return ok({"session": _live_session})


# ══════════════════════════════════════════════
# HEALTH CHECK
# ══════════════════════════════════════════════

@app.route("/api/ping", methods=["GET"])
def ping():
    """Simple health check endpoint."""
    return ok({"message": "Attendance API is running", "time": datetime.now().isoformat()})


# ══════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════

def run_api(host="0.0.0.0", port=5000, debug=False):
    """Start the Flask API server."""
    print(f"\n[API] Mobile API Server starting on http://{host}:{port}")
    print(f"[API] Ping: http://localhost:{port}/api/ping\n")
    app.run(host=host, port=port, debug=debug, use_reloader=False)


if __name__ == "__main__":
    run_api(debug=True)
