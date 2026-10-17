import os
import customtkinter as ctk
import sqlite3
import pandas as pd
from tkinter import filedialog, messagebox

def get_db_path():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, "database", "attendance_system.db")

def get_subjects_from_db(teacher_id=1):
    try:
        with sqlite3.connect(get_db_path()) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT subject_id, course_code, subject_name FROM Subjects WHERE teacher_id = ?", (teacher_id,))
            rows = cursor.fetchall()
            return [f"{row[0]} - [{row[1]}] {row[2]}" for row in rows]
    except Exception:
        return []

def fetch_attendance_dataframe(subject_id):
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
            return None

        students_df = df[['University ID', 'Student Name']].drop_duplicates().copy()
        attendance_records = df.dropna(subset=['Week'])
        
        if not attendance_records.empty:
            pivot_df = attendance_records.pivot_table(index=['University ID', 'Student Name'], columns='Week', values='Status', aggfunc='first').reset_index()
            rename_dict = {col: f'W{int(col)}' for col in pivot_df.columns if isinstance(col, (int, float))}
            pivot_df.rename(columns=rename_dict, inplace=True)
            final_df = pd.merge(students_df, pivot_df, on=['University ID', 'Student Name'], how='left')
        else:
            final_df = students_df
            
        for i in range(1, 15):
            if f'W{i}' not in final_df.columns: final_df[f'W{i}'] = '-'
                
        final_df.fillna('Absent', inplace=True)
        cols_order = ['University ID', 'Student Name'] + [f'W{i}' for i in range(1, 15)]
        final_df = final_df[cols_order]
        return final_df
    except Exception as e:
        print(f"Error fetching dataframe: {e}")
        return None

class ReportsWindow(ctk.CTkToplevel):
    def __init__(self, master=None, teacher_id=1):
        super().__init__(master)
        self.teacher_id = teacher_id
        if master:
            self.grab_set()
        
        self.geometry("1000x600")
        self.title("BioYoklama - Raporlar ve İstatistikler")
        if not master:
            ctk.set_appearance_mode("Dark")

        # Header
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(fill="x", padx=20, pady=20)
        
        ctk.CTkLabel(self.header_frame, text="Ders Yoklama Raporu", font=("Arial", 24, "bold")).pack(side="left")
        
        # Controls
        self.controls_frame = ctk.CTkFrame(self)
        self.controls_frame.pack(fill="x", padx=20, pady=(0, 10))
        
        subjects = get_subjects_from_db(self.teacher_id)
        
        ctk.CTkLabel(self.controls_frame, text="Ders Seçin:").pack(side="left", padx=10, pady=10)
        self.subject_dropdown = ctk.CTkComboBox(self.controls_frame, values=subjects if subjects else ["No subjects found"], width=300, command=self.on_subject_select)
        self.subject_dropdown.pack(side="left", padx=10, pady=10)
        if subjects:
            self.subject_dropdown.set(subjects[0])
            
        self.export_excel_btn = ctk.CTkButton(self.controls_frame, text="Excel Olarak Kaydet", fg_color="#107C41", hover_color="#0B5A2F", command=self.export_to_excel)
        self.export_excel_btn.pack(side="right", padx=5, pady=10)
        
        self.export_pdf_btn = ctk.CTkButton(self.controls_frame, text="PDF Olarak Kaydet", fg_color="#B32024", hover_color="#89181B", command=self.export_to_pdf)
        self.export_pdf_btn.pack(side="right", padx=5, pady=10)
        
        # Stats summary
        self.summary_label = ctk.CTkLabel(self, text="", font=("Arial", 14), text_color="gray")
        self.summary_label.pack(anchor="w", padx=20, pady=5)
        
        # Table Frame
        self.table_frame = ctk.CTkScrollableFrame(self)
        self.table_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        # Initial load
        if subjects:
            self.on_subject_select(subjects[0])

    def clear_table(self):
        for widget in self.table_frame.winfo_children():
            widget.destroy()

    def on_subject_select(self, selection):
        self.clear_table()
        if " - " not in selection:
            self.summary_label.configure(text="Lütfen geçerli bir ders seçin.")
            return
            
        subject_id = int(selection.split(" - ")[0])
        df = fetch_attendance_dataframe(subject_id)
        
        if df is None or df.empty:
            self.summary_label.configure(text="Bu derse kayıtlı öğrenci bulunmuyor.")
            return
            
        total_students = len(df)
        self.summary_label.configure(text=f"Toplam Kayıtlı Öğrenci: {total_students}")
        
        # Build Table Headers
        columns = list(df.columns)
        for col_idx, col_name in enumerate(columns):
            width = 150 if col_idx == 1 else 45 if col_idx > 1 else 100
            header = ctk.CTkLabel(self.table_frame, text=col_name, font=("Arial", 12, "bold"), width=width, fg_color="#333333", corner_radius=5)
            header.grid(row=0, column=col_idx, padx=2, pady=2, sticky="nsew")
            
        # Build Table Rows
        for row_idx, row in df.iterrows():
            for col_idx, value in enumerate(row):
                color = "green" if value == "Present" else "red" if value == "Absent" else "white"
                width = 150 if col_idx == 1 else 45 if col_idx > 1 else 100
                display_val = "✓" if value == "Present" else "✗" if value == "Absent" else value
                cell = ctk.CTkLabel(self.table_frame, text=str(display_val), font=("Arial", 12), text_color=color, width=width)
                cell.grid(row=row_idx+1, column=col_idx, padx=2, pady=2, sticky="nsew")

    def export_to_excel(self):
        selection = self.subject_dropdown.get()
        if " - " not in selection:
            messagebox.showerror("Hata", "Lütfen geçerli bir ders seçin!")
            return
            
        subject_id = int(selection.split(" - ")[0])
        subject_name = selection.split("] ")[1] 
        
        df = fetch_attendance_dataframe(subject_id)
        if df is None or df.empty:
            messagebox.showwarning("Uyarı", "Dışa aktarılacak veri bulunamadı.")
            return
            
        # Format weeks nicely for Excel
        rename_dict = {col: col.replace('W', 'Week ') for col in df.columns if col.startswith('W')}
        df.rename(columns=rename_dict, inplace=True)
            
        save_path = filedialog.asksaveasfilename(defaultextension=".xlsx", initialfile=f"Yoklama_{subject_name}.xlsx", title="Excel Raporunu Kaydet", filetypes=(("Excel Dosyaları", "*.xlsx"), ("Tüm Dosyalar", "*.*")))
        if save_path:
            try:
                df.to_excel(save_path, index=False)
                messagebox.showinfo("Başarılı", f"Rapor başarıyla kaydedildi:\n{save_path}")
            except Exception as e:
                messagebox.showerror("Hata", f"Kaydetme başarısız: {e}")

    def export_to_pdf(self):
        selection = self.subject_dropdown.get()
        if " - " not in selection:
            messagebox.showerror("Hata", "Lütfen geçerli bir ders seçin!")
            return
            
        subject_id = int(selection.split(" - ")[0])
        subject_name = selection.split("] ")[1] 
        
        df = fetch_attendance_dataframe(subject_id)
        if df is None or df.empty:
            messagebox.showwarning("Uyarı", "Dışa aktarılacak veri bulunamadı.")
            return
            
        save_path = filedialog.asksaveasfilename(defaultextension=".pdf", initialfile=f"Yoklama_{subject_name}.pdf", title="PDF Raporunu Kaydet", filetypes=(("PDF Dosyaları", "*.pdf"), ("Tüm Dosyalar", "*.*")))
        if not save_path:
            return
            
        try:
            from fpdf import FPDF
            
            class PDF(FPDF):
                def header(self):
                    self.set_font('helvetica', 'B', 15)
                    self.cell(0, 10, 'Akilli Yoklama Raporu', border=0, ln=1, align='C')
                    self.set_font('helvetica', 'I', 10)
                    self.cell(0, 10, f"Ders: {subject_name}", border=0, ln=1, align='C')
                    self.ln(10)
                    
                def footer(self):
                    self.set_y(-15)
                    self.set_font('helvetica', 'I', 8)
                    self.cell(0, 10, f'Sayfa {self.page_no()}/{{nb}}', align='C')

            pdf = PDF(orientation='L')
            pdf.add_page()
            
            # Use default Helvetica font
            pdf.set_font("helvetica", size=8)
            
            # Format weeks
            rename_dict = {col: col.replace('W', 'Hafta ') for col in df.columns if col.startswith('W')}
            df.rename(columns=rename_dict, inplace=True)
            
            columns = list(df.columns)
            
            page_width = pdf.w - 2 * pdf.l_margin
            col_widths = [20, 45] + [(page_width - 65) / max(1, len(columns) - 2)] * (len(columns) - 2)
            
            # Header Row
            pdf.set_font("helvetica", 'B', 8)
            pdf.set_fill_color(200, 220, 255)
            for i, col in enumerate(columns):
                safe_col = str(col).encode('ascii', 'ignore').decode('ascii')
                pdf.cell(col_widths[i], 8, safe_col, border=1, align='C', fill=True)
            pdf.ln()
            
            # Data Rows
            pdf.set_font("helvetica", size=8)
            for _, row in df.iterrows():
                for i, value in enumerate(row):
                    char_map = str.maketrans("ğüşıöçĞÜŞİÖÇ", "gusiocGUSIOC")
                    safe_val = str(value).translate(char_map)
                    
                    if safe_val == "Present":
                        pdf.set_text_color(0, 128, 0)
                        display_val = "Var"
                    elif safe_val == "Absent":
                        pdf.set_text_color(255, 0, 0)
                        display_val = "Yok"
                    else:
                        pdf.set_text_color(0, 0, 0)
                        display_val = safe_val
                        
                    pdf.cell(col_widths[i], 8, display_val, border=1, align='C')
                pdf.ln()
            
            pdf.output(save_path)
            messagebox.showinfo("Başarılı", f"PDF raporu başarıyla kaydedildi:\n{save_path}")
            
        except Exception as e:
            messagebox.showerror("Hata", f"PDF oluşturma başarısız: {e}")

def open_reports_window(master=None, teacher_id=1):
    if master:
        app = ReportsWindow(master, teacher_id)
    else:
        root = ctk.CTk()
        root.withdraw()
        app = ReportsWindow(root, teacher_id)
        root.mainloop()

if __name__ == "__main__":
    open_reports_window()