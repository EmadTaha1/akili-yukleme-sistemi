import customtkinter as ctk
from tkinter import messagebox
from services import auth_service
import os
import re

class LoginWindow(ctk.CTk):
    def __init__(self, on_success_callback):
        super().__init__()
        self.on_success_callback = on_success_callback
        
        self.title("Öğretmen Girişi")
        self.geometry("400x550")
        self.resizable(False, False)
        ctk.set_appearance_mode("Dark")
        
        # Center window
        self.update_idletasks()
        x = (self.winfo_screenwidth() - 400) // 2
        y = (self.winfo_screenheight() - 550) // 2
        self.geometry(f"+{x}+{y}")
        
        self.main_frame = ctk.CTkFrame(self, corner_radius=15)
        self.main_frame.pack(pady=40, padx=40, fill="both", expand=True)

        self.show_login_frame()

    def clear_frame(self):
        for widget in self.main_frame.winfo_children():
            widget.destroy()

    def show_login_frame(self):
        self.clear_frame()
        
        # Title
        ctk.CTkLabel(self.main_frame, text="Sisteme Giriş", font=("Arial", 24, "bold")).pack(pady=(30, 20))
        
        # Inputs
        self.email_entry = ctk.CTkEntry(self.main_frame, placeholder_text="E-posta", width=250, height=40)
        self.email_entry.pack(pady=10)
        
        self.password_entry = ctk.CTkEntry(self.main_frame, placeholder_text="Şifre", show="*", width=250, height=40)
        self.password_entry.pack(pady=10)
        
        # Login Button
        self.login_btn = ctk.CTkButton(self.main_frame, text="Giriş Yap", command=self.handle_login, width=250, height=40, fg_color="#1f538d")
        self.login_btn.pack(pady=(20, 10))
        
        # Forgot Password Button
        self.forgot_btn = ctk.CTkButton(self.main_frame, text="Şifremi Unuttum", command=self.show_forgot_password_frame, width=250, height=30, fg_color="transparent", hover_color="#333333", text_color="gray")
        self.forgot_btn.pack(pady=0)
        
        # Switch to Register
        self.switch_btn = ctk.CTkButton(self.main_frame, text="Yeni Hesap Oluştur", command=self.show_register_frame, width=250, height=30, fg_color="transparent", hover_color="#333333", text_color="#1f538d")
        self.switch_btn.pack(pady=5)
        
        self.bind('<Return>', lambda event: self.handle_login())

    def show_register_frame(self):
        self.clear_frame()
        
        # Title
        ctk.CTkLabel(self.main_frame, text="Hesap Oluştur", font=("Arial", 24, "bold")).pack(pady=(30, 20))
        
        # Inputs
        self.reg_name_entry = ctk.CTkEntry(self.main_frame, placeholder_text="Ad Soyad", width=250, height=40)
        self.reg_name_entry.pack(pady=10)
        
        self.reg_email_entry = ctk.CTkEntry(self.main_frame, placeholder_text="E-posta", width=250, height=40)
        self.reg_email_entry.pack(pady=10)
        
        self.reg_password_entry = ctk.CTkEntry(self.main_frame, placeholder_text="Şifre", show="*", width=250, height=40)
        self.reg_password_entry.pack(pady=10)
        
        # Register Button
        self.register_btn = ctk.CTkButton(self.main_frame, text="Kayıt Ol", command=self.handle_register, width=250, height=40, fg_color="#107C41", hover_color="#0B5A2F")
        self.register_btn.pack(pady=(20, 10))
        
        # Switch to Login
        self.switch_btn = ctk.CTkButton(self.main_frame, text="Zaten hesabım var (Giriş Yap)", command=self.show_login_frame, width=250, height=30, fg_color="transparent", hover_color="#333333", text_color="#1f538d")
        self.switch_btn.pack(pady=5)
        
        self.bind('<Return>', lambda event: self.handle_register())

    def show_forgot_password_frame(self):
        self.clear_frame()
        
        # Title
        ctk.CTkLabel(self.main_frame, text="Şifre Sıfırlama", font=("Arial", 24, "bold")).pack(pady=(30, 20))
        
        # Inputs
        self.forgot_email_entry = ctk.CTkEntry(self.main_frame, placeholder_text="E-posta Adresiniz", width=250, height=40)
        self.forgot_email_entry.pack(pady=10)
        
        self.forgot_key_entry = ctk.CTkEntry(self.main_frame, placeholder_text="Kurtarma Anahtarı (Recovery Key)", width=250, height=40)
        self.forgot_key_entry.pack(pady=10)
        
        self.forgot_new_pwd_entry = ctk.CTkEntry(self.main_frame, placeholder_text="Yeni Şifre", show="*", width=250, height=40)
        self.forgot_new_pwd_entry.pack(pady=10)
        
        # Reset Button
        self.reset_btn = ctk.CTkButton(self.main_frame, text="Şifreyi Yenile", command=self.handle_forgot_password, width=250, height=40, fg_color="#C85000", hover_color="#9c3e00")
        self.reset_btn.pack(pady=(20, 10))
        
        # Switch to Login
        self.back_btn = ctk.CTkButton(self.main_frame, text="Geri Dön (İptal)", command=self.show_login_frame, width=250, height=30, fg_color="transparent", hover_color="#333333", text_color="gray")
        self.back_btn.pack(pady=5)
        
        self.bind('<Return>', lambda event: self.handle_forgot_password())

    def handle_login(self):
        email = self.email_entry.get().strip()
        password = self.password_entry.get().strip()
        
        if not email or not password:
            messagebox.showwarning("Uyarı", "Lütfen tüm alanları doldurun.")
            return
            
        teacher_info = auth_service.verify_login(email, password)
        
        if teacher_info:
            self.on_success_callback(teacher_info, self)
        else:
            messagebox.showerror("Hata", "E-posta veya şifre hatalı!")

    def handle_register(self):
        name = self.reg_name_entry.get().strip()
        email = self.reg_email_entry.get().strip()
        password = self.reg_password_entry.get().strip()
        
        if not name or not email or not password:
            messagebox.showwarning("Uyarı", "Lütfen tüm alanları doldurun.")
            return
            
        email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
        if not re.match(email_regex, email):
            messagebox.showwarning("Uyarı", "Geçersiz e-posta formatı! Lütfen doğru bir e-posta girin.")
            return
            
        if len(password) < 6:
            messagebox.showwarning("Uyarı", "Şifre en az 6 karakter olmalıdır.")
            return
            
        success, recovery_key = auth_service.register_teacher(name, email, password)
        
        if success:
            msg = f"Hesabınız başarıyla oluşturuldu!\n\nÖNEMLİ:\nLütfen aşağıdaki Kurtarma Anahtarını kopyalayın ve güvenli bir yerde saklayın. Şifrenizi unutursanız hesabınızı kurtarmanın tek yolu budur:\n\n{recovery_key}"
            # Show a custom dialog or messagebox so they can copy it
            dialog = ctk.CTkToplevel(self)
            dialog.title("Hesap Oluşturuldu - Önemli")
            dialog.geometry("450x300")
            dialog.attributes('-topmost', True)
            dialog.grab_set()
            
            ctk.CTkLabel(dialog, text="Hesabınız başarıyla oluşturuldu!", font=("Arial", 16, "bold"), text_color="green").pack(pady=15)
            ctk.CTkLabel(dialog, text="Lütfen aşağıdaki Kurtarma Anahtarını kopyalayın ve\ngüvenli bir yerde saklayın.", font=("Arial", 14)).pack(pady=5)
            
            key_entry = ctk.CTkEntry(dialog, width=350, justify="center", font=("Arial", 14, "bold"))
            key_entry.insert(0, recovery_key)
            key_entry.configure(state="readonly")
            key_entry.pack(pady=10)
            
            def on_ok():
                dialog.destroy()
                self.show_login_frame()
                
            ctk.CTkButton(dialog, text="Tamam, Kaydettim", command=on_ok).pack(pady=20)
            
        else:
            messagebox.showerror("Hata", "Kayıt başarısız. Bu e-posta zaten kullanımda olabilir.")

    def handle_forgot_password(self):
        email = self.forgot_email_entry.get().strip()
        key = self.forgot_key_entry.get().strip()
        new_pwd = self.forgot_new_pwd_entry.get().strip()
        
        if not email or not key or not new_pwd:
            messagebox.showwarning("Uyarı", "Lütfen tüm alanları doldurun.")
            return
            
        if len(new_pwd) < 6:
            messagebox.showwarning("Uyarı", "Yeni şifre en az 6 karakter olmalıdır.")
            return
            
        success = auth_service.reset_password_with_key(email, key, new_pwd)
        if success:
            messagebox.showinfo("Başarılı", "Şifreniz başarıyla güncellendi! Yeni şifrenizle giriş yapabilirsiniz.")
            self.show_login_frame()
        else:
            messagebox.showerror("Hata", "E-posta veya Kurtarma Anahtarı hatalı!")
