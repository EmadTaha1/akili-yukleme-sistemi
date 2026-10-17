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

def get_resource_path(relative_path):
    """ 
    Get absolute path to resource, works for dev and for PyInstaller.
    Checks multiple possible locations to ensure compatibility across modes.
    """
    possible_paths = []
    
    if getattr(sys, 'frozen', False):
        # 1. PyInstaller _internal directory (One Directory mode)
        if hasattr(sys, '_MEIPASS'):
            possible_paths.append(sys._MEIPASS)
        # 2. PyInstaller executable directory (Root of One Directory)
        possible_paths.append(os.path.dirname(sys.executable))
    else:
        # 3. Development environment root directory
        possible_paths.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
    for base_path in possible_paths:
        full_path = os.path.join(base_path, relative_path)
        if os.path.exists(full_path):
            return full_path
            
    # Fallback to the first expected path if none exist
    if possible_paths:
        return os.path.join(possible_paths[0], relative_path)
    return relative_path

def load_dnn_model_safe(prototxt_path, model_path):
    """Safely load DNN models bypassing OpenCV's Unicode path bug on Windows."""
    try:
        # Method 1: Change Working Directory temporarily to pass ASCII filenames
        orig_cwd = os.getcwd()
        try:
            os.chdir(os.path.dirname(prototxt_path))
            return cv2.dnn.readNetFromCaffe(os.path.basename(prototxt_path), os.path.basename(model_path))
        finally:
            os.chdir(orig_cwd)
    except Exception:
        # Method 2: Copy to an English-only Public path as fallback
        import shutil
        import uuid
        safe_dir = os.path.join(os.environ.get('PUBLIC', 'C:\\'), f"dnn_temp_{uuid.uuid4().hex[:6]}")
        os.makedirs(safe_dir, exist_ok=True)
        safe_proto = os.path.join(safe_dir, "deploy.prototxt")
        safe_model = os.path.join(safe_dir, "model.caffemodel")
        shutil.copy(prototxt_path, safe_proto)
        shutil.copy(model_path, safe_model)
        try:
            return cv2.dnn.readNetFromCaffe(safe_proto, safe_model)
        finally:
            try:
                shutil.rmtree(safe_dir)
            except Exception:
                pass

def capture_face_dataset(face_id, cam_src=0):
    """Deep Learning (DNN) logic to capture 100 face samples."""
    cam = cv2.VideoCapture(cam_src)
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, 640)   # Reduce resolution from 1280 to save memory
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)  # Perfectly sufficient for face recognition
    
    prototxt_path = get_resource_path(os.path.join("models", "dnn_model", "deploy.prototxt"))
    model_path = get_resource_path(os.path.join("models", "dnn_model", "res10_300x300_ssd_iter_140000.caffemodel"))
    dataset_path = os.path.join(base_dir, "dataset")

    try:
        net = load_dnn_model_safe(prototxt_path, model_path)
    except Exception as e:
        messagebox.showerror("Error", f"DNN model load failed even with fallback.\nReason: {str(e)}")
        return False
    
    if not os.path.exists(dataset_path):
        os.makedirs(dataset_path)

    count = 0
    frame_skip = 0
    while True:
        ret, img = cam.read()
        if not ret: break
        
        frame_skip += 1
        
        # Only process every 3rd frame to save RAM and CPU
        if frame_skip % 3 == 0:
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
                    cv2.imwrite(os.path.join(dataset_path, f"User.{face_id}.{count}.jpg"), gray_face)
                    if count >= 100: break
                
        cv2.imshow('Fotograf Cekiliyor - Kameraya Bakiniz', img)
        if cv2.waitKey(10) & 0xFF == 27 or count >= 100:
            break

    cam.release()
    cv2.destroyAllWindows()
    return count >= 100

def load_subjects(dropdown_ui, teacher_id=1):
    subjects = db_service.get_subjects(teacher_id)
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

def handle_capture(subject_dropdown, student_dropdown, cam_dropdown=None):
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
        cam_sel = cam_dropdown.get() if cam_dropdown else "Kamera 0"
        if cam_sel == "IP/RTSP Kamera":
            dialog = ctk.CTkInputDialog(text="IP/RTSP Kamera Linkini Girin (Örn: rtsp://... veya http://...):", title="Kamera Linki")
            cam_src = dialog.get_input()
            if not cam_src:
                return # cancelled
        else:
            cam_src = int(cam_sel.split()[-1]) # Extracts 0, 1, or 2

        messagebox.showinfo("Kamera Hazır", f"'{student_name}' için yüz verisi bulunamadı.\nKamerayı başlatmak için Tamam'a basın.")
        success = capture_face_dataset(student_db_id, cam_src)
        
        if success:
            db_service.update_student_face_path(student_db_id, student_db_id)
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

def handle_manual_add(subject_dropdown, uid_entry, name_entry, email_entry):
    subject_selection = subject_dropdown.get()
    if " - " not in subject_selection:
        messagebox.showerror("Hata", "Lütfen bir ders seçin!")
        return
        
    uid_str = uid_entry.get().strip()
    name = name_entry.get().strip()
    email = email_entry.get().strip()
    
    if not uid_str or not name:
        messagebox.showwarning("Uyarı", "Öğrenci No ve Ad Soyad zorunludur!")
        return
        
    try:
        uid = int(uid_str)
    except ValueError:
        messagebox.showerror("Hata", "Öğrenci No sadece sayılardan oluşmalıdır!")
        return
        
    subject_id = int(subject_selection.split(" - ")[0])
    
    enrolled = db_service.add_student_manual(uid, name, email if email else None, subject_id)
    if enrolled:
        messagebox.showinfo("Başarılı", f"'{name}' sisteme eklendi ve derse kaydedildi!")
        uid_entry.delete(0, 'end'); name_entry.delete(0, 'end'); email_entry.delete(0, 'end')
    else:
        messagebox.showinfo("Bilgi", f"'{name}' zaten bu derse kayıtlı veya güncellendi.")

def handle_delete_student(subject_dropdown, student_dropdown, window):
    subject_selection = subject_dropdown.get()
    student_selection = student_dropdown.get()

    if " - " not in subject_selection or " | " not in student_selection:
        messagebox.showerror("Hata", "Lütfen geçerli bir ders ve öğrenci seçin.")
        return

    parts = student_selection.split(" | ")
    student_db_id = int(parts[0])
    student_name = parts[2]

    confirm = messagebox.askyesno("Öğrenciyi Sil", f"DIKKAT!\n\n'{student_name}' adlı öğrencinin tüm verilerini, yüz kayıtlarını ve yoklama geçmişini tamamen silmek istediğinize emin misiniz?\n\nBu işlem geri alınamaz!", parent=window)
    
    if confirm:
        try:
            subject_ids = db_service.delete_student_completely(student_db_id)
            
            # Re-train models for subjects this student was in
            for sid in subject_ids:
                model_trainer.train_lbph_model(sid)
                
            messagebox.showinfo("Başarılı", f"'{student_name}' adlı öğrencinin tüm verileri ve yüz görüntüleri sistemden tamamen silindi.\nEtkilenen yapay zeka modelleri güncellendi.", parent=window)
            
            # Refresh search results
            subject_dropdown.event_generate("<<ComboboxSelected>>")
            
        except Exception as e:
            messagebox.showerror("Hata", f"Silme işlemi sırasında bir hata oluştu:\n{e}", parent=window)


class StudentEnrollmentWindow(ctk.CTkToplevel):
    def __init__(self, master=None, teacher_id=1):
        super().__init__(master)
        self.teacher_id = teacher_id
        if master:
            self.grab_set() # Focus on this window
        self.geometry("600x600")
        self.title("BioYoklama - Öğrenci Kayıt Sistemi")
        if not master:
            ctk.set_appearance_mode("Dark")
            ctk.set_default_color_theme("blue")

        title_label = ctk.CTkLabel(self, text="Öğrenci Yönetimi", font=("Arial", 22, "bold"))
        title_label.pack(pady=20)

        self.tabview = ctk.CTkTabview(self, width=550, height=450)
        self.tabview.pack(padx=20, pady=10)
        
        self.tabview.add("Yüz Tanıma Kaydı")
        self.tabview.add("Excel Yükleme")
        self.tabview.add("Manuel Kayıt")
        self.tabview.add("Öğrenci Sil")

        self.setup_capture_tab()
        self.setup_excel_tab()
        self.setup_manual_tab()
        self.setup_delete_tab()

    def setup_capture_tab(self):
        tab = self.tabview.tab("Yüz Tanıma Kaydı")

        subject_label = ctk.CTkLabel(tab, text="1. Ders Seçin:")
        subject_label.pack(pady=(10, 0))
        self.capture_subject_dropdown = ctk.CTkComboBox(tab, width=350, command=self.on_subject_change)
        self.capture_subject_dropdown.pack(pady=5)
        load_subjects(self.capture_subject_dropdown, self.teacher_id)

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

        # === NEW: Camera Selection ===
        cam_label = ctk.CTkLabel(tab, text="4. Kamera Seçin:")
        cam_label.pack(pady=(10, 0))
        cam_options = ["Kamera 0", "Kamera 1", "Kamera 2", "IP/RTSP Kamera"]
        self.cam_dropdown = ctk.CTkComboBox(tab, values=cam_options, width=350)
        self.cam_dropdown.pack(pady=5)
        self.cam_dropdown.set("Kamera 0")

        process_btn = ctk.CTkButton(tab, text="Fotoğraf Çek", fg_color="#C85000", hover_color="#9c3e00", width=350, height=40,
                                    command=lambda: handle_capture(self.capture_subject_dropdown, self.result_dropdown, self.cam_dropdown))
        process_btn.pack(pady=20)
        
        # Trigger initial update after everything is created
        if self.capture_subject_dropdown.get() != "No subjects found":
            self.on_subject_change(self.capture_subject_dropdown.get())

    def on_subject_change(self, choice):
        self.search_entry.delete(0, "end")
        handle_strict_search(self.search_entry, self.capture_subject_dropdown, self.result_dropdown)

    def setup_excel_tab(self):
        tab = self.tabview.tab("Excel Yükleme")

        info_label = ctk.CTkLabel(tab, text="Excel ile Toplu Öğrenci Kaydı", font=("Arial", 16, "bold"))
        info_label.pack(pady=20)

        subject_label = ctk.CTkLabel(tab, text="Ders Seçin:")
        subject_label.pack(pady=(10, 0))
        self.excel_subject_dropdown = ctk.CTkComboBox(tab, width=350)
        self.excel_subject_dropdown.pack(pady=5)
        load_subjects(self.excel_subject_dropdown, self.teacher_id)

        upload_btn = ctk.CTkButton(tab, text="Excel Dosyası Yükle", fg_color="#107C41", hover_color="#0B5A2F", width=350, height=40,
                                   command=lambda: handle_excel_upload(self.excel_subject_dropdown))
        upload_btn.pack(pady=40)

    def setup_manual_tab(self):
        tab = self.tabview.tab("Manuel Kayıt")
        
        ctk.CTkLabel(tab, text="Öğrenciyi Manuel Ekle", font=("Arial", 16, "bold")).pack(pady=10)
        
        ctk.CTkLabel(tab, text="Ders Seçin:").pack()
        manual_subject_dropdown = ctk.CTkComboBox(tab, width=300)
        manual_subject_dropdown.pack(pady=(0, 10))
        load_subjects(manual_subject_dropdown, self.teacher_id)
        
        uid_entry = ctk.CTkEntry(tab, placeholder_text="Öğrenci Numarası", width=300)
        uid_entry.pack(pady=5)
        
        name_entry = ctk.CTkEntry(tab, placeholder_text="Öğrenci Adı Soyadı", width=300)
        name_entry.pack(pady=5)
        
        email_entry = ctk.CTkEntry(tab, placeholder_text="Öğrenci E-posta (Opsiyonel)", width=300)
        email_entry.pack(pady=5)
        
        add_btn = ctk.CTkButton(tab, text="Öğrenciyi Kaydet", width=300, 
                                command=lambda: handle_manual_add(manual_subject_dropdown, uid_entry, name_entry, email_entry))
        add_btn.pack(pady=20)

    def setup_delete_tab(self):
        tab = self.tabview.tab("Öğrenci Sil")
        
        ctk.CTkLabel(tab, text="Öğrenci Verilerini Tamamen Sil", font=("Arial", 16, "bold"), text_color="red").pack(pady=(10, 0))
        ctk.CTkLabel(tab, text="DİKKAT: Bu işlem öğrencinin tüm yoklama geçmişini, yüz fotoğraflarını ve sistem kayıtlarını geri dönüşümsüz olarak siler.", font=("Arial", 11), text_color="gray", wraplength=500).pack(pady=(5, 15))

        subject_label = ctk.CTkLabel(tab, text="1. Ders Seçin:")
        subject_label.pack(pady=(5, 0))
        self.delete_subject_dropdown = ctk.CTkComboBox(tab, width=350, command=self.on_delete_subject_change)
        self.delete_subject_dropdown.pack(pady=5)
        load_subjects(self.delete_subject_dropdown, self.teacher_id)

        search_frame = ctk.CTkFrame(tab)
        search_frame.pack(pady=10, padx=20, fill="x")
        
        search_label = ctk.CTkLabel(search_frame, text="2. Öğrenci Ara (İsim veya No):")
        search_label.pack(pady=5)
        
        self.delete_search_entry = ctk.CTkEntry(search_frame, placeholder_text="ID veya İsim yazın...", width=250)
        self.delete_search_entry.pack(side="left", padx=(20, 10), pady=10)
        
        self.delete_result_dropdown = ctk.CTkComboBox(tab, values=["Arama bekleniyor..."], width=350)

        search_btn = ctk.CTkButton(search_frame, text="Ara", width=100, 
                                   command=lambda: handle_strict_search(self.delete_search_entry, self.delete_subject_dropdown, self.delete_result_dropdown))
        search_btn.pack(side="left", padx=10, pady=10)

        res_label = ctk.CTkLabel(tab, text="3. Silinecek Öğrenciyi Seçin:")
        res_label.pack(pady=(10, 0))
        self.delete_result_dropdown.pack(pady=5)

        delete_btn = ctk.CTkButton(tab, text="Verileri Tamamen Sil", fg_color="red", hover_color="darkred", width=350, height=40,
                                    command=lambda: handle_delete_student(self.delete_subject_dropdown, self.delete_result_dropdown, self))
        delete_btn.pack(pady=20)
        
        if self.delete_subject_dropdown.get() != "No subjects found":
            self.on_delete_subject_change(self.delete_subject_dropdown.get())

    def on_delete_subject_change(self, choice):
        self.delete_search_entry.delete(0, "end")
        handle_strict_search(self.delete_search_entry, self.delete_subject_dropdown, self.delete_result_dropdown)


if __name__ == "__main__":
    root = ctk.CTk()
    root.withdraw() # Hide the empty root window
    app = StudentEnrollmentWindow(root)
    root.mainloop()