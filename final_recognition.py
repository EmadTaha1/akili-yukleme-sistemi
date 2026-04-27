import cv2
import pyttsx3
import random
import time
import datetime
import sqlite3
import os
import sys

# ==========================================
# 0. Smart Path Logic (For EXE Support)
# ==========================================
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# ==========================================
# 1. Setup Audio Engine
# ==========================================
engine = pyttsx3.init()
engine.setProperty("rate", 145)

# ==========================================
# 2. Load Classifiers (Using Smart Paths)
# ==========================================
faceCascade = cv2.CascadeClassifier(resource_path("haarcascade_frontalface_default.xml"))
smileCascade = cv2.CascadeClassifier(resource_path("haarcascade_smile.xml"))
eyeCascade = cv2.CascadeClassifier(resource_path("haarcascade_eye.xml"))

recognizer = cv2.face.LBPHFaceRecognizer_create()
# التحقق من وجود ملف المدرب قبل القراءة
trainer_path = resource_path("trainer.yml")
if os.path.exists(trainer_path):
    recognizer.read(trainer_path)
else:
    print(f"[ERROR] Trainer file not found at: {trainer_path}")

# ==========================================
# 3. Database Functions
# ==========================================
def get_student_info(student_id):
    """Fetch student name and status from the SQLite database."""
    try:
        conn = sqlite3.connect(resource_path('attendance.db'))
        cursor = conn.cursor()
        cursor.execute("SELECT name, status FROM Students WHERE student_id = ?", (student_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return result[0], result[1]
        else:
            return "Not Registered", "Unknown"
    except Exception as e:
        print(f"[ERROR] DB Read Error: {e}")
        return "Unknown", "Error"

def mark_attendance_db(student_id):
    """Insert attendance record into the database."""
    try:
        conn = sqlite3.connect(resource_path('attendance.db'))
        cursor = conn.cursor()
        today_date = datetime.datetime.now().strftime("%Y-%m-%d")
        current_time = datetime.datetime.now().strftime("%H:%M:%S")

        cursor.execute("SELECT * FROM Attendance_Log WHERE student_id = ? AND date = ?", (student_id, today_date))
        if cursor.fetchone():
            conn.close()
            return False

        cursor.execute("INSERT INTO Attendance_Log (student_id, date, time, status) VALUES (?, ?, ?, ?)",
                       (student_id, today_date, current_time, 'Present'))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[ERROR] DB Write Error: {e}")
        return False

# ==========================================
# 4. Logic Variables
# ==========================================
challenges = ["SMILE", "BLINK"]
current_challenge = random.choice(challenges)
blink_count = 0
eye_closed = False
recorded_names = []
last_record_time = 0 

# Camera Setup (DroidCam = 1)
cam = cv2.VideoCapture(0)
#cam = cv2.VideoCapture(0, cv2.CAP_DSHOW)    

print(f"\n[SYSTEM] Continuous Mode Active. Current Challenge: {current_challenge}")

while True:
    ret, img = cam.read()
    if not ret: break
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = faceCascade.detectMultiScale(gray, 1.2, 5)

    status_ready = True if (time.time() - last_record_time > 5) else False

    for x, y, w, h in faces:
        roi_gray = gray[y : y + h, x : x + w]
        
        # 1. Predict
        id_num, confidence = recognizer.predict(roi_gray)

        # 2. Threshold Logic
        if confidence < 75:  
            user_name, user_status = get_student_info(id_num)
            conf_percent = round(100 - confidence)
            display_text = f"{user_name} ({conf_percent}%)"
            is_identified = True
        elif confidence < 90: 
            user_name, user_status = get_student_info(id_num)
            display_text = f"{user_name} (Verifying...)"
            is_identified = True
        else: 
            user_name = "Unknown"
            user_status = "Unknown"
            display_text = "Unknown Person"
            is_identified = False

        if user_status == 'Deprived':
            color = (0, 0, 255) 
            cv2.rectangle(img, (x, y), (x + w, y + h), color, 2)
            cv2.putText(img, f"{user_name}: DEPRIVED", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            continue 

        is_verified = False

        if is_identified:
            if user_name in recorded_names and not status_ready:
                color = (0, 0, 0)
                display_text = "Attendance Recorded"
            else:
                if current_challenge == "SMILE":
                    smiles = smileCascade.detectMultiScale(roi_gray, 1.8, 20)
                    if len(smiles) > 0: is_verified = True
                elif current_challenge == "BLINK":
                    eyes = eyeCascade.detectMultiScale(roi_gray, 1.1, 10)
                    if len(eyes) == 0:
                        eye_closed = True
                    else:
                        if eye_closed:
                            blink_count += 1
                            eye_closed = False
                    if blink_count >= 2: is_verified = True

                color = (0, 255, 0) if is_verified else (255, 255, 0)
                if not is_verified: display_text = f"Action: {current_challenge}"
                else: display_text = "VERIFIED"

                if is_verified:
                    if mark_attendance_db(id_num):
                        engine.say(f"Welcome {user_name}")
                        engine.runAndWait()
                    
                    recorded_names.append(user_name)
                    last_record_time = time.time()
                    current_challenge = random.choice(challenges)
                    blink_count = 0
        else:
            color = (0, 165, 255) 

        cv2.rectangle(img, (x, y), (x + w, y + h), color, 2)
        cv2.putText(img, display_text, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

    cv2.imshow("BITIRME PROJESI - SMART ATTENDANCE", img)
    if cv2.waitKey(10) & 0xFF == ord("q"):
        break

cam.release()
cv2.destroyAllWindows()