import customtkinter as ctk
from tkinter import messagebox, filedialog
import cv2
import numpy as np
import os
import sys

# Ensure Python can find the 'services' folder from the root directory
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(base_dir)

from services import db_service, model_trainer

def capture_face_dataset(uni_id):
    """Deep Learning (DNN) logic to capture 100 face samples."""
    cam = cv2.VideoCapture(0)
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    
    prototxt_path = os.path.join(base_dir, "models", "dnn_model", "deploy.prototxt")
    model_path = os.path.join(base_dir, "models", "dnn_model", "res10_300x300_ssd_iter_140000.caffemodel")
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
                
        cv2.imshow('Fotoğraf Çekiliyor - Kameraya Bakınız', img)
        if cv2.waitKey(10) & 0xFF == 27 or count >= 100:
            break

    cam.release()
    cv2.destroyAllWindows()
    return count >= 100

def load_subjects(dropdown_ui):
    subjects = db_service.get_subjects()
    if subjects:
        formatted_subjects = [f"{row[0]} - [{row[1]}] {row[2]}" for row in subjects]
        dropdown_ui.configure(values=formatted_subjects)
        dropdown_ui.set(formatted_subjects[0])
    else:
        dropdown_ui.configure(values=["No subjects found"])
        dropdown_ui.set("No subjects found")

def handle_strict_search(search_entry, subject_dropdown, result_dropdown):
    """STRICT SEARCH: Only searches students ALREADY enrolled in the selected subject."""
    query = search_entry.get()
    subject_selection = subject_dropdown.get()

    if " - " not in subject_selection:
        messagebox.showwarning("Warning", "Please select a valid subject first!")
        return

    subject_id = int(subject_selection.split(" - ")[0])
    
    # Using the strict search function from db_service
    results = db_service.search_enrolled_students(subject_id, query)

    if results:
        # Format: DB_ID | UNI_ID | NAME
        formatted_results = [f"{row[0]} | {row[1]} | {row[2]}" for row in results]
        result_dropdown.configure(values=formatted_results)
        result_dropdown.set(formatted_results[0])
    else:
        result_dropdown.configure(values=["Student not found in this subject"])
        result_dropdown.set("Student not found in this subject")

def handle_capture(subject_dropdown, student_dropdown):
    subject_selection = subject_dropdown.get()
    student_selection = student_dropdown.get()

    if " - " not in subject_selection or " | " not in student_selection:
        messagebox.showerror("Error", "Invalid selection. Please search and select a student.")
        return

    subject_id = int(subject_selection.split(" - ")[0])
    parts = student_selection.split(" | ")
    student_db_id = int(parts[0])
    uni_id = int(parts[1])
    student_name = parts[2]

    has_face, _ = db_service.get_student_status(student_db_id, subject_id)

    if has_face:
        messagebox.showinfo("Info", f"{student_name} already has a face print registered in this subject.")
    else:
        messagebox.showinfo("Kamera Hazır", f"'{student_name}' için yüz verisi bulunamadı.\nKamerayı başlatmak için Tamam'a basın.")
        success = capture_face_dataset(uni_id)
        
        if success:
            db_service.update_student_face_path(student_db_id, uni_id)
            # Automate Training
            model_trainer.train_lbph_model(subject_id)
            messagebox.showinfo("Başarılı", f"'{student_name}' için yüz kaydı yapıldı ve sistem otomatik olarak eğitildi!")
        else:
            messagebox.showerror("Hata", "Yüz kaydı başarısız oldu.")

def handle_excel_upload(subject_dropdown):
    subject_selection = subject_dropdown.get()
    if " - " not in subject_selection:
        messagebox.showerror("Error", "Please select a valid subject first!")
        return

    subject_id = int(subject_selection.split(" - ")[0])
    
    file_path = filedialog.askopenfilename(
        title="Select Excel/CSV File",
        filetypes=[("Excel files", "*.xlsx *.xls"), ("CSV files", "*.csv")]
    )
    
    if not file_path: return

    try:
        new_students, enrolled_students = db_service.process_excel_upload(file_path, subject_id)
        messagebox.showinfo("Upload Complete", 
                            f"File processed successfully for this subject!\n\n"
                            f"Students Enrolled: {enrolled_students}")
    except Exception as e:
        messagebox.showerror("Upload Error", f"Failed to process file:\n{str(e)}")


class StudentEnrollmentWindow(ctk.CTkToplevel):
    def __init__(self, master=None):
        super().__init__(master)
        if master:
            self.grab_set() # Focus on this window
        self.geometry("600x600")
        self.title("Öğrenci Kayıt Sistemi")
        if not master:
            ctk.set_appearance_mode("Dark")
            ctk.set_default_color_theme("blue")

        title_label = ctk.CTkLabel(self, text="Öğrenci Yönetimi", font=("Arial", 22, "bold"))
        title_label.pack(pady=20)

        self.tabview = ctk.CTkTabview(self, width=550, height=450)
        self.tabview.pack(padx=20, pady=10)
        
        self.tabview.add("Yüz Tanıma Kaydı")
        self.tabview.add("Excel Yükleme")

        self.setup_capture_tab()
        self.setup_excel_tab()

    def setup_capture_tab(self):
        tab = self.tabview.tab("Yüz Tanıma Kaydı")

        subject_label = ctk.CTkLabel(tab, text="1. Ders Seçin:")
        subject_label.pack(pady=(10, 0))
        self.capture_subject_dropdown = ctk.CTkComboBox(tab, width=350)
        self.capture_subject_dropdown.pack(pady=5)
        load_subjects(self.capture_subject_dropdown)

        search_frame = ctk.CTkFrame(tab)
        search_frame.pack(pady=20, padx=20, fill="x")
        
        search_label = ctk.CTkLabel(search_frame, text="2. Öğrenci Ara (İsim veya No):")
        search_label.pack(pady=5)
        
        self.search_entry = ctk.CTkEntry(search_frame, placeholder_text="ID veya İsim yazın...", width=250)
        self.search_entry.pack(side="left", padx=(20, 10), pady=10)
        
        self.result_dropdown = ctk.CTkComboBox(tab, values=["Arama bekleniyor..."], width=350)

        # BUTTON CALLS THE STRICT SEARCH
        search_btn = ctk.CTkButton(search_frame, text="Dersi Ara", width=100, 
                                   command=lambda: handle_strict_search(self.search_entry, self.capture_subject_dropdown, self.result_dropdown))
        search_btn.pack(side="left", padx=10, pady=10)

        res_label = ctk.CTkLabel(tab, text="3. Öğrenci Seçin:")
        res_label.pack(pady=(10, 0))
        self.result_dropdown.pack(pady=5)

        process_btn = ctk.CTkButton(tab, text="Fotoğraf Çek", fg_color="#C85000", hover_color="#9c3e00", width=350, height=40,
                                    command=lambda: handle_capture(self.capture_subject_dropdown, self.result_dropdown))
        process_btn.pack(pady=30)

    def setup_excel_tab(self):
        tab = self.tabview.tab("Excel Yükleme")

        info_label = ctk.CTkLabel(tab, text="Excel ile Toplu Öğrenci Kaydı", font=("Arial", 16, "bold"))
        info_label.pack(pady=20)

        subject_label = ctk.CTkLabel(tab, text="Ders Seçin:")
        subject_label.pack(pady=(10, 0))
        self.excel_subject_dropdown = ctk.CTkComboBox(tab, width=350)
        self.excel_subject_dropdown.pack(pady=5)
        load_subjects(self.excel_subject_dropdown)

        upload_btn = ctk.CTkButton(tab, text="Excel Dosyası Yükle", fg_color="#107C41", hover_color="#0B5A2F", width=350, height=40,
                                   command=lambda: handle_excel_upload(self.excel_subject_dropdown))
        upload_btn.pack(pady=40)

if __name__ == "__main__":
    root = ctk.CTk()
    root.withdraw() # Hide the empty root window
    app = StudentEnrollmentWindow(root)
    root.mainloop()