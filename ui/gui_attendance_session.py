import os
import customtkinter as ctk
import sqlite3
import cv2
import numpy as np
from datetime import datetime
from tkinter import messagebox
import glob
import sys

# Import common preprocessing function to ensure consistency with training phase
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.append(root_dir)
from services.face_service import preprocess_face

# --- Recognition Constants --------------------------------------------------------
CONFIDENCE_THRESHOLD = 70   # Confidence threshold (lower is stricter/more accurate)
REQUIRED_VOTES = 5           # Number of consecutive frames required to confirm recognition

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

        student_dict = {int(row[0]): row[2] for row in enrolled_students}
        previously_attended = set()
        cursor.execute('''
            SELECT e.student_id FROM Attendance a
            JOIN Enrollments e ON a.enrollment_id = e.enrollment_id
            WHERE e.subject_id = ? AND a.date = ? AND a.status = 'Present' AND a.week_number = ?
        ''', (subject_id, today_date, week_number))
        for row in cursor.fetchall(): previously_attended.add(int(row[0]))

        attended_today = set()
        vote_counter = {}  # {db_student_id: number of correct frames}
        cam = cv2.VideoCapture(1)
        cam.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        while True:
            ret, img = cam.read()
            if not ret: break
            h_img, w_img = img.shape[:2]
            blob = cv2.dnn.blobFromImage(cv2.resize(img, (300, 300)), 1.0, (300, 300), (104.0, 177.0, 123.0))
            net.setInput(blob)
            detections = net.forward()
            for i in range(0, detections.shape[2]):
                confidence = detections[0, 0, i, 2]
                if confidence > 0.3:
                    box = detections[0, 0, i, 3:7] * np.array([w_img, h_img, w_img, h_img])
                    (startX, startY, endX, endY) = box.astype("int")
                    startX, startY = max(0, startX), max(0, startY)
                    endX, endY = min(w_img, endX), min(h_img, endY)
                    
                    # -- Debug: Always draw a white rectangle to confirm the camera detected a face --
                    cv2.rectangle(img, (startX, startY), (endX, endY), (255, 255, 255), 1)

                    face_roi = img[startY:endY, startX:endX]
                    if face_roi.size == 0: continue
                    gray_face = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)

                    # --- Apply same preprocessing as training (Resize + CLAHE) -----------------
                    gray_face = preprocess_face(gray_face)

                    predicted_id, lbph_confidence = recognizer.predict(gray_face)

                    if lbph_confidence < CONFIDENCE_THRESHOLD:
                        if predicted_id in student_dict:
                            name = student_dict[predicted_id]
                            # --- Multi-frame voting system --------------------------
                            if predicted_id not in attended_today and predicted_id not in previously_attended:
                                # Increase vote count
                                vote_counter[predicted_id] = vote_counter.get(predicted_id, 0) + 1
                                votes = vote_counter[predicted_id]
                                # Show progress bar
                                progress = int((votes / REQUIRED_VOTES) * (endX - startX))
                                cv2.rectangle(img, (startX, endY + 4), (startX + progress, endY + 12), (0, 200, 255), -1)
                                cv2.putText(img, f"{name} ({votes}/{REQUIRED_VOTES})",
                                            (startX, startY - 10), 0, 0.7, (0, 200, 255), 2)
                                cv2.rectangle(img, (startX, startY), (endX, endY), (0, 200, 255), 2)
                                if votes >= REQUIRED_VOTES:
                                    attended_today.add(predicted_id)
                                    vote_counter[predicted_id] = 0  # Reset counter
                            elif predicted_id in previously_attended:
                                cv2.rectangle(img, (startX, startY), (endX, endY), (255, 255, 0), 2)
                                cv2.putText(img, f"{name} (Already Present)", (startX, startY-10), 0, 0.7, (255, 255, 0), 2)
                            else:
                                # Attendance recorded in this session
                                cv2.rectangle(img, (startX, startY), (endX, endY), (0, 255, 0), 2)
                                cv2.putText(img, f"{name} (Done)", (startX, startY-10), 0, 0.8, (0, 255, 0), 2)
                        else:
                            # Face known to AI but not enrolled in this subject!
                            cv2.rectangle(img, (startX, startY), (endX, endY), (0, 165, 255), 2)
                            cv2.putText(img, f"Not in class ID:{predicted_id}", (startX, startY-10), 0, 0.6, (0, 165, 255), 2)
                    else:
                        cv2.rectangle(img, (startX, startY), (endX, endY), (0, 0, 255), 2)
                        cv2.putText(img, f"? ({lbph_confidence:.0f})", (startX, startY-10), 0, 0.6, (0, 0, 255), 2)
            
            # -- Show text to confirm camera is reading frames --
            cv2.putText(img, "Scanning... Please wait", (10, 30), 0, 0.7, (0, 255, 0), 2)
            cv2.imshow('Yoklama Sistemi', img)
            if cv2.waitKey(10) & 0xFF == 27: break
        cam.release(); cv2.destroyAllWindows()
        
        for student in enrolled_students:
            db_student_id = student[0]
            status = "Present" if (db_student_id in previously_attended or db_student_id in attended_today) else "Absent"
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