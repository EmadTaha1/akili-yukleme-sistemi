import os
import customtkinter as ctk
import sqlite3
import pandas as pd
from tkinter import filedialog, messagebox

def get_db_path():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, "database", "attendance_system.db")

def get_subjects_from_db():
    try:
        with sqlite3.connect(get_db_path()) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT subject_id, course_code, subject_name FROM Subjects")
            rows = cursor.fetchall()
            return [f"{row[0]} - [{row[1]}] {row[2]}" for row in rows]
    except Exception:
        return []

def export_to_excel(subject_selection):
    if not subject_selection or "No" in subject_selection or subject_selection == "Ders Seçin":
        messagebox.showerror("Error", "Please select a valid subject!")
        return

    subject_id = int(subject_selection.split(" - ")[0])
    subject_name = subject_selection.split("] ")[1] 
    
    try:
        with sqlite3.connect(get_db_path()) as conn:
            query = '''
                SELECT s.university_id AS 'University ID', s.name AS 'Student Name', a.week_number AS 'Week', a.status AS 'Status'
                FROM Enrollments e
                JOIN Students s ON e.student_id = s.student_id
                LEFT JOIN Attendance a ON e.enrollment_id = a.enrollment_id
                WHERE e.subject_id = ?
            '''
            df = pd.read_sql_query(query, conn, params=(subject_id,))

        if df.empty:
            messagebox.showwarning("No Data", "No students enrolled.")
            return

        students_df = df[['University ID', 'Student Name']].drop_duplicates().copy()
        attendance_records = df.dropna(subset=['Week'])
        
        if not attendance_records.empty:
            pivot_df = attendance_records.pivot_table(index=['University ID', 'Student Name'], columns='Week', values='Status', aggfunc='first').reset_index()
            rename_dict = {col: f'Week {int(col)}' for col in pivot_df.columns if isinstance(col, (int, float))}
            pivot_df.rename(columns=rename_dict, inplace=True)
            final_df = pd.merge(students_df, pivot_df, on=['University ID', 'Student Name'], how='left')
        else:
            final_df = students_df
            
        for i in range(1, 15):
            if f'Week {i}' not in final_df.columns: final_df[f'Week {i}'] = '-'
                
        final_df.fillna('Absent', inplace=True)
        cols_order = ['University ID', 'Student Name'] + [f'Week {i}' for i in range(1, 15)]
        final_df = final_df[cols_order]

        save_path = filedialog.asksaveasfilename(defaultextension=".xlsx", initialfile=f"Yoklama_{subject_name}.xlsx", title="Excel Raporunu Kaydet", filetypes=(("Excel Dosyaları", "*.xlsx"), ("Tüm Dosyalar", "*.*")))
        if save_path:
            final_df.to_excel(save_path, index=False)
            messagebox.showinfo("Success", f"Report saved to:\n{save_path}")
    except Exception as e:
        messagebox.showerror("Export Error", str(e))

def open_reports_window(master=None):
    """Main GUI for Excel Export."""
    if master:
        app = ctk.CTkToplevel(master)
        app.grab_set()
    else:
        ctk.set_appearance_mode("Dark")
        app = ctk.CTk()
    
    app.geometry("450x300")
    app.title("Raporları Dışa Aktar")

    ctk.CTkLabel(app, text="Yoklamayı Excel'e Aktar", font=("Arial", 22, "bold")).pack(pady=30)
    subjects = get_subjects_from_db()
    subject_dropdown = ctk.CTkComboBox(app, values=subjects if subjects else ["No subjects found"], width=300)
    subject_dropdown.pack(pady=20)
    subject_dropdown.set(subjects[0] if subjects else "Ders Seçin")

    ctk.CTkButton(app, text="Excel Olarak Kaydet", fg_color="#107C41", hover_color="#0B5A2F", width=300, command=lambda: export_to_excel(subject_dropdown.get())).pack(pady=10)

    if not master:
        app.mainloop()

if __name__ == "__main__":
    open_reports_window()