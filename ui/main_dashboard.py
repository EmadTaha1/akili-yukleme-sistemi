import customtkinter as ctk
from PIL import Image
import os
import sys

# Ensure root is in path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.append(root_dir)

from ui.gui_subject_setup import open_setup_window
from ui.gui_student_enrollment import StudentEnrollmentWindow
# from ui.gui_trainer_subject import SubjectTrainerApp # Removed because training is automated
from ui.gui_attendance_session import open_attendance_window
from ui.gui_reports import open_reports_window


class AttendanceApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Akıllı Yoklama Sistemi - Yönetici Paneli")
        self.geometry("900x600")
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        
        # Logo
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            logo_path = os.path.join(base_dir, "assets", "logo.ico")
            self.logo_image = ctk.CTkImage(light_image=Image.open(logo_path),
                                           dark_image=Image.open(logo_path),
                                           size=(100, 100))
            self.logo_label = ctk.CTkLabel(self.sidebar_frame, image=self.logo_image, text="")
            self.logo_label.pack(pady=(30, 0))
        except Exception as e:
            print(f"Could not load logo: {e}")

        ctk.CTkLabel(self.sidebar_frame, text="Yoklama Sistemi", font=("Arial", 20, "bold")).pack(pady=(10, 30))

        ctk.CTkButton(self.sidebar_frame, text="Sistem Kurulumu", command=lambda: open_setup_window(self)).pack(pady=10, padx=20)
        ctk.CTkButton(self.sidebar_frame, text="Öğrenci Kaydı", command=lambda: StudentEnrollmentWindow(self)).pack(pady=10, padx=20)
        # Training is now automated after capture
        ctk.CTkButton(self.sidebar_frame, text="Yoklama Al", command=lambda: open_attendance_window(self), fg_color="green").pack(pady=10, padx=20)
        ctk.CTkButton(self.sidebar_frame, text="Raporlar", command=lambda: open_reports_window(self)).pack(pady=10, padx=20)

        # Main Content
        self.main_content = ctk.CTkFrame(self, fg_color="transparent")
        self.main_content.grid(row=0, column=1, padx=30, pady=30, sticky="nsew")
        ctk.CTkLabel(self.main_content, text="Hoş Geldiniz!", font=("Arial", 28, "bold")).pack(pady=(50, 10))
        ctk.CTkLabel(self.main_content, text="İşlem yapmak için yan menüden bir seçenek seçin.").pack(pady=10)
        
        self.stats_frame = ctk.CTkFrame(self.main_content, height=150)
        self.stats_frame.pack(fill="x", pady=50, padx=20)
        ctk.CTkLabel(self.stats_frame, text="Sistem Durumu: Aktif", text_color="green", font=("Arial", 12, "bold")).pack(pady=20)

        self.mode_menu = ctk.CTkOptionMenu(self.sidebar_frame, values=["Koyu", "Açık"], command=self.change_appearance_mode_event)
        self.mode_menu.pack(side="bottom", padx=20, pady=20)

    def change_appearance_mode_event(self, new_appearance_mode: str):
        if new_appearance_mode == "Koyu":
            ctk.set_appearance_mode("Dark")
        elif new_appearance_mode == "Açık":
            ctk.set_appearance_mode("Light")

if __name__ == "__main__":
    app = AttendanceApp()
    app.mainloop()