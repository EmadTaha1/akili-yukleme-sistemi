import os
import glob

base_dir = os.path.abspath(os.path.dirname(__file__))

def replace_in_file(filepath, old_str, new_str):
    if not os.path.exists(filepath): return
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    if old_str in content:
        content = content.replace(old_str, new_str)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated {filepath}")

# 1. Update DB paths
py_files = glob.glob(os.path.join(base_dir, '**', '*.py'), recursive=True)
db_import_str = "import os\n"
db_path_str = 'os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "database", "attendance_system.db")'

for f in py_files:
    if "db_service.py" in f or "fix_all.py" in f: continue
    
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()
        
    if 'sqlite3.connect("attendance_system.db")' in content:
        if 'import os' not in content:
            content = "import os\n" + content
        if "database_setup.py" in f:
            # It's one level deep
            local_db_path = 'os.path.join(os.path.dirname(os.path.abspath(__file__)), "attendance_system.db")'
            content = content.replace('sqlite3.connect("attendance_system.db")', f'sqlite3.connect({local_db_path})')
        else:
            # Most UI files are one level deep
            content = content.replace('sqlite3.connect("attendance_system.db")', f'sqlite3.connect({db_path_str})')
        
        with open(f, 'w', encoding='utf-8') as file:
            file.write(content)
        print(f"Fixed DB path in {f}")

# 2. Update model_trainer.py
mt_path = os.path.join(base_dir, "services", "model_trainer.py")
if os.path.exists(mt_path):
    with open(mt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if "def train_lbph_model(" in content and "os.path.join" not in content.split("def train_lbph_model(")[1][:150]:
        new_def = """def train_lbph_model():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dataset_path = os.path.join(base_dir, "dataset")
    model_save_path = os.path.join(base_dir, "models", "trainer.yml")
"""
        content = content.replace('def train_lbph_model(dataset_path="dataset", model_save_path="trainer.yml"):', new_def)
        with open(mt_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("Fixed model_trainer.py")

# 3. Update main_dashboard.py
md_path = os.path.join(base_dir, "ui", "main_dashboard.py")
if os.path.exists(md_path):
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Fix imports
    content = content.replace('from gui_subject_setup import open_setup_window', 'import sys\nimport os\nsys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))\nfrom ui.gui_subject_setup import open_setup_window')
    content = content.replace('from gui_enrollment import open_enrollment_window', 'from ui.gui_student_enrollment import StudentEnrollmentWindow')
    content = content.replace('from model_trainer import train_lbph_model', 'from services.model_trainer import train_lbph_model')
    content = content.replace('from gui_attendance_session import open_attendance_window', 'from ui.gui_attendance_session import open_attendance_window')
    content = content.replace('from gui_reports import open_reports_window', 'from ui.gui_reports import open_reports_window')
    
    # Fix enrollment button
    content = content.replace('command=open_enrollment_window', 'command=lambda: StudentEnrollmentWindow(self)')
    
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Fixed main_dashboard.py")

# 4. Create main.py
main_content = """import sys
import os
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from ui.main_dashboard import AttendanceApp

if __name__ == "__main__":
    app = AttendanceApp()
    app.mainloop()
"""
with open(os.path.join(base_dir, "main.py"), "w", encoding='utf-8') as f:
    f.write(main_content)
print("Created main.py")

