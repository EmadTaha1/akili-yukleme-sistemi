import os
import sys
import customtkinter as ctk
import sqlite3
from tkinter import messagebox

# Ensure Python can find the 'services' folder from the root directory
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.append(base_dir)

from services import db_service

def load_subjects_to_dropdown(dropdown_ui, teacher_id=1):
    subjects = db_service.get_subjects(teacher_id)
    if subjects:
        formatted_subjects = [f"{row[0]} - [{row[1]}] {row[2]}" for row in subjects]
        dropdown_ui.configure(values=formatted_subjects)
        dropdown_ui.set(formatted_subjects[0])
    else:
        dropdown_ui.configure(values=["No subjects found"])
        dropdown_ui.set("No subjects found")

def handle_delete_subject(dropdown_ui, teacher_id, window):
    selection = dropdown_ui.get()
    if not selection or "No" in selection:
        messagebox.showerror("Hata", "Lütfen silinecek bir ders seçin.", parent=window)
        return
        
    subject_id = int(selection.split(" - ")[0])
    subject_name = selection.split(" - ")[1]
    
    confirm = messagebox.askyesno("Dersi Sil", f"DİKKAT!\n\n{subject_name} dersini ve bu derse ait tüm kayıtları, yoklamaları ve modeli silmek istediğinize emin misiniz?\n\nBu işlem geri alınamaz!", parent=window)
    if confirm:
        try:
            db_service.delete_subject(subject_id)
            messagebox.showinfo("Başarılı", f"'{subject_name}' başarıyla silindi.", parent=window)
            load_subjects_to_dropdown(dropdown_ui, teacher_id)
        except Exception as e:
            messagebox.showerror("Hata", f"Silme işlemi başarısız: {e}", parent=window)

def save_subject(course_code, subject_name, study_year, academic_year, major, teacher_id=1, delete_dropdown=None):
    """Saves the new subject into the database."""
    if not all([course_code, subject_name, study_year, academic_year, major]):
        messagebox.showerror("Error", "All fields are required!")
        return

    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        db_path = os.path.join(base_dir, "database", "attendance_system.db")
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM Subjects WHERE course_code = ?", (course_code,))
            if cursor.fetchone():
                messagebox.showerror("Error", f"Course Code '{course_code}' already exists!")
                return

            cursor.execute('''
                INSERT INTO Subjects (course_code, subject_name, study_year, academic_year, major, teacher_id)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (course_code, subject_name, study_year, academic_year, major, teacher_id))
            conn.commit()
        messagebox.showinfo("Success", f"Subject [{course_code}] {subject_name} added successfully!")
        if delete_dropdown:
            load_subjects_to_dropdown(delete_dropdown, teacher_id)
    except Exception as e:
        messagebox.showerror("Database Error", str(e))

def open_setup_window(master=None, teacher_id=1):
    """Main GUI for Subject Setup."""
    if master:
        app = ctk.CTkToplevel(master)
        app.grab_set()
    else:
        ctk.set_appearance_mode("Dark")
        app = ctk.CTk()

    app.geometry("500x600")
    app.title("BioYoklama - Ders Ekle")

    ctk.CTkLabel(app, text="Yeni Ders Ekle", font=("Arial", 22, "bold")).pack(pady=20)
    
    course_code_entry = ctk.CTkEntry(app, placeholder_text="Ders Kodu", width=300)
    course_code_entry.pack(pady=10)
    name_entry = ctk.CTkEntry(app, placeholder_text="Ders Adı", width=300)
    name_entry.pack(pady=10)

    ctk.CTkLabel(app, text="Sınıf:").pack(pady=(10, 0))
    study_year_dropdown = ctk.CTkComboBox(app, values=["1. Sınıf", "2. Sınıf", "3. Sınıf", "4. Sınıf"], width=300)
    study_year_dropdown.pack(pady=5)
    study_year_dropdown.set("1. Sınıf")

    academic_year_entry = ctk.CTkEntry(app, placeholder_text="Akademik Yıl", width=300)
    academic_year_entry.pack(pady=10)
    major_entry = ctk.CTkEntry(app, placeholder_text="Bölüm", width=300)
    major_entry.pack(pady=10)

    def on_submit():
        save_subject(course_code_entry.get().strip(), name_entry.get().strip(), study_year_dropdown.get(), academic_year_entry.get().strip(), major_entry.get().strip(), teacher_id, delete_subject_dropdown)
        course_code_entry.delete(0, 'end'); name_entry.delete(0, 'end'); academic_year_entry.delete(0, 'end'); major_entry.delete(0, 'end')

    ctk.CTkButton(app, text="Dersi Kaydet", command=on_submit, width=300).pack(pady=20)

    # --- Delete Subject Section ---
    ctk.CTkFrame(app, height=2, fg_color="gray").pack(fill="x", padx=40, pady=20)
    
    ctk.CTkLabel(app, text="Ders Silme (Tehlikeli İşlem)", font=("Arial", 16, "bold"), text_color="red").pack(pady=(0, 10))
    
    delete_subject_dropdown = ctk.CTkComboBox(app, width=300)
    delete_subject_dropdown.pack(pady=5)
    load_subjects_to_dropdown(delete_subject_dropdown, teacher_id)
    
    ctk.CTkButton(app, text="Dersi Tamamen Sil", fg_color="red", hover_color="darkred", width=300,
                  command=lambda: handle_delete_subject(delete_subject_dropdown, teacher_id, app)).pack(pady=10)

    if not master:
        app.mainloop()

if __name__ == "__main__":
    open_setup_window()