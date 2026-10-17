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
from services import stats_service
from services import auth_service
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import tkinter.messagebox as messagebox
import matplotlib.pyplot as plt


class AttendanceApp(ctk.CTk):
    def __init__(self, teacher_info=None):
        super().__init__()
        self.teacher_info = teacher_info or {"teacher_id": 1, "name": "Bilinmeyen Kullanıcı"}
        self.title("BioYoklama - Yönetici Paneli")
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

        ctk.CTkLabel(self.sidebar_frame, text="BioYoklama", font=("Arial", 20, "bold")).pack(pady=(10, 30))

        ctk.CTkButton(self.sidebar_frame, text="Sistem Kurulumu", command=lambda: open_setup_window(self, self.teacher_info.get('teacher_id', 1))).pack(pady=10, padx=20)
        ctk.CTkButton(self.sidebar_frame, text="Öğrenci Kaydı", command=lambda: StudentEnrollmentWindow(self, self.teacher_info.get('teacher_id', 1))).pack(pady=10, padx=20)
        ctk.CTkButton(self.sidebar_frame, text="Yoklama Al", command=lambda: open_attendance_window(self, self.teacher_info.get('teacher_id', 1)), fg_color="green").pack(pady=10, padx=20)
        ctk.CTkButton(self.sidebar_frame, text="Raporlar", command=lambda: open_reports_window(self, self.teacher_info.get('teacher_id', 1))).pack(pady=10, padx=20)
        ctk.CTkButton(self.sidebar_frame, text="Profil & Güvenlik", command=self.open_profile_window, fg_color="#C85000", hover_color="#9c3e00").pack(pady=10, padx=20)

        # Main Content
        self.main_content = ctk.CTkFrame(self, fg_color="transparent")
        self.main_content.grid(row=0, column=1, padx=30, pady=10, sticky="nsew")
        
        self.welcome_label = ctk.CTkLabel(self.main_content, text=f"Hoş Geldiniz, {self.teacher_info['name']}!", font=("Arial", 28, "bold"))
        self.welcome_label.pack(pady=(20, 5), anchor="w")
        ctk.CTkLabel(self.main_content, text="Sisteminizin anlık durumu aşağıdadır.", text_color="gray").pack(pady=(0, 20), anchor="w")
        
        # Stats Cards
        self.stats_frame = ctk.CTkFrame(self.main_content, fg_color="transparent")
        self.stats_frame.pack(fill="x", pady=(10, 20))
        self.stats_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
        
        stats = stats_service.get_dashboard_stats(self.teacher_info.get('teacher_id', 1))
        
        self.create_stat_card(self.stats_frame, "📚 Dersler", str(stats['total_subjects']), 0)
        self.create_stat_card(self.stats_frame, "👥 Öğrenciler", str(stats['total_students']), 1)
        self.create_stat_card(self.stats_frame, "✅ Bugünkü Katılım", stats['today_attendance'], 2)
        self.create_stat_card(self.stats_frame, "📅 Son Yoklama", stats['last_session'], 3)

        # Chart
        self.chart_frame = ctk.CTkFrame(self.main_content)
        self.chart_frame.pack(fill="both", expand=True, pady=10)
        
        self.draw_chart()

        self.mode_menu = ctk.CTkOptionMenu(self.sidebar_frame, values=["Koyu", "Açık"], command=self.change_appearance_mode_event)
        self.mode_menu.pack(side="bottom", padx=20, pady=20)
        
        self.logout_btn = ctk.CTkButton(self.sidebar_frame, text="Çıkış Yap", command=self.logout, fg_color="#b82121", hover_color="#8f1a1a")
        self.logout_btn.pack(side="bottom", padx=20, pady=(0, 10))

    def logout(self):
        confirm = messagebox.askyesno("Çıkış", "Sistemden çıkış yapmak istediğinize emin misiniz?", parent=self)
        if confirm:
            self.destroy()
            os.execl(sys.executable, sys.executable, *sys.argv)

    def change_appearance_mode_event(self, new_appearance_mode: str):
        if new_appearance_mode == "Koyu":
            ctk.set_appearance_mode("Dark")
        elif new_appearance_mode == "Açık":
            ctk.set_appearance_mode("Light")

    def open_profile_window(self):
        # Fetch latest details to ensure we have the recovery key
        details = auth_service.get_teacher_details(self.teacher_info.get('teacher_id', 1))
        if not details:
            messagebox.showerror("Hata", "Profil bilgileri alınamadı.")
            return
            
        sec_win = ctk.CTkToplevel(self)
        sec_win.title("Profil ve Güvenlik")
        sec_win.geometry("500x640")
        sec_win.grab_set()
        
        ctk.CTkLabel(sec_win, text="Profil Ayarları", font=("Arial", 20, "bold")).pack(pady=(20, 10))
        
        # Name
        ctk.CTkLabel(sec_win, text="Ad Soyad:").pack(anchor="w", padx=50)
        name_entry = ctk.CTkEntry(sec_win, width=400)
        name_entry.insert(0, details['name'])
        name_entry.pack(pady=(0, 10))
        
        # Email
        ctk.CTkLabel(sec_win, text="E-posta:").pack(anchor="w", padx=50)
        email_entry = ctk.CTkEntry(sec_win, width=400)
        email_entry.insert(0, details['email'])
        email_entry.pack(pady=(0, 10))
        
        # Recovery Key (Read Only)
        ctk.CTkLabel(sec_win, text="Kurtarma Anahtarı (Şifre sıfırlama için gereklidir):", text_color="#C85000").pack(anchor="w", padx=50)
        key_frame = ctk.CTkFrame(sec_win, fg_color="transparent")
        key_frame.pack(pady=(0, 10), padx=50, fill="x")
        
        key_entry = ctk.CTkEntry(key_frame, width=320)
        key_entry.insert(0, details['recovery_key'] if details['recovery_key'] else "Yok")
        key_entry.configure(state="readonly")
        key_entry.pack(side="left", padx=(0, 10))
        
        def copy_key():
            self.clipboard_clear()
            self.clipboard_append(details['recovery_key'] if details['recovery_key'] else "")
            messagebox.showinfo("Kopyalandı", "Kurtarma anahtarı panoya kopyalandı!", parent=sec_win)
            
        ctk.CTkButton(key_frame, text="Kopyala", width=70, command=copy_key).pack(side="left")
        
        # Password
        ctk.CTkLabel(sec_win, text="Yeni Şifre (Değiştirmek istemiyorsanız boş bırakın):").pack(anchor="w", padx=50, pady=(10, 0))
        pwd_entry = ctk.CTkEntry(sec_win, placeholder_text="Yeni Şifre (En az 6 karakter)", show="*", width=400)
        pwd_entry.pack(pady=(0, 10))
        
        # Gmail App Password
        ctk.CTkLabel(sec_win, text="Gmail Uygulama Şifresi (Yoklama Bildirimleri için):").pack(anchor="w", padx=50)
        gmail_entry = ctk.CTkEntry(sec_win, placeholder_text="Örn: xxxx xxxx xxxx xxxx", show="*", width=400)
        gmail_entry.insert(0, details.get('gmail_app_password', ''))
        gmail_entry.pack(pady=(0, 20))
        
        def save_profile():
            new_name = name_entry.get().strip()
            new_email = email_entry.get().strip()
            new_pwd = pwd_entry.get().strip()
            new_gmail = gmail_entry.get().strip()
            
            if not new_name or not new_email:
                messagebox.showwarning("Uyarı", "Ad ve E-posta alanları boş bırakılamaz!", parent=sec_win)
                return
                
            if new_pwd and len(new_pwd) < 6:
                messagebox.showwarning("Uyarı", "Şifre en az 6 karakter olmalıdır!", parent=sec_win)
                return
            
            success = auth_service.update_teacher_profile(
                self.teacher_info.get('teacher_id', 1), 
                new_name, 
                new_email, 
                new_pwd if new_pwd else None,
                new_gmail
            )
            
            if success:
                messagebox.showinfo("Başarılı", "Profiliniz başarıyla güncellendi!", parent=sec_win)
                # Update UI and local info
                self.teacher_info['name'] = new_name
                self.teacher_info['email'] = new_email
                self.welcome_label.configure(text=f"Hoş Geldiniz, {new_name}!")
                sec_win.destroy()
            else:
                messagebox.showerror("Hata", "Güncelleme başarısız. Bu e-posta başka bir hesap tarafından kullanılıyor olabilir.", parent=sec_win)
                
        ctk.CTkButton(sec_win, text="Değişiklikleri Kaydet", command=save_profile, width=400, height=40, fg_color="#107C41", hover_color="#0B5A2F").pack(pady=10)

    def create_stat_card(self, parent, title, value, col):
        card = ctk.CTkFrame(parent, corner_radius=10)
        card.grid(row=0, column=col, padx=10, sticky="ew")
        
        ctk.CTkLabel(card, text=title, font=("Arial", 14, "bold"), text_color="gray").pack(pady=(15, 5))
        ctk.CTkLabel(card, text=value, font=("Arial", 24, "bold")).pack(pady=(0, 15))

    def draw_chart(self):
        chart_data = stats_service.get_attendance_chart_data(self.teacher_info.get('teacher_id', 1))
        
        fig, ax = plt.subplots(figsize=(6, 3), dpi=100)
        fig.patch.set_facecolor('#2b2b2b') # Dark theme bg
        ax.set_facecolor('#2b2b2b')
        
        labels = chart_data['labels'] if chart_data['labels'] else ['Veri Yok']
        rates = chart_data['rates'] if chart_data['rates'] else [0]
        
        bars = ax.bar(labels, rates, color='#1f538d', width=0.5)
        
        ax.set_ylim(0, 100)
        ax.tick_params(colors='white')
        for spine in ax.spines.values():
            spine.set_edgecolor('#555555')
            
        # Add labels on top of bars
        for bar in bars:
            yval = bar.get_height()
            if yval > 0:
                ax.text(bar.get_x() + bar.get_width()/2, yval + 2, f'{yval}%', ha='center', color='white', fontdict={'size': 9})
                
        plt.tight_layout()
        
        canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)

if __name__ == "__main__":
    app = AttendanceApp()
    app.mainloop()