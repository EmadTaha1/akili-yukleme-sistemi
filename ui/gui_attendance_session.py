import os
import customtkinter as ctk
import sqlite3
import cv2
import numpy as np
from datetime import datetime
from tkinter import messagebox
import glob

def get_db_path():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, "database", "attendance_system.db")

def get_subjects_from_db():
    try:
        with sqlite3.connect(get_db_path()) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT subject_id, course_code, subject_name, study_year FROM Subjects")
            rows = cursor.fetchall()
            return [f"{row[0]} - [{row[1]}] {row[2]} ({row[3]})" for row in rows]
    except Exception:
        return []

def find_model_file(base_dir, subject_id):
    """Finds a model file starting with trainer_ID{subject_id}_."""
    pattern = os.path.join(base_dir, "models", f"trainer_ID{subject_id}_*.yml")
    files = glob.glob(pattern)
    return files[0] if files else None

def start_attendance_session(subject_selection, week_selection):
    if not subject_selection or "No" in subject_selection or subject_selection == "Ders Seçin":
        messagebox.showerror("Error", "Please select a valid subject first!")
        return

    subject_id = int(subject_selection.split(" - ")[0])
    # Extract number from "1. Hafta"
    week_number = int(week_selection.split(".")[0])
    today_date = datetime.now().strftime("%Y-%m-%d")
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    model_path = find_model_file(base_dir, subject_id)
    
    if not model_path:
        messagebox.showerror("Error", "No AI model found for this subject. Please train it first.")
        return
        
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    try:
        recognizer.read(model_path)
    except:
        messagebox.showerror("Error", "Failed to load the AI model.")
        return

    prototxt_path = os.path.join(base_dir, "models", "dnn_model", "deploy.prototxt")
    dnn_model_path = os.path.join(base_dir, "models", "dnn_model", "res10_300x300_ssd_iter_140000.caffemodel")
    try:
        net = cv2.dnn.readNetFromCaffe(prototxt_path, dnn_model_path)
    except:
        messagebox.showerror("Error", "DNN models not found.")
        return
    
    with sqlite3.connect(get_db_path()) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT Students.student_id, Students.university_id, Students.name 
            FROM Enrollments 
            JOIN Students ON Enrollments.student_id = Students.student_id 
            WHERE Enrollments.subject_id = ?
        ''', (subject_id,))
        enrolled_students = cursor.fetchall()
        
        if not enrolled_students:
            messagebox.showwarning("Warning", "No students enrolled.")
            return

        student_dict = {int(row[1]): row[2] for row in enrolled_students}
        previously_attended = set()
        cursor.execute('''
            SELECT s.university_id FROM Attendance a
            JOIN Enrollments e ON a.enrollment_id = e.enrollment_id
            JOIN Students s ON e.student_id = s.student_id
            WHERE e.subject_id = ? AND a.date = ? AND a.status = 'Present' AND a.week_number = ?
        ''', (subject_id, today_date, week_number))
        for row in cursor.fetchall(): previously_attended.add(int(row[0]))

        attended_today = set()
        cam = cv2.VideoCapture(0)
        while True:
            ret, img = cam.read()
            if not ret: break
            h_img, w_img = img.shape[:2]
            blob = cv2.dnn.blobFromImage(cv2.resize(img, (300, 300)), 1.0, (300, 300), (104.0, 177.0, 123.0))
            net.setInput(blob)
            detections = net.forward()
            for i in range(0, detections.shape[2]):
                confidence = detections[0, 0, i, 2]
                if confidence > 0.5:
                    box = detections[0, 0, i, 3:7] * np.array([w_img, h_img, w_img, h_img])
                    (startX, startY, endX, endY) = box.astype("int")
                    startX, startY = max(0, startX), max(0, startY)
                    endX, endY = min(w_img, endX), min(h_img, endY)
                    face_roi = img[startY:endY, startX:endX]
                    if face_roi.size == 0: continue
                    gray_face = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
                    predicted_id, lbph_confidence = recognizer.predict(gray_face)
                    if lbph_confidence < 65:
                        if predicted_id in student_dict:
                            name = student_dict[predicted_id]
                            if predicted_id in previously_attended:
                                cv2.rectangle(img, (startX, startY), (endX, endY), (255, 255, 0), 2)
                                cv2.putText(img, f"{name} (Tamam)", (startX, startY-10), 0, 0.7, (255, 255, 0), 2)
                            else:
                                attended_today.add(predicted_id)
                                cv2.rectangle(img, (startX, startY), (endX, endY), (0, 255, 0), 2)
                                cv2.putText(img, f"{name} (Burada)", (startX, startY-10), 0, 0.8, (0, 255, 0), 2)
                    else:
                        cv2.rectangle(img, (startX, startY), (endX, endY), (0, 0, 255), 2)
            cv2.imshow('Yoklama Sistemi', img)
            if cv2.waitKey(10) & 0xFF == 27: break
        cam.release(); cv2.destroyAllWindows()
        
        for student in enrolled_students:
            db_student_id, uni_id = student[0], int(student[1])
            status = "Present" if (uni_id in previously_attended or uni_id in attended_today) else "Absent"
            cursor.execute("SELECT enrollment_id FROM Enrollments WHERE student_id=? AND subject_id=?", (db_student_id, subject_id))
            enrollment_id = cursor.fetchone()[0]
            cursor.execute("SELECT attendance_id, status FROM Attendance WHERE enrollment_id=? AND date=? AND week_number=?", (enrollment_id, today_date, week_number))
            exist = cursor.fetchone()
            if exist:
                if exist[1] == "Absent" and status == "Present":
                    cursor.execute("UPDATE Attendance SET status=? WHERE attendance_id=?", (status, exist[0]))
            else:
                cursor.execute("INSERT INTO Attendance (enrollment_id, date, week_number, status) VALUES (?, ?, ?, ?)", (enrollment_id, today_date, week_number, status))
        conn.commit()
    messagebox.showinfo("Session Ended", "Attendance synced.")

def open_attendance_window(master=None):
    if master:
        app = ctk.CTkToplevel(master)
        app.grab_set()
    else:
        ctk.set_appearance_mode("Dark")
        app = ctk.CTk()
    
    app.geometry("500x450")
    app.title("Günlük Yoklama")
    ctk.CTkLabel(app, text="Ders Yoklamasını Başlat", font=("Arial", 22, "bold")).pack(pady=20)
    subjects = get_subjects_from_db()
    subject_dropdown = ctk.CTkComboBox(app, values=subjects if subjects else ["No subjects found"], width=350)
    subject_dropdown.pack(pady=5); subject_dropdown.set(subjects[0] if subjects else "Ders Seçin")
    weeks = [f"{i}. Hafta" for i in range(1, 15)]
    week_dropdown = ctk.CTkComboBox(app, values=weeks, width=350)
    week_dropdown.pack(pady=5); week_dropdown.set("1. Hafta")
    ctk.CTkButton(app, text="Kamerayı Başlat", command=lambda: start_attendance_session(subject_dropdown.get(), week_dropdown.get()), width=350, height=40).pack(pady=30)
    if not master: app.mainloop()

if __name__ == "__main__":
    open_attendance_window()