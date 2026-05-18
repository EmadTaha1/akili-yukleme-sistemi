import sqlite3
import os
import glob
import shutil

def reset_student_data():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(base_dir, "database", "attendance_system.db")
    
    print("[INFO] Resetting database student records...")
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Clear Attendance, Enrollments, and Students tables
            cursor.execute("DELETE FROM Attendance")
            cursor.execute("DELETE FROM Enrollments")
            cursor.execute("DELETE FROM Students")
            conn.commit()
            print("[SUCCESS] Cleared database tables: Attendance, Enrollments, Students.")
    except Exception as e:
        print(f"[ERROR] Database clear failed: {e}")
        return

    # Delete all photos in dataset folder
    dataset_dir = os.path.join(base_dir, "dataset")
    print(f"[INFO] Clearing student photos in {dataset_dir}...")
    if os.path.exists(dataset_dir):
        jpg_files = glob.glob(os.path.join(dataset_dir, "*.jpg"))
        deleted_pics = 0
        for f in jpg_files:
            try:
                os.remove(f)
                deleted_pics += 1
            except Exception as e:
                print(f"[WARNING] Failed to delete {f}: {e}")
        print(f"[SUCCESS] Deleted {deleted_pics} student photos.")
    
    # Delete trained models in models folder (except models/dnn_model)
    models_dir = os.path.join(base_dir, "models")
    print(f"[INFO] Clearing trained models in {models_dir}...")
    if os.path.exists(models_dir):
        # We find files directly inside models/ (not inside subfolders like dnn_model)
        for entry in os.listdir(models_dir):
            full_path = os.path.join(models_dir, entry)
            if os.path.isfile(full_path) and (entry.endswith(".pkl") or entry.endswith(".yml")):
                try:
                    os.remove(full_path)
                    print(f"Deleted model: {entry}")
                except Exception as e:
                    print(f"[WARNING] Failed to delete model {entry}: {e}")
        print("[SUCCESS] Trained models cleared.")

if __name__ == "__main__":
    reset_student_data()
