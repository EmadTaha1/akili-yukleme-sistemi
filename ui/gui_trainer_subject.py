import customtkinter as ctk
from tkinter import messagebox
import os
import sys

# Ensure root is in path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.append(root_dir)

from services import db_service, model_trainer

class SubjectTrainerApp(ctk.CTkToplevel):
    def __init__(self, master=None):
        if master:
            super().__init__(master)
            self.grab_set()
        else:
            self.root = ctk.CTk()
            super().__init__(self.root)
            
        self.title("Yapay Zeka Modeli Eğitimi")
        self.geometry("450x300")
        
        ctk.CTkLabel(self, text="Eğitilecek Dersi Seçin", font=("Arial", 20, "bold")).pack(pady=20)
        
        subjects = self.get_subject_list()
        self.subject_dropdown = ctk.CTkComboBox(self, values=subjects, width=350)
        self.subject_dropdown.pack(pady=20)
        self.subject_dropdown.set(subjects[0] if subjects else "Ders Seçin")
        
        self.train_btn = ctk.CTkButton(self, text="Eğitimi Başlat", command=self.train, fg_color="green", height=40)
        self.train_btn.pack(pady=30)
        
        if not master:
            self.root.mainloop()

    def get_subject_list(self):
        try:
            subjects = db_service.get_subjects()
            return [f"{row[0]} - [{row[1]}] {row[2]}" for row in subjects] if subjects else ["No subjects found."]
        except:
            return ["Error"]

    def train(self):
        sel = self.subject_dropdown.get()
        if "No" in sel or sel == "Ders Seçin": return
        
        subject_id = int(sel.split(" - ")[0])
        
        self.train_btn.configure(state="disabled", text="Eğitiliyor...")
        self.update()
        
        success, msg = model_trainer.train_lbph_model(subject_id)
        
        if success:
            messagebox.showinfo("Success", msg)
            self.destroy()
        else:
            messagebox.showerror("Error", msg)
            self.train_btn.configure(state="normal", text="Eğitimi Başlat")

if __name__ == "__main__":
    SubjectTrainerApp()
