import cv2
import os
import shutil
import numpy as np

# --- Image processing constants (must be identical in training and recognition) ---
FACE_SIZE = (200, 200)
CLAHE_CLIP = 2.0
CLAHE_GRID = (8, 8)

# --- Create CLAHE only once (Singleton) to avoid recreating it every frame ---
_CLAHE = cv2.createCLAHE(clipLimit=CLAHE_CLIP, tileGridSize=CLAHE_GRID)

def get_base_dir():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def ensure_required_files():
    xml_files = ["haarcascade_frontalface_default.xml", "haarcascade_smile.xml", "haarcascade_eye.xml"]
    cv2_path = os.path.dirname(cv2.__file__)
    cascade_path = os.path.join(cv2_path, 'data')
    base_dir = get_base_dir()
    for file in xml_files:
        dest = os.path.join(base_dir, "models", file)
        src = os.path.join(cascade_path, file)
        if not os.path.exists(dest) and os.path.exists(src):
            shutil.copy(src, dest)

def preprocess_face(gray_face):
    """
    Apply uniform preprocessing on the face image.
    The same function is used in training and attendance session to ensure compatibility.
    Uses the unified _CLAHE (Singleton) instead of creating a new object every frame.
    """
    # 1. Resize
    face_resized = cv2.resize(gray_face, FACE_SIZE)
    # 2. Enhance contrast using pre-initialized CLAHE
    face_enhanced = _CLAHE.apply(face_resized)
    return face_enhanced

def augment_face(face_img):
    """
    Generate augmented versions of the face image to increase training data variety.
    Returns a list of additional images (without the original).
    """
    augmented = []
    # Horizontally flipped version
    augmented.append(cv2.flip(face_img, 1))
    # Brighter version
    augmented.append(cv2.convertScaleAbs(face_img, alpha=1.2, beta=30))
    # Darker version
    augmented.append(cv2.convertScaleAbs(face_img, alpha=0.8, beta=-30))
    return augmented

def capture_face_dataset(uni_id):
    ensure_required_files()
    base_dir = get_base_dir()
    prototxt_path = os.path.join(base_dir, "models", "dnn_model", "deploy.prototxt")
    model_path = os.path.join(base_dir, "models", "dnn_model", "res10_300x300_ssd_iter_140000.caffemodel")
    if not os.path.exists(prototxt_path) or not os.path.exists(model_path):
        raise FileNotFoundError("DNN model files not found.")
    net = cv2.dnn.readNetFromCaffe(prototxt_path, model_path)
    dataset_dir = os.path.join(base_dir, "dataset")
    if not os.path.exists(dataset_dir): os.makedirs(dataset_dir)
    cam = cv2.VideoCapture(0)
    count = 0
    # We only need 100 original images (3 augmented versions will be generated for each during training)
    TARGET_ORIGINAL = 100
    try:
        while True:
            ret, img = cam.read()
            if not ret: break
            h_img, w_img = img.shape[:2]
            blob = cv2.dnn.blobFromImage(cv2.resize(img, (300, 300)), 1.0, (300, 300), (104.0, 177.0, 123.0))
            net.setInput(blob)
            detections = net.forward()
            for i in range(0, detections.shape[2]):
                confidence = detections[0, 0, i, 2]
                if confidence > 0.5:
                    box = detections[0, 0, i, 3:7] * np.array([w_img, h_img, w_img, h_img])
                    (startX, startY, endX, endY) = box.astype("int")
                    startX, startY = max(0, startX), max(0, startY)
                    endX, endY = min(w_img, endX), min(h_img, endY)
                    face_roi = img[startY:endY, startX:endX]
                    if face_roi.size == 0: continue
                    gray_face = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)

                    # --- Enhance image and standardize size ---
                    processed_face = preprocess_face(gray_face)

                    cv2.rectangle(img, (startX, startY), (endX, endY), (255, 0, 0), 2)
                    count += 1
                    # Save enhanced original image
                    cv2.imwrite(os.path.join(dataset_dir, f"User.{uni_id}.{count}.jpg"), processed_face)

                    # --- Data Augmentation: Save augmented versions ---
                    for aug_face in augment_face(processed_face):
                        count += 1
                        cv2.imwrite(os.path.join(dataset_dir, f"User.{uni_id}.{count}.jpg"), aug_face)

                    # Show progress info on screen
                    original_count = count // 4  # Each original image generates 4 images (1 + 3 augmented)
                    cv2.putText(img, f"Captured: {original_count}/{TARGET_ORIGINAL}",
                                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

                    if original_count >= TARGET_ORIGINAL: break

            cv2.imshow('Face Capture', img)
            original_count = count // 4
            if cv2.waitKey(10) & 0xFF == 27 or original_count >= TARGET_ORIGINAL: break
    finally:
        cam.release()
        cv2.destroyAllWindows()
    return (count // 4) >= TARGET_ORIGINAL
