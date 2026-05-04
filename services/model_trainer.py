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

def train_lbph_model(subject_id=None):
    """
    Trains a model with a descriptive filename.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dataset_path = os.path.join(base_dir, "dataset")
    
    if subject_id:
        filename = get_model_filename(subject_id)
        model_save_path = os.path.join(base_dir, "models", filename)
        allowed_ids = db_service.get_enrolled_university_ids(subject_id)
    else:
        model_save_path = os.path.join(base_dir, "models", "trainer_global.yml")
        allowed_ids = None

    recognizer = cv2.face.LBPHFaceRecognizer_create()
    
    if not os.path.exists(dataset_path):
        return False, "Dataset folder not found."

    image_paths = [os.path.join(dataset_path, f) for f in os.listdir(dataset_path) if f.endswith('.jpg')]
    
    face_samples = []
    ids = []

    for image_path in image_paths:
        try:
            student_uni_id = int(os.path.split(image_path)[-1].split(".")[1])
            if allowed_ids is not None and student_uni_id not in allowed_ids:
                continue
            img_numpy = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
            if img_numpy is None: continue
            face_samples.append(img_numpy)
            ids.append(student_uni_id)
        except: continue

    if not face_samples:
        return False, "No training images found."

    recognizer.train(face_samples, np.array(ids))
    
    # Remove old models for this subject ID to avoid duplicates with different names
    models_dir = os.path.join(base_dir, "models")
    for f in os.listdir(models_dir):
        if f.startswith(f"trainer_ID{subject_id}_") and f.endswith(".yml"):
            try: os.remove(os.path.join(models_dir, f))
            except: pass

    recognizer.write(model_save_path)
    return True, f"Model saved as: {filename}"