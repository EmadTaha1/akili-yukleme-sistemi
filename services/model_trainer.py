import cv2
import numpy as np
import os
import sys
import re

# Add root to path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.append(root_dir)

from services import db_service
from services.face_service import preprocess_face  # Common preprocessing between training and recognition

def sanitize_filename(name):
    """Removes special characters and replaces spaces with underscores."""
    return re.sub(r'[^\w\s-]', '', name).strip().replace(' ', '_')

def get_model_filename(subject_id):
    """Constructs a descriptive filename for the AI model."""
    details = db_service.get_subject_details(subject_id)
    if not details:
        return f"trainer_{subject_id}.yml"
    
    # details = (id, code, name, year)
    code = sanitize_filename(str(details[1]))
    name = sanitize_filename(str(details[2]))
    year = sanitize_filename(str(details[3]))
    
    return f"trainer_ID{subject_id}_{code}_{name}_{year}.yml"

def save_lbph_model_safe(recognizer, model_save_path):
    """Safely save LBPH models bypassing OpenCV's Unicode path bug on Windows."""
    try:
        orig_cwd = os.getcwd()
        try:
            os.chdir(os.path.dirname(model_save_path))
            recognizer.write(os.path.basename(model_save_path))
        finally:
            os.chdir(orig_cwd)
    except Exception:
        import shutil
        import uuid
        safe_dir = os.path.join(os.environ.get('PUBLIC', 'C:\\'), f"lbph_temp_{uuid.uuid4().hex[:6]}")
        os.makedirs(safe_dir, exist_ok=True)
        safe_model = os.path.join(safe_dir, "model.yml")
        try:
            recognizer.write(safe_model)
            shutil.copy(safe_model, model_save_path)
        finally:
            try:
                shutil.rmtree(safe_dir)
            except Exception:
                pass

def train_lbph_model(subject_id=None):
    """
    Trains a model with a descriptive filename.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dataset_path = os.path.join(base_dir, "dataset")
    
    if subject_id:
        filename = get_model_filename(subject_id)
        model_save_path = os.path.join(base_dir, "models", filename)
        allowed_ids = db_service.get_enrolled_student_ids(subject_id)
    else:
        model_save_path = os.path.join(base_dir, "models", "trainer_global.yml")
        allowed_ids = None

    # --- Standard LBPH parameters (balance between accuracy and file size) ---------
    # neighbors=16 inflated the model 256x too much -> 782MB!
    # neighbors=8 (default) -> File size ~3MB with excellent accuracy
    recognizer = cv2.face.LBPHFaceRecognizer_create(
        radius=1,
        neighbors=8,
        grid_x=8,
        grid_y=8
    )
    
    if not os.path.exists(dataset_path):
        return False, "Dataset folder not found."

    image_paths = [os.path.join(dataset_path, f) for f in os.listdir(dataset_path) if f.endswith('.jpg')]
    
    face_samples = []
    ids = []

    for image_path in image_paths:
        try:
            student_db_id = int(os.path.split(image_path)[-1].split(".")[1])
            if allowed_ids is not None and student_db_id not in allowed_ids:
                continue
            img_numpy = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
            if img_numpy is None: continue
            # --- Same preprocessing as capture: Resize + CLAHE -------------------------
            img_numpy = preprocess_face(img_numpy)
            face_samples.append(img_numpy)
            ids.append(student_db_id)
        except: continue

    if not face_samples:
        return False, "No training images found."

    recognizer.train(face_samples, np.array(ids, dtype=np.int32))
    
    # --- Free memory immediately after training (instead of waiting for GC) ---------
    del face_samples
    del ids

    # Remove old models for this subject ID to avoid duplicates with different names
    models_dir = os.path.join(base_dir, "models")
    for f in os.listdir(models_dir):
        if f.startswith(f"trainer_ID{subject_id}_") and f.endswith(".yml"):
            try: os.remove(os.path.join(models_dir, f))
            except: pass

    save_lbph_model_safe(recognizer, model_save_path)
    return True, f"Model saved as: {filename}"