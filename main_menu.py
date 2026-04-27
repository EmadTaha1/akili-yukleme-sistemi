import customtkinter as ctk
import os
import sys
import tkinter as tk
from tkinter import messagebox, filedialog
import sqlite3
import csv
import datetime
import runpy

# ==========================================
# ⚠️ الاستيرادات الخفية (إجبارية لنجاح الـ EXE)
# ==========================================
# نضعها هنا لنجبر أداة التحويل على دمج هذه المكتبات داخل البرنامج
# لأن الملفات الأخرى ستحتاجها للتعرف على الوجه والصوت.
import cv2
import pyttsx3
import random
import time
import numpy as np
try:
    from PIL import Image, ImageTk
except ImportError:
    pass

# ==========================================
# إعدادات المظهر والسمات
# ==========================================
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Akıllı Yoklama Sistemi - Control Panel")
        self.geometry("700x500")
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # إنشاء القائمة الجانبية
        self.sidebar_frame = ctk.CTkFrame(self, width=170, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, rowspan=4, sticky="nsew")
        
        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="⚙️ İşlemler", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        self.btn_recognition = ctk.CTkButton(self.sidebar_frame, text="📸 Yoklamayı Başlat", 
                                             fg_color="#4CAF50", hover_color="#388E3C",
                                             font=ctk.CTkFont(weight="bold"),
                                             command=self.start_recognition)
        self.btn_recognition.grid(row=1, column=0, padx=20, pady=10)

        self.btn_add_student = ctk.CTkButton(self.sidebar_frame, text="➕ Öğrenci Ekle", 
                                             fg_color="transparent", border_width=1, border_color="#D1D1D1",
                                             command=self.add_student_gui)
        self.btn_add_student.grid(row=2, column=0, padx=20, pady=10)

        self.appearance_mode_label = ctk.CTkLabel(self.sidebar_frame, text="Görünüm:", anchor="w")
        self.appearance_mode_label.grid(row=5, column=0, padx=20, pady=(10, 0))
        self.appearance_mode_optionemenu = ctk.CTkOptionMenu(self.sidebar_frame, values=["Dark", "Light", "System"],
                                                             command=self.change_appearance_mode_event)
        self.appearance_mode_optionemenu.grid(row=6, column=0, padx=20, pady=(10, 10))

        # المنطقة الرئيسية
        self.welcome_label = ctk.CTkLabel(self, text="Hoş Geldiniz, Hocam! 👋", font=ctk.CTkFont(size=24, weight="bold"))
        self.welcome_label.grid(row=0, column=1, padx=20, pady=(30, 0))

        self.status_frame = ctk.CTkFrame(self, corner_radius=10, fg_color="#2B2B2B")
        self.status_frame.grid(row=1, column=1, padx=20, pady=20, sticky="nsew")
        
        self.status_title = ctk.CTkLabel(self.status_frame, text="Sistem Durumu:", font=ctk.CTkFont(weight="bold"))
        self.status_title.pack(pady=(10, 5), padx=10, anchor="w")
        
        self.status_text = ctk.CTkLabel(self.status_frame, text="🔄 Hazır. İşlem Bekleniyor...", text_color="#D1D1D1")
        self.status_text.pack(pady=(0, 10), padx=20, anchor="w")

        self.export_frame = ctk.CTkFrame(self, corner_radius=10)
        self.export_frame.grid(row=2, column=1, padx=20, pady=(0, 20), sticky="nsew")
        
        self.export_title = ctk.CTkLabel(self.export_frame, text="📋 Moodle Yoklama Dosyası Oluştur", font=ctk.CTkFont(weight="bold"))
        self.export_title.pack(pady=10, padx=10, anchor="w")

        self.btn_moodle_export = ctk.CTkButton(self.export_frame, text="📊 Excel (CSV) Dışa Aktar", 
                                                fg_color="#2196F3", hover_color="#1976D2",
                                                font=ctk.CTkFont(weight="bold"),
                                                command=self.export_to_moodle)
        self.btn_moodle_export.pack(pady=10)

    # ==========================================
    # المحرك الأساسي لتشغيل الملفات الداخلية
    # ==========================================
    def execute_external_script(self, script_name):
        """دالة احترافية لتشغيل سكريبتات بايثون من داخل الـ EXE"""
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.abspath(".")
        
        script_path = os.path.join(base_path, script_name)
        
        if not os.path.exists(script_path):
            messagebox.showerror("Hata", f"Dosya bulunamadı: {script_name}\nLütfen bu dosyayı EXE'nin yanına kopyalayın.")
            return False
        
        try:
            # تشغيل الكود داخلياً وكأنه جزء من البرنامج
            runpy.run_path(script_path)
            return True
        except SystemExit:
            # تخطي خطأ إغلاق النافذة اليدوي
            return True
        except Exception as e:
            messagebox.showerror("Hata", f"Çalıştırma hatası ({script_name}):\n{e}")
            return False

    def start_recognition(self):
        self.status_text.configure(text="🎥 Kamera Açılıyor... Lütfen bekleyin.", text_color="#FFC107")
        self.update() # إجبار الواجهة على التحديث قبل التشغيل
        
        success = self.execute_external_script("final_recognition.py")
        
        if success:
            self.status_text.configure(text="🔄 Hazır. İşlem Bekleniyor...", text_color="#D1D1D1")
        else:
            self.status_text.configure(text="❌ Hata Oluştu.", text_color="#F44336")

    def add_student_gui(self):
        self.execute_external_script("gui_trainer.py")

    def export_to_moodle(self):
        db_path = 'attendance.db'
        
        if not os.path.exists(db_path):
            messagebox.showwarning("Uyarı", "Veritabanı bulunamadı! Lütfen önce sistemi kullanın.")
            return

        moodle_csv_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Dosyası", "*.csv")],
            title="Moodle Yoklama Dosyasını Kaydet",
            initialfile=f"moodle_yoklama_{datetime.date.today()}.csv"
        )

        if not moodle_csv_path: return

        self.status_text.configure(text="📊 Moodle dosyası oluşturuluyor...", text_color="#2196F3")

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT s.student_id, s.name, a.date, a.time, a.status 
                FROM Attendance_Log a
                JOIN Students s ON a.student_id = s.student_id
            ''')
            records = cursor.fetchall()
            
            if not records:
                messagebox.showinfo("Bilgi", "Bugün için henüz yoklama kaydı yok.")
                self.status_text.configure(text="🔄 Hazır.", text_color="#D1D1D1")
                conn.close()
                return

            with open(moodle_csv_path, 'w', newline='', encoding='utf-8-sig') as csv_file:
                writer = csv.writer(csv_file, delimiter=';') 
                writer.writerow(["Moodle ID", "Ad Soyad", "Tarih", "Saat", "Durum"])
                for record in records:
                    writer.writerow([record[0], record[1], record[2], record[3], "Present"])

            messagebox.showinfo("Başarılı", f"Moodle yoklama dosyası oluşturuldu:\n{moodle_csv_path}")
            self.status_text.configure(text="✅ Moodle dosyası başarıyla dışa aktarıldı.", text_color="#4CAF50")
            conn.close()
            
        except Exception as e:
            messagebox.showerror("Hata", f"Dosya dönüştürülürken hata oluştu: {e}")
            self.status_text.configure(text="❌ Dışa aktarma hatası.", text_color="#F44336")

    def change_appearance_mode_event(self, new_appearance_mode: str):
        ctk.set_appearance_mode(new_appearance_mode)

if __name__ == "__main__":
    app = App()
    app.mainloop()