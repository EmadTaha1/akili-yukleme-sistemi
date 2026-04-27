import cv2
import os
import sys
import customtkinter as ctk
from tkinter import messagebox
import sqlite3
import numpy as np
from PIL import Image

# ==========================================
# 0. Smart Path Logic (البوصلة الهندسية)
# ==========================================
def resource_path(relative_path):
    """ الحصول على المسار الصحيح سواء في بيئة التطوير أو داخل الـ EXE """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class FaceTrainerGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Face Registration System")
        self.geometry("450x400")
        
        # UI Elements
        self.label = ctk.CTkLabel(self, text="Student Registration (Live Camera)", font=("Arial", 20, "bold"))
        self.label.pack(pady=20)

        self.id_entry = ctk.CTkEntry(self, placeholder_text="Enter Student ID (Numbers only)")
        self.id_entry.pack(pady=10, padx=20, fill="x")

        self.name_entry = ctk.CTkEntry(self, placeholder_text="Enter Student Full Name")
        self.name_entry.pack(pady=10, padx=20, fill="x")

        self.btn_capture = ctk.CTkButton(self, text="Step 1: Capture 100 Photos", command=self.capture_images, fg_color="#2196F3")
        self.btn_capture.pack(pady=10)

        self.btn_train = ctk.CTkButton(self, text="Step 2: Train System", command=self.train_model, fg_color="#4CAF50")
        self.btn_train.pack(pady=10)

        # Create dataset folder if not exists in the correct EXE path
        self.dataset_dir = resource_path("dataset")
        if not os.path.exists(self.dataset_dir):
            os.makedirs(self.dataset_dir)

    def capture_images(self):
        student_id = self.id_entry.get()
        student_name = self.name_entry.get()

        if not student_id or not student_name:
            messagebox.showerror("Error", "Please enter both ID and Name")
            return

        # Save student to database securely
        try:
            db_path = resource_path('attendance.db')
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO Students (student_id, name, status) VALUES (?, ?, ?)", 
                           (student_id, student_name, 'Active'))
            conn.commit()
            conn.close()
        except Exception as e:
            messagebox.showerror("DB Error", f"Could not save to database: {e}")
            return

        # Open DroidCam (Camera 1)
        cam = cv2.VideoCapture(0)
        #cam = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        # Using the local XML file
        xml_path = resource_path("haarcascade_frontalface_default.xml")
        detector = cv2.CascadeClassifier(xml_path)
        
        count = 0
        messagebox.showinfo("Instructions", "Look at the Mobile Camera and move your head slowly. Capturing 100 photos...")

        while True:
            ret, img = cam.read()
            if not ret:
                break
            
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            faces = detector.detectMultiScale(gray, 1.3, 5)

            for (x, y, w, h) in faces:
                count += 1
                # Save the captured image into the correct dataset folder
                img_path = os.path.join(self.dataset_dir, f"User.{student_id}.{count}.jpg")
                cv2.imwrite(img_path, gray[y:y+h, x:x+w])
                cv2.rectangle(img, (x, y), (x+w, y+h), (255, 0, 0), 2)
                cv2.putText(img, f"Captured: {count}/100", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

            cv2.imshow("Capturing Photos - Stay Still", img)

            if cv2.waitKey(1) & 0xFF == ord('q') or count >= 100:
                break

        cam.release()
        cv2.destroyAllWindows()
        messagebox.showinfo("Success", f"Finished! 100 photos captured for {student_name}")

    def train_model(self):
        recognizer = cv2.face.LBPHFaceRecognizer_create()
        xml_path = resource_path("haarcascade_frontalface_default.xml")
        detector = cv2.CascadeClassifier(xml_path)

        def get_images_and_labels(path):
            image_paths = [os.path.join(path, f) for f in os.listdir(path)]
            face_samples = []
            ids = []
            for image_path in image_paths:
                if not image_path.endswith(".jpg"): continue
                
                PIL_img = Image.open(image_path).convert('L')
                img_numpy = np.array(PIL_img, 'uint8')
                id = int(os.path.split(image_path)[-1].split(".")[1])
                faces = detector.detectMultiScale(img_numpy)
                for (x, y, w, h) in faces:
                    face_samples.append(img_numpy[y:y+h, x:x+w])
                    ids.append(id)
            return face_samples, ids

        try:
            faces, ids = get_images_and_labels(self.dataset_dir)
            if len(faces) == 0:
                messagebox.showerror("Error", "No training data found in dataset folder.")
                return
                
            recognizer.train(faces, np.array(ids))
            
            # Save the trained model to the correct local path
            trainer_path = resource_path('trainer.yml')
            recognizer.write(trainer_path)
            messagebox.showinfo("Success", "System Trained Successfully! You can now use the Main Menu.")
        except Exception as e:
            messagebox.showerror("Error", f"Training failed: {e}")

if __name__ == "__main__":
    app = FaceTrainerGUI()
    app.mainloop()