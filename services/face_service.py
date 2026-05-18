"""
====================================================================
Face Processing Service (Face Service)
====================================================================
Responsibilities:
1. Face detection using DNN (SSD ResNet-10)
2. Image preprocessing (CLAHE in LAB color space)
3. Embedding extraction (OpenFace) with L2 Normalization
4. Anti-Spoofing (Motion Detection and Eye Blink Detection)
5. Quality Assessment (Brightness, Sharpness, Size check)
6. Data Augmentation
"""

import cv2
import os
import sys
import shutil
import numpy as np

try:
    from services.logger_service import get_logger, measure_time, log_ai_event
    logger = get_logger("ai")
except ImportError:
    import logging
    logger = logging.getLogger("ai")


# ==================== Constants ====================
FACE_SIZE = (200, 200)
CLAHE_CLIP = 2.0
CLAHE_GRID = (8, 8)
MIN_FACE_SIZE = 80

# Quality Assessment thresholds
MIN_BRIGHTNESS = 40       # Minimum acceptable average brightness
MAX_BRIGHTNESS = 220      # Maximum acceptable average brightness
MIN_SHARPNESS = 50        # Minimum Laplacian variance (sharpness)
MAX_BLUR_THRESHOLD = 100

# CLAHE Singleton
_CLAHE = cv2.createCLAHE(clipLimit=CLAHE_CLIP, tileGridSize=CLAHE_GRID)


def get_base_dir():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def ensure_required_files():
    """Ensures Haar Cascade files exist in local path."""
    xml_files = ["haarcascade_frontalface_default.xml", "haarcascade_eye.xml"]
    cv2_path = os.path.dirname(cv2.__file__)
    cascade_path = os.path.join(cv2_path, 'data')
    base_dir = get_base_dir()
    for file in xml_files:
        dest = os.path.join(base_dir, "models", file)
        src = os.path.join(cascade_path, file)
        if not os.path.exists(dest) and os.path.exists(src):
            shutil.copy(src, dest)


# ==================== Quality Assessment ====================

def calculate_sharpness(image):
    """Calculates image sharpness using Laplacian variance."""
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    return cv2.Laplacian(gray, cv2.CV_64F).var()


def calculate_brightness(image):
    """Calculates average image brightness."""
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    return np.mean(gray)


def assess_face_quality(face_img):
    """
    Evaluates the quality of a cropped face image.
    Returns dictionary with quality score, status, and issues detected.
    """
    issues = []
    score = 100.0
    
    # 1. Size Check
    h, w = face_img.shape[:2]
    if w < MIN_FACE_SIZE or h < MIN_FACE_SIZE:
        issues.append(f"Küçük boyut ({w}x{h})")
        score -= 30
    
    # 2. Brightness Check
    brightness = calculate_brightness(face_img)
    if brightness < MIN_BRIGHTNESS:
        issues.append(f"Düşük ışık ({brightness:.0f})")
        score -= 25
    elif brightness > MAX_BRIGHTNESS:
        issues.append(f"Yüksek ışık ({brightness:.0f})")
        score -= 20
    
    # 3. Sharpness Check
    sharpness = calculate_sharpness(face_img)
    if sharpness < MIN_SHARPNESS:
        issues.append(f"Bulanık resim ({sharpness:.0f})")
        score -= 30
    
    score = max(0, score)
    is_good = score >= 60
    
    return {
        'is_good': is_good,
        'score': score,
        'brightness': brightness,
        'sharpness': sharpness,
        'size': (w, h),
        'issues': issues
    }


# ==================== Anti-Spoofing ====================

class MotionDetector:
    """
    Motion detector to prevent print/photo attacks.
    Compares consecutive frames; static prints exhibit near-zero change.
    """
    def __init__(self, history_size=10, motion_threshold=2.0):
        self.history = []
        self.history_size = history_size
        self.motion_threshold = motion_threshold
    
    def add_frame(self, face_region):
        """Adds a face frame to history."""
        if len(face_region.shape) == 3:
            gray = cv2.cvtColor(face_region, cv2.COLOR_BGR2GRAY)
        else:
            gray = face_region
        gray = cv2.resize(gray, (100, 100))  # Downsample for speed
        self.history.append(gray)
        if len(self.history) > self.history_size:
            self.history.pop(0)
    
    def is_alive(self):
        """Returns True if sufficient motion is observed across frames."""
        if len(self.history) < 5:
            return True  # Await more frames
        
        # Calculate differences between consecutive frames
        diffs = []
        for i in range(1, len(self.history)):
            diff = cv2.absdiff(self.history[i], self.history[i-1])
            diffs.append(np.mean(diff))
        
        avg_motion = np.mean(diffs)
        return avg_motion > self.motion_threshold


def detect_eye_blink(face_img):
    """Attempts to detect eye blinks using Haar eye cascades."""
    try:
        base_dir = get_base_dir()
        eye_cascade_path = os.path.join(base_dir, "models", "haarcascade_eye.xml")
        if not os.path.exists(eye_cascade_path):
            return None
        
        eye_cascade = cv2.CascadeClassifier(eye_cascade_path)
        gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY) if len(face_img.shape) == 3 else face_img
        eyes = eye_cascade.detectMultiScale(gray, 1.1, 5)
        return len(eyes)
    except Exception:
        return None


# ==================== Image Preprocessing ====================

def preprocess_face_color(bgr_face):
    """
    Normalizes color face size and CLAHE processes LAB space luminance channel.
    Ensures colors are preserved for OpenFace model inputs.
    """
    face_resized = cv2.resize(bgr_face, FACE_SIZE)
    lab = cv2.cvtColor(face_resized, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    l_enhanced = _CLAHE.apply(l)
    lab_enhanced = cv2.merge([l_enhanced, a, b])
    bgr_enhanced = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)
    return bgr_enhanced


def preprocess_face(gray_face):
    """Legacy preprocessing method."""
    face_resized = cv2.resize(gray_face, FACE_SIZE)
    return _CLAHE.apply(face_resized)


def augment_face_color(bgr_face):
    """
    Generates 5 augmented variants of a BGR face:
    1. Horizontal Flip
    2. Higher Brightness (+15)
    3. Lower Brightness (-15)
    4. Clockwise rotation (+5 degrees)
    5. Counter-clockwise rotation (-5 degrees)
    """
    augmented = []
    augmented.append(cv2.flip(bgr_face, 1))
    augmented.append(cv2.convertScaleAbs(bgr_face, alpha=1.15, beta=15))
    augmented.append(cv2.convertScaleAbs(bgr_face, alpha=0.85, beta=-15))
    
    h, w = bgr_face.shape[:2]
    M_pos = cv2.getRotationMatrix2D((w/2, h/2), 5, 1.0)
    augmented.append(cv2.warpAffine(bgr_face, M_pos, (w, h), borderMode=cv2.BORDER_REFLECT))
    M_neg = cv2.getRotationMatrix2D((w/2, h/2), -5, 1.0)
    augmented.append(cv2.warpAffine(bgr_face, M_neg, (w, h), borderMode=cv2.BORDER_REFLECT))
    
    return augmented


def augment_face(face_img):
    """Legacy augmentation method."""
    if len(face_img.shape) == 3:
        return augment_face_color(face_img)
    return [
        cv2.flip(face_img, 1),
        cv2.convertScaleAbs(face_img, alpha=1.2, beta=30),
        cv2.convertScaleAbs(face_img, alpha=0.8, beta=-30)
    ]


# ==================== Safe DNN Model Loading ====================

def get_resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


def load_dnn_model_safe(prototxt_path, model_path):
    """Loads Caffe DNN model safely, bypassing potential Windows Unicode path errors."""
    try:
        orig_cwd = os.getcwd()
        try:
            os.chdir(os.path.dirname(prototxt_path))
            return cv2.dnn.readNetFromCaffe(os.path.basename(prototxt_path), os.path.basename(model_path))
        finally:
            os.chdir(orig_cwd)
    except Exception as e:
        logger.warning(f"Unicode path issue, using fallback: {e}")
        import uuid
        safe_dir = os.path.join(os.environ.get('PUBLIC', 'C:\\'), f"dnn_temp_{uuid.uuid4().hex[:6]}")
        os.makedirs(safe_dir, exist_ok=True)
        safe_proto = os.path.join(safe_dir, "deploy.prototxt")
        safe_model = os.path.join(safe_dir, "model.caffemodel")
        shutil.copy(prototxt_path, safe_proto)
        shutil.copy(model_path, safe_model)
        try:
            return cv2.dnn.readNetFromCaffe(safe_proto, safe_model)
        finally:
            try:
                shutil.rmtree(safe_dir)
            except Exception:
                pass


def load_embedder_model_safe(model_path):
    """Loads Torch OpenFace model safely, bypassing potential Windows Unicode path errors."""
    try:
        orig_cwd = os.getcwd()
        try:
            os.chdir(os.path.dirname(model_path))
            return cv2.dnn.readNetFromTorch(os.path.basename(model_path))
        finally:
            os.chdir(orig_cwd)
    except Exception:
        import uuid
        safe_dir = os.path.join(os.environ.get('PUBLIC', 'C:\\'), f"dnn_temp_{uuid.uuid4().hex[:6]}")
        os.makedirs(safe_dir, exist_ok=True)
        safe_model = os.path.join(safe_dir, "model.t7")
        shutil.copy(model_path, safe_model)
        try:
            return cv2.dnn.readNetFromTorch(safe_model)
        finally:
            try:
                shutil.rmtree(safe_dir)
            except Exception:
                pass


# ==================== Embedding Extraction ====================

def get_face_embedding(face_img, embedder_net):
    """Extracts a 128-dimensional embedding from a cropped face image and L2 normalizes it."""
    if len(face_img.shape) == 2:
        face_img = cv2.cvtColor(face_img, cv2.COLOR_GRAY2BGR)
    
    # OpenFace expects a 96x96 RGB blob
    face_blob = cv2.dnn.blobFromImage(face_img, 1.0/255, (96, 96), (0, 0, 0), swapRB=True, crop=False)
    embedder_net.setInput(face_blob)
    vec = embedder_net.forward()
    vec = vec.flatten()
    
    # L2 Normalization (required for precise Euclidean comparison)
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    
    return vec


# ==================== Face Capture ====================

def capture_face_dataset(uni_id):
    """
    Captures face dataset from camera.
    Evaluates quality and generates augmented variations.
    """
    ensure_required_files()
    base_dir = get_base_dir()
    prototxt_path = get_resource_path(os.path.join("models", "dnn_model", "deploy.prototxt"))
    model_path = get_resource_path(os.path.join("models", "dnn_model", "res10_300x300_ssd_iter_140000.caffemodel"))
    
    if not os.path.exists(prototxt_path) or not os.path.exists(model_path):
        logger.error("DNN model files not found")
        raise FileNotFoundError("DNN model files not found.")
    
    net = load_dnn_model_safe(prototxt_path, model_path)
    dataset_dir = os.path.join(base_dir, "dataset")
    os.makedirs(dataset_dir, exist_ok=True)
    
    logger.info(f"Öğrenci veri yakalama başlatıldı: {uni_id}")
    
    cam = cv2.VideoCapture(0)
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    count = 0
    rejected = 0
    TARGET_ORIGINAL = 60
    AUGMENT_PER_IMAGE = 5
    
    try:
        while True:
            ret, img = cam.read()
            if not ret:
                break
            
            h_img, w_img = img.shape[:2]
            blob = cv2.dnn.blobFromImage(cv2.resize(img, (300, 300)), 1.0, (300, 300), (104.0, 177.0, 123.0))
            net.setInput(blob)
            detections = net.forward()
            
            # Identify the largest face in frame
            best_face = None
            best_area = 0
            
            for i in range(detections.shape[2]):
                confidence = detections[0, 0, i, 2]
                if confidence > 0.7:
                    box = detections[0, 0, i, 3:7] * np.array([w_img, h_img, w_img, h_img])
                    (startX, startY, endX, endY) = box.astype("int")
                    
                    face_w_orig = endX - startX
                    face_h_orig = endY - startY
                    
                    if face_w_orig < MIN_FACE_SIZE or face_h_orig < MIN_FACE_SIZE:
                        continue
                    
                    pad_x = int(face_w_orig * 0.15)
                    pad_y = int(face_h_orig * 0.15)
                    
                    startX = max(0, startX - pad_x)
                    startY = max(0, startY - pad_y)
                    endX = min(w_img, endX + pad_x)
                    endY = min(h_img, endY + pad_y)
                    
                    area = face_w_orig * face_h_orig
                    if area > best_area:
                        best_area = area
                        best_face = (startX, startY, endX, endY)
            
            if best_face:
                startX, startY, endX, endY = best_face
                face_roi = img[startY:endY, startX:endX]
                
                if face_roi.size > 0:
                    quality = assess_face_quality(face_roi)
                    
                    if quality['is_good']:
                        processed_face = preprocess_face_color(face_roi)
                        
                        cv2.rectangle(img, (startX, startY), (endX, endY), (0, 255, 0), 2)
                        count += 1
                        cv2.imwrite(os.path.join(dataset_dir, f"User.{uni_id}.{count}.jpg"), processed_face)
                        
                        for aug_face in augment_face_color(processed_face):
                            count += 1
                            cv2.imwrite(os.path.join(dataset_dir, f"User.{uni_id}.{count}.jpg"), aug_face)
                        
                        original_count = count // (1 + AUGMENT_PER_IMAGE)
                        
                        # Draw status overlay
                        cv2.putText(img, f"Kaydedilen: {original_count}/{TARGET_ORIGINAL}",
                                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                        cv2.putText(img, f"Kalite: {quality['score']:.0f}/100",
                                    (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                        cv2.putText(img, "Basinizi yavasca hareket ettirin: yukari, asagi, sol, sag",
                                    (10, h_img - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
                        
                        if original_count >= TARGET_ORIGINAL:
                            break
                    else:
                        rejected += 1
                        cv2.rectangle(img, (startX, startY), (endX, endY), (0, 165, 255), 2)
                        issue_text = ", ".join(quality['issues'][:2])
                        cv2.putText(img, f"Dusuk kalite: {issue_text}",
                                    (startX, startY - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 1)
            else:
                cv2.putText(img, "Yuzunuzu kameraya ortalayin",
                            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            
            cv2.imshow('Face Capture', img)
            original_count = count // (1 + AUGMENT_PER_IMAGE)
            if cv2.waitKey(10) & 0xFF == 27 or original_count >= TARGET_ORIGINAL:
                break
    finally:
        cam.release()
        cv2.destroyAllWindows()
        logger.info(f"Öğrenci {uni_id} veri yakalama tamamlandı: Kabul={count}, Reddedilen={rejected}")
        try:
            log_ai_event("CAPTURE_COMPLETE", student_id=uni_id, accepted=count, rejected=rejected)
        except:
            pass
    
    return (count // (1 + AUGMENT_PER_IMAGE)) >= TARGET_ORIGINAL