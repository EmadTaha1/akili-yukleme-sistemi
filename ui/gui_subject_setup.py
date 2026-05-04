import os
import customtkinter as ctk
import sqlite3
from tkinter import messagebox

def save_subject(course_code, subject_name, study_year, academic_year, major):
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
                VALUES (?, ?, ?, ?, ?, 1)
            ''', (course_code, subject_name, study_year, academic_year, major))
            conn.commit()
        messagebox.showinfo("Success", f"Subject [{course_code}] {subject_name} added successfully!")
    except Exception as e:
        messagebox.showerror("Database Error", str(e))

def open_setup_window(master=None):
    """Main GUI for Subject Setup."""
    if master:
        app = ctk.CTkToplevel(master)
        app.grab_set()
    else:
        ctk.set_appearance_mode("Dark")
        app = ctk.CTk()

    app.geometry("500x600")
    app.title("Sistem Kurulumu - Ders Ekle")

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
        save_subject(course_code_entry.get().strip(), name_entry.get().strip(), study_year_dropdown.get(), academic_year_entry.get().strip(), major_entry.get().strip())
        course_code_entry.delete(0, 'end'); name_entry.delete(0, 'end'); academic_year_entry.delete(0, 'end'); major_entry.delete(0, 'end')

    ctk.CTkButton(app, text="Dersi Kaydet", command=on_submit, width=300).pack(pady=30)

    if not master:
        app.mainloop()

if __name__ == "__main__":
    open_setup_window()