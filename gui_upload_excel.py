import os
import customtkinter as ctk
import sqlite3
import pandas as pd
from tkinter import filedialog, messagebox

def get_subjects_from_db():
    """Fetch subjects with the new schema."""
    try:
        conn = sqlite3.connect(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "database", "attendance_system.db"))
        cursor = conn.cursor()
        cursor.execute("SELECT subject_id, course_code, subject_name FROM Subjects")
        rows = cursor.fetchall()
        conn.close()
        return [f"{row[0]} - [{row[1]}] {row[2]}" for row in rows]
    except Exception as e:
        return []

def upload_and_process_file(subject_dropdown):
    """Reads Excel/CSV and inserts students into the database."""
    subject_selection = subject_dropdown.get()
    if not subject_selection or subject_selection == "Select Subject":
        messagebox.showerror("Error", "Please select a subject first!")
        return

    subject_id = int(subject_selection.split(" - ")[0])

    file_path = filedialog.askopenfilename(
        title="Select Excel/CSV File",
        filetypes=(("Excel Files", "*.xlsx *.xls"), ("CSV Files", "*.csv"), ("All Files", "*.*"))
    )
    
    if not file_path:
        return

    try:
        # 1. Read the file
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)

        # Drop empty rows based on the first two columns
        df = df.dropna(subset=[df.columns[0], df.columns[1]])

        conn = sqlite3.connect(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "database", "attendance_system.db"))
        cursor = conn.cursor()
        
        new_students = 0
        enrolled_students = 0
        
        # 2. Process each student
        for index, row in df.iterrows():
            try:
                uni_id = int(row.iloc[0])
                name = str(row.iloc[1]).strip()
            except ValueError:
                continue # Skip rows that don't have a valid integer ID
            
            # Check if student exists globally
            cursor.execute("SELECT student_id FROM Students WHERE university_id = ?", (uni_id,))
            result = cursor.fetchone()
            
            if result:
                student_db_id = result[0]
            else:
                # Insert new student (without face data yet)
                cursor.execute("INSERT INTO Students (university_id, name) VALUES (?, ?)", (uni_id, name))
                student_db_id = cursor.lastrowid
                new_students += 1
                
            # Enroll the student in the selected subject
            cursor.execute("SELECT * FROM Enrollments WHERE student_id = ? AND subject_id = ?", (student_db_id, subject_id))
            if not cursor.fetchone():
                cursor.execute("INSERT INTO Enrollments (student_id, subject_id) VALUES (?, ?)", (student_db_id, subject_id))
                enrolled_students += 1

        conn.commit()
        conn.close()
        
        messagebox.showinfo("Success", f"File Processed Successfully!\n\n- New Students Added to System: {new_students}\n- Students Enrolled in this Subject: {enrolled_students}")
        
    except Exception as e:
        messagebox.showerror("Error", f"Failed to read file: {str(e)}\n\nPlease ensure Column A is ID and Column B is Name.")

def open_upload_window():
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")

    app = ctk.CTk()
    app.geometry("500x350")
    app.title("Pre-Registration - Upload Students")

    title_label = ctk.CTkLabel(app, text="Upload Class List (Excel)", font=("Arial", 22, "bold"))
    title_label.pack(pady=30)

    subjects = get_subjects_from_db()
    if not subjects: subjects = ["No subjects found."]
    
    subject_dropdown = ctk.CTkComboBox(app, values=subjects, width=300)
    subject_dropdown.pack(pady=20)
    subject_dropdown.set(subjects[0] if subjects else "Select Subject")

    # Excel Green color for the button
    upload_btn = ctk.CTkButton(app, text="Browse & Upload File", command=lambda: upload_and_process_file(subject_dropdown), width=300, fg_color="#107C41", hover_color="#0B5A2F")
    upload_btn.pack(pady=30)

    app.mainloop()

if __name__ == "__main__":
    open_upload_window()