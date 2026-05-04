import customtkinter as ctk
from tkinter import messagebox, filedialog
import cv2
import numpy as np
import os
import sys

# Ensure Python can find the 'services' folder from the root directory
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(base_dir)

from services import db_service

# --- LOGIC FUNCTIONS ---

def capture_face_dataset(uni_id):
    """Deep Learning (DNN) logic to capture 100 face samples."""
    cam = cv2.VideoCapture(0)
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    
    # Use absolute paths for DNN models to avoid relative path crashes
    prototxt_path = os.path.join(base_dir, "dnn_model", "deploy.prototxt")
    model_path = os.path.join(base_dir, "dnn_model", "res10_300x300_ssd_iter_140000.caffemodel")
    dataset_path = os.path.join(base_dir, "dataset")

    try:
        net = cv2.dnn.readNetFromCaffe(prototxt_path, model_path)
    except Exception:
        messagebox.showerror("Error", "DNN model files missing in 'dnn_model' directory.")
        return False
    
    if not os.path.exists(dataset_path):
        os.makedirs(dataset_path)

    count = 0
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
                cv2.rectangle(img, (startX, startY), (endX, endY), (255, 0, 0), 2)
                
                count += 1
                cv2.imwrite(os.path.join(dataset_path, f"User.{uni_id}.{count}.jpg"), gray_face)
                if count >= 100: break
                
        cv2.imshow('DNN Face Capture - Look at the camera', img)
        if cv2.waitKey(10) & 0xFF == 27 or count >= 100:
            break

    cam.release()
    cv2.destroyAllWindows()
    return count >= 100

def load_subjects(dropdown_ui):
    """Loads subjects from DB Service into a UI dropdown."""
    subjects = db_service.get_subjects()
    if subjects:
        formatted_subjects = [f"{row[0]} - [{row[1]}] {row[2]}" for row in subjects]
        dropdown_ui.configure(values=formatted_subjects)
        dropdown_ui.set(formatted_subjects[0])
    else:
        dropdown_ui.configure(values=["No subjects found"])
        dropdown_ui.set("No subjects found")

def handle_search(search_entry, subject_dropdown, result_dropdown):
    """Executes the strict search using db_service."""
    query = search_entry.get()
    subject_selection = subject_dropdown.get()

    if " - " not in subject_selection:
        messagebox.showwarning("Warning", "Please select a valid subject first!")
        return

    subject_id = int(subject_selection.split(" - ")[0])
    # Call the new strict search function
    results = db_service.search_enrolled_students(subject_id, query)

    if results:
        # Expected Format from DB: "DB_ID | UNI_ID | NAME"
        result_dropdown.configure(values=results)
        result_dropdown.set(results[0])
    else:
        result_dropdown.configure(values=["No results found in this subject"])
        result_dropdown.set("No results found in this subject")

def handle_capture_and_link(subject_dropdown, student_dropdown):
    """Handles logic for checking face data and opening camera."""
    subject_selection = subject_dropdown.get()
    student_selection = student_dropdown.get()

    if " - " not in subject_selection or " | " not in student_selection:
        messagebox.showerror("Error", "Invalid Subject or Student selection. Search first.")
        return

    subject_id = int(subject_selection.split(" - ")[0])
    parts = student_selection.split(" | ")
    student_db_id = int(parts[0])
    uni_id = int(parts[1])
    student_name = parts[2]

    has_face, _ = db_service.get_student_status(student_db_id, subject_id)

    if has_face:
        messagebox.showinfo("Info", f"{student_name} already has a face print registered. No action needed.")
    else:
        messagebox.showinfo("Camera Ready", f"No face data found for '{student_name}'.\nPress OK to open the camera and take 100 samples.")
        success = capture_face_dataset(uni_id)
        
        if success:
            db_service.update_student_face_path(student_db_id, uni_id)
            messagebox.showinfo("Success", f"Face captured and system updated for '{student_name}'!")
        else:
            messagebox.showerror("Error", "Face capture failed or was cancelled.")

def handle_excel_upload(subject_dropdown):
    """Handles Excel file upload logic."""
    subject_selection = subject_dropdown.get()
    if " - " not in subject_selection:
        messagebox.showerror("Error", "Please select a valid subject first!")
        return

    subject_id = int(subject_selection.split(" - ")[0])
    
    file_path = filedialog.askopenfilename(
        title="Select Excel/CSV File",
        filetypes=[("Excel files", "*.xlsx *.xls"), ("CSV files", "*.csv")]
    )
    
    if not file_path:
        return

    try:
        new_students, enrolled_students = db_service.process_excel_upload(file_path, subject_id)
        messagebox.showinfo("Upload Complete", 
                            f"File processed successfully!\n\n"
                            f"New Students Created: {new_students}\n"
                            f"Students Enrolled in Subject: {enrolled_students}")
    except Exception as e:
        messagebox.showerror("Upload Error", f"Failed to process file:\n{str(e)}")

# --- UI CLASS ---

class StudentEnrollmentWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.geometry("600x600")
        self.title("Student Setup (Clean Architecture)")
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        title_label = ctk.CTkLabel(self, text="Student Management", font=("Arial", 22, "bold"))
        title_label.pack(pady=20)

        # Tab View Structure
        self.tabview = ctk.CTkTabview(self, width=550, height=450)
        self.tabview.pack(padx=20, pady=10)
        
        self.tabview.add("Face Capture")
        self.tabview.add("Excel Upload")

        self.setup_capture_tab()
        self.setup_excel_tab()

    def setup_capture_tab(self):
        tab = self.tabview.tab("Face Capture")

        # Subject Selection
        subject_label = ctk.CTkLabel(tab, text="1. Select Subject:")
        subject_label.pack(pady=(10, 0))
        self.capture_subject_dropdown = ctk.CTkComboBox(tab, width=350)
        self.capture_subject_dropdown.pack(pady=5)
        load_subjects(self.capture_subject_dropdown)

        # Search Frame
        search_frame = ctk.CTkFrame(tab)
        search_frame.pack(pady=20, padx=20, fill="x")
        
        search_label = ctk.CTkLabel(search_frame, text="2. Search Enrolled Student (Name/ID):")
        search_label.pack(pady=5)
        
        self.search_entry = ctk.CTkEntry(search_frame, placeholder_text="Type ID or Name...", width=250)
        self.search_entry.pack(side="left", padx=(20, 10), pady=10)
        
        self.result_dropdown = ctk.CTkComboBox(tab, values=["Awaiting search..."], width=350)

        search_btn = ctk.CTkButton(search_frame, text="Search", width=80, 
                                   command=lambda: handle_search(self.search_entry, self.capture_subject_dropdown, self.result_dropdown))
        search_btn.pack(side="left", padx=10, pady=10)

        # Result Selection
        res_label = ctk.CTkLabel(tab, text="3. Select Student from Results:")
        res_label.pack(pady=(10, 0))
        self.result_dropdown.pack(pady=5)

        # Process Button
        process_btn = ctk.CTkButton(tab, text="Capture Face Print", fg_color="#C85000", hover_color="#9c3e00", width=350, height=40,
                                    command=lambda: handle_capture_and_link(self.capture_subject_dropdown, self.result_dropdown))
        process_btn.pack(pady=30)

    def setup_excel_tab(self):
        tab = self.tabview.tab("Excel Upload")

        info_label = ctk.CTkLabel(tab, text="Bulk Enroll Students via Excel/CSV", font=("Arial", 16, "bold"))
        info_label.pack(pady=20)

        # Subject Selection
        subject_label = ctk.CTkLabel(tab, text="Select Subject to Enroll Students Into:")
        subject_label.pack(pady=(10, 0))
        self.excel_subject_dropdown = ctk.CTkComboBox(tab, width=350)
        self.excel_subject_dropdown.pack(pady=5)
        load_subjects(self.excel_subject_dropdown)

        upload_btn = ctk.CTkButton(tab, text="Browse & Upload Excel", fg_color="#107C41", hover_color="#0B5A2F", width=350, height=40,
                                   command=lambda: handle_excel_upload(self.excel_subject_dropdown))
        upload_btn.pack(pady=40)

if __name__ == "__main__":
    app = StudentEnrollmentWindow()
    app.mainloop()