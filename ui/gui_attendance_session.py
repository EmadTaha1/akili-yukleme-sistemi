"""
====================================================================
Live Attendance Session GUI
====================================================================
Responsibilities:
1. Capture real-time video stream (Multi-threaded CameraThread)
2. Detect student faces using SSD ResNet DNN
3. Multi-face tracking using IoU thresholding (FaceTracker)
4. Robust KNN-based recognition with strict dynamic threshold clamping
5. Real-time anti-spoofing via structural frame motion checks
6. Beautiful overlay overlays displaying FPS, match counts, and times
"""

import os
import customtkinter as ctk
import sqlite3
import cv2
import numpy as np
from datetime import datetime
from tkinter import messagebox
import glob
import sys
import time
import threading
from queue import Queue, Empty
from collections import deque

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.append(root_dir)

from services.face_service import (
    preprocess_face_color, get_face_embedding,
    load_embedder_model_safe, MIN_FACE_SIZE,
    MotionDetector, assess_face_quality
)
from services import notification_service
from services import backup_service
from services.stats_service import LiveSessionStats

try:
    from services.logger_service import get_logger, log_attendance_event
    logger = get_logger("attendance")
except ImportError:
    import logging
    logger = logging.getLogger("attendance")

import pickle


# ==================== Recognition Constants ====================
DISTANCE_THRESHOLD = 0.65
STRICT_THRESHOLD = 0.50
MARGIN_RATIO = 0.85
K_NEIGHBORS = 3
REQUIRED_VOTES = 4
MAX_MISSING_FRAMES = 15

# ==================== Smoothing Constants ====================
SMOOTHING_WINDOW = 5
CONFIDENCE_THRESHOLD = 0.6
HYSTERESIS_MARGIN = 0.05
IOU_THRESHOLD = 0.3

# ==================== Anti-Spoofing Constants ====================
ENABLE_ANTI_SPOOFING = True
MOTION_HISTORY_SIZE = 10
MOTION_THRESHOLD = 1.5

# ==================== Multi-threading Configuration ====================
FRAME_QUEUE_SIZE = 2


# ==================== Camera Thread ====================
class CameraThread(threading.Thread):
    """
    Dedicated camera decoding thread.
    Retrieves camera frames asynchronously in a background loop to ensure smooth UI responsiveness.
    """
    def __init__(self, src=0, width=1280, height=720):
        super().__init__()
        self.daemon = True
        self.cap = cv2.VideoCapture(src)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Buffer size set to 1 for latest frame focus
        self.frame_queue = Queue(maxsize=FRAME_QUEUE_SIZE)
        self.running = False
        self.frame_count = 0
    
    def run(self):
        self.running = True
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.01)
                continue
            
            self.frame_count += 1
            
            # Keep queue clean by dropping obsolete frames
            if self.frame_queue.full():
                try:
                    self.frame_queue.get_nowait()
                except Empty:
                    pass
            
            self.frame_queue.put(frame)
    
    def get_frame(self, timeout=0.1):
        try:
            return self.frame_queue.get(timeout=timeout)
        except Empty:
            return None
    
    def stop(self):
        self.running = False
        time.sleep(0.1)
        self.cap.release()


# ==================== Face Tracker ====================
def calculate_iou(box1, box2):
    """Computes Intersection over Union (IoU) of two bounding boxes."""
    x1_1, y1_1, x2_1, y2_1 = box1
    x1_2, y1_2, x2_2, y2_2 = box2
    
    xi1 = max(x1_1, x1_2)
    yi1 = max(y1_1, y1_2)
    xi2 = min(x2_1, x2_2)
    yi2 = min(y2_1, y2_2)
    
    inter = max(0, xi2 - xi1) * max(0, yi2 - yi1)
    area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
    area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
    union = area1 + area2 - inter
    
    return inter / union if union > 0 else 0.0


class FaceTracker:
    """Manages spatial tracking and state smoothing for a single face region."""
    def __init__(self, box, face_id):
        self.box = box
        self.face_id = face_id
        self.last_seen = 0
        self.history = deque(maxlen=SMOOTHING_WINDOW)
        self.vote_count = 0
        self.stable_id = -1
        self.stable_distance = float('inf')
        self.stable_confidence = 'unknown'
        
        # Micro-motion tracker for live face assurance
        self.motion_detector = MotionDetector(MOTION_HISTORY_SIZE, MOTION_THRESHOLD)
        self.is_live = True
    
    def update(self, box, predicted_id, distance, confidence_level, frame_num, face_roi=None):
        self.box = box
        self.last_seen = frame_num
        self.history.append({
            'id': predicted_id,
            'distance': distance,
            'confidence': confidence_level
        })
        
        # Update structural motion parameters
        if ENABLE_ANTI_SPOOFING and face_roi is not None:
            self.motion_detector.add_frame(face_roi)
            self.is_live = self.motion_detector.is_alive()
        
        if len(self.history) >= 3:
            self._compute_stable_decision()
    
    def _compute_stable_decision(self):
        if not self.history:
            return
        
        id_votes = {}
        distances = []
        
        for entry in self.history:
            pred_id = entry['id']
            id_votes[pred_id] = id_votes.get(pred_id, 0) + 1
            if pred_id != -1:
                distances.append(entry['distance'])
        
        if id_votes:
            most_common_id = max(id_votes, key=id_votes.get)
            vote_ratio = id_votes[most_common_id] / len(self.history)
            
            threshold = CONFIDENCE_THRESHOLD
            if self.stable_id != -1 and most_common_id != self.stable_id:
                threshold = 0.7
            
            if vote_ratio >= threshold:
                avg_distance = np.mean(distances) if distances else float('inf')
                effective_threshold = DISTANCE_THRESHOLD
                if self.stable_id == most_common_id:
                    effective_threshold += HYSTERESIS_MARGIN
                
                if avg_distance < effective_threshold:
                    self.stable_id = most_common_id
                    self.stable_distance = avg_distance
                    
                    if avg_distance < STRICT_THRESHOLD:
                        self.stable_confidence = 'high'
                    elif avg_distance < DISTANCE_THRESHOLD:
                        self.stable_confidence = 'medium'
                    else:
                        self.stable_confidence = 'low'
                else:
                    self.stable_id = -1
                    self.stable_confidence = 'unknown'
            else:
                if vote_ratio < 0.4:
                    self.stable_id = -1
                    self.stable_confidence = 'unknown'
    
    def get_stable_result(self):
        return self.stable_id, self.stable_distance, self.stable_confidence
    
    def is_same_face(self, box):
        return calculate_iou(self.box, box) > IOU_THRESHOLD


# ==================== Recognition Logic ====================
def identify_face_knn(face_vec, model_data, k=K_NEIGHBORS):
    """
    Classifies a face vector using k-NN with distance margins and adaptive thresholds.
    """
    embeddings_dict = model_data['embeddings']
    thresholds = model_data.get('thresholds', {})
    
    all_distances = []
    for sid, vecs_array in embeddings_dict.items():
        diffs = vecs_array - face_vec
        dists = np.linalg.norm(diffs, axis=1)
        for d in dists:
            all_distances.append((d, sid))
    
    if not all_distances:
        return -1, float('inf'), 'unknown'
    
    all_distances.sort(key=lambda x: x[0])
    top_k = all_distances[:k]
    
    votes = {}
    for dist, sid in top_k:
        weight = 1.0 / (dist + 1e-6)
        votes[sid] = votes.get(sid, 0) + weight
    
    best_sid = max(votes, key=votes.get)
    best_dist = min(d for d, s in top_k if s == best_sid)
    
    second_best_dist = float('inf')
    for d, s in all_distances:
        if s != best_sid:
            second_best_dist = d
            break
    
    # Retrieve secure clamped threshold for this particular student
    effective_threshold = thresholds.get(best_sid, DISTANCE_THRESHOLD)
    
    if best_dist > effective_threshold:
        return -1, best_dist, 'unknown'
    
    margin_ok = (best_dist < second_best_dist * MARGIN_RATIO)
    
    if best_dist < STRICT_THRESHOLD and margin_ok:
        return best_sid, best_dist, 'high'
    elif best_dist < effective_threshold and margin_ok:
        return best_sid, best_dist, 'medium'
    else:
        return -1, best_dist, 'unknown'


# ==================== Utilities ====================
def get_db_path():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, "database", "attendance_system.db")


def get_subjects_from_db(teacher_id=1):
    try:
        with sqlite3.connect(get_db_path()) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT subject_id, course_code, subject_name, study_year FROM Subjects WHERE teacher_id = ?", (teacher_id,))
            rows = cursor.fetchall()
            return [f"{row[0]} - [{row[1]}] {row[2]} ({row[3]})" for row in rows]
    except Exception:
        return []


def find_model_file(base_dir, subject_id):
    pattern = os.path.join(base_dir, "models", f"trainer_ID{subject_id}_*.pkl")
    files = glob.glob(pattern)
    return files[0] if files else None


def get_resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


def load_dnn_model_safe(prototxt_path, model_path):
    try:
        orig_cwd = os.getcwd()
        try:
            os.chdir(os.path.dirname(prototxt_path))
            return cv2.dnn.readNetFromCaffe(os.path.basename(prototxt_path), os.path.basename(model_path))
        finally:
            os.chdir(orig_cwd)
    except Exception:
        import shutil
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


# ==================== UI Overlay ====================
def draw_dashboard_overlay(img, stats, fps, paused=False):
    """Draws a premium translucent information header and shortcut bar onto the live feed."""
    h, w = img.shape[:2]
    
    # Translucent top bar
    overlay = img.copy()
    cv2.rectangle(overlay, (0, 0), (w, 80), (0, 0, 0), -1)
    img = cv2.addWeighted(overlay, 0.6, img, 0.4, 0)
    
    # Top stats
    text1 = f"Katilan: {stats['attended']}/{stats['total']}"
    text2 = f"Dogruluk: {stats['recognition_accuracy']}%"
    text3 = f"FPS: {fps:.1f}"
    
    cv2.putText(img, text1, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    cv2.putText(img, text2, (200, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 255), 2)
    cv2.putText(img, text3, (400, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 200, 0), 2)
    
    # Elapsed duration
    elapsed = int(stats['elapsed_seconds'])
    mins, secs = divmod(elapsed, 60)
    time_text = f"Sure: {mins:02d}:{secs:02d}"
    cv2.putText(img, time_text, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
    
    # Paused status indicator
    if paused:
        cv2.putText(img, "⏸ DURAKLATILDI", (w - 240, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
    
    # Bottom hotkeys bar
    cv2.rectangle(img, (0, h - 30), (w, h), (0, 0, 0), -1)
    shortcuts = "[ESC]Cikis  [P]Duraklat  [S]Hizli Kaydet  [R]Sifirla  [I]Bilgi"
    cv2.putText(img, shortcuts, (10, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
    
    return img


# ==================== Core Session Loop ====================
def start_attendance_session(subject_selection, week_selection, teacher_id=1, cam_src=0):
    """Launches the multi-threaded video stream and controls state for active attendance tracking."""
    
    # Input verification
    if not subject_selection or "No" in subject_selection or subject_selection == "Ders Seçin":
        messagebox.showerror("Hata", "Lütfen geçerli bir ders seçin!")
        return
    
    subject_id = int(subject_selection.split(" - ")[0])
    week_number = int(week_selection.split(".")[0])
    today_date = datetime.now().strftime("%Y-%m-%d")
    
    logger.info(f"Oturum başladı: ders={subject_id}, hafta={week_number}, tarih={today_date}")
    
    # Auto-backup execution prior to data logging
    try:
        backup_service.create_database_backup()
        logger.info("✅ Oturum öncesi yedek alındı")
    except Exception as e:
        logger.warning(f"Yedekleme başarısız oldu: {e}")
    
    # Load AI models
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    model_path = find_model_file(base_dir, subject_id)
    
    if not model_path:
        messagebox.showerror("Hata", "Bu ders için AI modeli bulunamadı. Lütfen önce eğitin.")
        return
    
    try:
        with open(model_path, 'rb') as f:
            model_data = pickle.load(f)
        if not isinstance(model_data, dict) or 'embeddings' not in model_data:
            messagebox.showerror("Hata", "Model eski formatta. Lütfen yeniden eğitin.")
            return
        logger.info(f"Model yüklendi: {len(model_data['embeddings'])} öğrenci")
    except Exception as e:
        logger.error(f"Model yükleme başarısız oldu: {e}")
        messagebox.showerror("Hata", f"Model yüklenemedi: {e}")
        return
    
    # Initialize neural net models safely
    prototxt_path = get_resource_path(os.path.join("models", "dnn_model", "deploy.prototxt"))
    dnn_model_path = get_resource_path(os.path.join("models", "dnn_model", "res10_300x300_ssd_iter_140000.caffemodel"))
    try:
        net = load_dnn_model_safe(prototxt_path, dnn_model_path)
    except:
        messagebox.showerror("Hata", "Yüz dedektör modelleri bulunamadı.")
        return
    
    embedder_model_path = get_resource_path(os.path.join("models", "dnn_model", "openface_nn4.small2.v1.t7"))
    try:
        embedder_net = load_embedder_model_safe(embedder_model_path)
    except:
        messagebox.showerror("Hata", "OpenFace modeli bulunamadı.")
        return
    
    # Load student lists
    with sqlite3.connect(get_db_path()) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT Students.student_id, Students.university_id, Students.name, Students.email
            FROM Enrollments
            JOIN Students ON Enrollments.student_id = Students.student_id
            WHERE Enrollments.subject_id = ?
        ''', (subject_id,))
        enrolled_students = cursor.fetchall()
        
        if not enrolled_students:
            messagebox.showwarning("Uyarı", "Bu derse kayıtlı öğrenci yok.")
            return
        
        student_dict = {int(row[0]): row[2] for row in enrolled_students}
        previously_attended = set()
        cursor.execute('''
            SELECT e.student_id FROM Attendance a
            JOIN Enrollments e ON a.enrollment_id = e.enrollment_id
            WHERE e.subject_id = ? AND a.date = ? AND a.status = 'Present' AND a.week_number = ?
        ''', (subject_id, today_date, week_number))
        for row in cursor.fetchall():
            previously_attended.add(int(row[0]))
    
    # Initialize states and tracker histories
    attended_today = set()
    face_trackers = []
    next_face_id = 0
    frame_num = 0
    
    live_stats = LiveSessionStats(total_students=len(enrolled_students))
    
    # Launch concurrent frame decoding
    camera = CameraThread(src=cam_src, width=1280, height=720)
    camera.start()
    time.sleep(0.5)  # Await initialization latency
    
    logger.info("📷 Kamera başlatıldı")
    
    # Local loop statuses
    paused = False
    show_info = False
    last_fps_time = time.time()
    fps_counter = 0
    current_fps = 0

    try:
        while True:
            # Capture frame
            img = camera.get_frame()
            if img is None:
                continue
            
            frame_num += 1
            h_img, w_img = img.shape[:2]
            
            # FPS tracking
            fps_counter += 1
            current_time = time.time()
            if current_time - last_fps_time >= 1.0:
                current_fps = fps_counter / (current_time - last_fps_time)
                live_stats.record_fps(current_fps)
                fps_counter = 0
                last_fps_time = current_time
            
            # Handle Pause Mode
            if paused:
                img = draw_dashboard_overlay(img, live_stats.get_current_stats(), current_fps, paused=True)
                cv2.imshow('Yoklama Sistemi', img)
                key = cv2.waitKey(50) & 0xFF
                if key == 27:
                    break
                elif key == ord('p') or key == ord('P'):
                    paused = False
                continue
            
            # Face Detection
            blob = cv2.dnn.blobFromImage(cv2.resize(img, (300, 300)), 1.0, (300, 300), (104.0, 177.0, 123.0))
            net.setInput(blob)
            detections = net.forward()
            
            detected_faces = []
            for i in range(detections.shape[2]):
                confidence = detections[0, 0, i, 2]
                if confidence > 0.6:
                    box = detections[0, 0, i, 3:7] * np.array([w_img, h_img, w_img, h_img])
                    (startX, startY, endX, endY) = box.astype("int")
                    
                    face_w_orig = endX - startX
                    face_h_orig = endY - startY
                    
                    if face_w_orig < MIN_FACE_SIZE or face_h_orig < MIN_FACE_SIZE:
                        continue
                    
                    # Apply 15% padding for OpenFace
                    pad_x = int(face_w_orig * 0.15)
                    pad_y = int(face_h_orig * 0.15)
                    
                    startX = max(0, startX - pad_x)
                    startY = max(0, startY - pad_y)
                    endX = min(w_img, endX + pad_x)
                    endY = min(h_img, endY + pad_y)
                    
                    detected_faces.append((startX, startY, endX, endY))
            
            # Process observed faces
            for box in detected_faces:
                startX, startY, endX, endY = box
                
                matched_tracker = None
                for tracker in face_trackers:
                    if tracker.is_same_face(box):
                        matched_tracker = tracker
                        break
                
                face_roi = img[startY:endY, startX:endX]
                if face_roi.size == 0:
                    continue
                
                # Quality Check
                quality = assess_face_quality(face_roi)
                
                if not quality['is_good']:
                    cv2.rectangle(img, (startX, startY), (endX, endY), (128, 128, 128), 1)
                    cv2.putText(img, f"Dusuk Kalite ({quality['score']:.0f})",
                                (startX, startY - 5), 0, 0.4, (128, 128, 128), 1)
                    continue
                
                processed_face = preprocess_face_color(face_roi)
                vec = get_face_embedding(processed_face, embedder_net)
                
                predicted_id, min_dist, confidence_level = identify_face_knn(vec, model_data)
                live_stats.record_recognition(predicted_id != -1)
                
                if matched_tracker:
                    matched_tracker.update(box, predicted_id, min_dist, confidence_level, frame_num, face_roi)
                else:
                    new_tracker = FaceTracker(box, next_face_id)
                    next_face_id += 1
                    new_tracker.update(box, predicted_id, min_dist, confidence_level, frame_num, face_roi)
                    face_trackers.append(new_tracker)
                    matched_tracker = new_tracker
                
                stable_id, stable_dist, stable_conf = matched_tracker.get_stable_result()
                
                # Anti-Spoofing Check
                if ENABLE_ANTI_SPOOFING and not matched_tracker.is_live:
                    cv2.rectangle(img, (startX, startY), (endX, endY), (0, 0, 255), 3)
                    cv2.putText(img, "TAKILIT/SPOOF UYARISI!",
                                (startX, startY - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                    cv2.putText(img, "(hareketsiz = fotograf)",
                                (startX, endY + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)
                    continue
                
                # Render results
                if stable_conf == 'unknown' or stable_id == -1:
                    cv2.rectangle(img, (startX, startY), (endX, endY), (0, 0, 255), 2)
                    cv2.putText(img, "BILINMEYEN", (startX, startY - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                    cv2.putText(img, f"d:{stable_dist:.2f}", (startX, endY + 15),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
                    live_stats.record_unknown()
                    continue
                
                if stable_id not in student_dict:
                    cv2.rectangle(img, (startX, startY), (endX, endY), (0, 165, 255), 2)
                    cv2.putText(img, f"Kayitli Degil (ID:{stable_id})",
                                (startX, startY - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)
                    continue
                
                name = student_dict[stable_id]
                color_map = {'high': (0, 255, 0), 'medium': (0, 200, 255), 'low': (0, 150, 255)}
                color = color_map.get(stable_conf, (0, 200, 255))
                
                if stable_id in attended_today:
                    cv2.rectangle(img, (startX, startY), (endX, endY), (0, 255, 0), 3)
                    cv2.putText(img, f"{name} Tamam", (startX, startY - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                elif stable_id in previously_attended:
                    cv2.rectangle(img, (startX, startY), (endX, endY), (255, 255, 0), 2)
                    cv2.putText(img, f"{name} (Kayitli)",
                                (startX, startY - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
                else:
                    matched_tracker.vote_count += 1
                    votes = matched_tracker.vote_count
                    
                    progress = int((votes / REQUIRED_VOTES) * (endX - startX))
                    cv2.rectangle(img, (startX, endY + 4), (startX + progress, endY + 12), color, -1)
                    cv2.rectangle(img, (startX, startY), (endX, endY), color, 2)
                    cv2.putText(img, f"{name} ({votes}/{REQUIRED_VOTES})",
                                (startX, startY - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                    
                    if show_info:
                        cv2.putText(img, f"d:{stable_dist:.2f} q:{quality['score']:.0f}",
                                    (startX, endY + 28), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
                    
                    if votes >= REQUIRED_VOTES:
                        attended_today.add(stable_id)
                        matched_tracker.vote_count = 0
                        live_stats.record_attendance()
                        logger.info(f"✅ Katılım: {name} (ID:{stable_id}) mesafe={stable_dist:.3f}")
                        try:
                            log_attendance_event("MARKED_PRESENT", stable_id, name=name, distance=stable_dist)
                        except:
                            pass
            
            # Prune obsolete trackers
            face_trackers = [t for t in face_trackers if frame_num - t.last_seen <= MAX_MISSING_FRAMES]
            
            # Draw header dashboard
            img = draw_dashboard_overlay(img, live_stats.get_current_stats(), current_fps)
            
            cv2.imshow('Yoklama Sistemi', img)
            
            # Hotkeys processing
            key = cv2.waitKey(1) & 0xFF
            if key == 27:  # ESC
                logger.info("Oturum ESC ile sonlandırıldı")
                break
            elif key == ord('p') or key == ord('P'):
                paused = True
                logger.info("⏸ Oturum duraklatıldı")
            elif key == ord('s') or key == ord('S'):
                logger.info("💾 Hızlı kaydetme")
                _save_attendance_to_db(enrolled_students, subject_id, today_date,
                                       week_number, previously_attended, attended_today)
            elif key == ord('r') or key == ord('R'):
                face_trackers.clear()
                logger.info("🔄 İzleyiciler sıfırlandı")
            elif key == ord('i') or key == ord('I'):
                show_info = not show_info
                logger.info(f"Ek bilgi: {show_info}")
    
    finally:
        camera.stop()
        cv2.destroyAllWindows()
        logger.info(f"Oturum bitti - Katılanlar: {len(attended_today)}")
    
    # Save final logged records
    _save_attendance_to_db(enrolled_students, subject_id, today_date,
                           week_number, previously_attended, attended_today)
    
    # Absence notification emails trigger
    _ask_send_emails(enrolled_students, previously_attended, attended_today,
                     subject_selection, today_date, week_number, teacher_id)
    
    # final stats display box
    final_stats = live_stats.get_current_stats()
    messagebox.showinfo(
        "Oturum Tamamlandı",
        f"✅ Yoklama kaydedildi\n\n"
        f"Katılan öğrenci: {len(attended_today)}\n"
        f"Toplam öğrenci: {len(enrolled_students)}\n"
        f"Katılım oranı: {final_stats['attendance_rate']}%\n"
        f"Süre: {int(final_stats['elapsed_seconds'])} saniye"
    )


def _save_attendance_to_db(enrolled_students, subject_id, today_date,
                            week_number, previously_attended, attended_today):
    """Commits compiled active session records into SQLite database."""
    try:
        with sqlite3.connect(get_db_path()) as conn:
            cursor = conn.cursor()
            for student in enrolled_students:
                db_student_id = student[0]
                status = "Present" if (db_student_id in previously_attended or db_student_id in attended_today) else "Absent"
                cursor.execute("SELECT enrollment_id FROM Enrollments WHERE student_id=? AND subject_id=?",
                               (db_student_id, subject_id))
                enrollment_id = cursor.fetchone()[0]
                cursor.execute("SELECT attendance_id, status FROM Attendance WHERE enrollment_id=? AND date=? AND week_number=?",
                               (enrollment_id, today_date, week_number))
                exist = cursor.fetchone()
                if exist:
                    if exist[1] == "Absent" and status == "Present":
                        cursor.execute("UPDATE Attendance SET status=? WHERE attendance_id=?", (status, exist[0]))
                else:
                    cursor.execute("INSERT INTO Attendance (enrollment_id, date, week_number, status) VALUES (?, ?, ?, ?)",
                                   (enrollment_id, today_date, week_number, status))
            conn.commit()
        logger.info("✅ Sonuçlar veritabanına kaydedildi")
    except Exception as e:
        logger.error(f"Kaydetme başarısız oldu: {e}")


def _ask_send_emails(enrolled_students, previously_attended, attended_today,
                      subject_selection, today_date, week_number, teacher_id):
    """Triggers SMTP email dispatch routines for absent students."""
    if not messagebox.askyesno("E-posta Bildirimi",
                                "Derse katılmayan öğrencilere uyarı e-postası göndermek ister misiniz?"):
        return
    
    with sqlite3.connect(get_db_path()) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT email, gmail_app_password FROM Teachers WHERE teacher_id = ?", (teacher_id,))
        row = cursor.fetchone()
        teacher_email = row[0]
        app_password = row[1] if row[1] else ""
    
    # If not saved, prompt the user
    if not app_password:
        dialog = ctk.CTkInputDialog(text="Gmail Uygulama Şifrenizi (App Password) girin:",
                                     title="E-posta Gönderimi")
        app_password = dialog.get_input()
        
        if not app_password:
            return
            
        # Ask to save permanently
        if messagebox.askyesno("Şifreyi Kaydet", "Bu şifreyi sonraki kullanımlar için kalıcı olarak kaydetmek ister misiniz?"):
            try:
                with sqlite3.connect(get_db_path()) as conn:
                    cursor = conn.cursor()
                    cursor.execute("UPDATE Teachers SET gmail_app_password = ? WHERE teacher_id = ?", (app_password, teacher_id))
                    conn.commit()
                logger.info("🔑 Gmail şifresi başarıyla kaydedildi")
            except Exception as e:
                logger.error(f"Şifre kaydedilemedi: {e}")
    
    subject_name = subject_selection.split("] ")[1]
    sent_count = 0
    fail_count = 0
    
    for student in enrolled_students:
        db_student_id, _, s_name, s_email = student
        status = "Present" if (db_student_id in previously_attended or db_student_id in attended_today) else "Absent"
        
        if status == "Absent" and s_email:
            success, err = notification_service.send_absence_email(
                teacher_email, app_password, s_email, s_name, subject_name, today_date, week_number
            )
            if success:
                sent_count += 1
            else:
                fail_count += 1
    
    logger.info(f"E-postalar: Başarılı={sent_count}, Başarısız={fail_count}")
    
    if fail_count > 0:
        messagebox.showwarning("Bildirim Sonucu",
                                f"{sent_count} öğrenciye gönderildi.\n{fail_count} başarısız.")
    else:
        messagebox.showinfo("Başarılı", f"{sent_count} öğrenciye bildirim gönderildi.")


# ==================== GUI View Frame ====================
def open_attendance_window(master=None, teacher_id=1):
    if master:
        app = ctk.CTkToplevel(master)
        app.grab_set()
    else:
        ctk.set_appearance_mode("Dark")
        app = ctk.CTk()
    
    app.geometry("500x500")
    app.title("Günlük Yoklama")
    
    ctk.CTkLabel(app, text="Ders Yoklamasını Başlat",
                 font=("Arial", 22, "bold")).pack(pady=20)
    
    subjects = get_subjects_from_db(teacher_id)
    subject_dropdown = ctk.CTkComboBox(app, values=subjects if subjects else ["No subjects found"], width=350)
    subject_dropdown.pack(pady=5)
    subject_dropdown.set(subjects[0] if subjects else "Ders Seçin")
    
    weeks = [f"{i}. Hafta" for i in range(1, 15)]
    week_dropdown = ctk.CTkComboBox(app, values=weeks, width=350)
    week_dropdown.pack(pady=5)
    week_dropdown.set("1. Hafta")
    
    # === NEW: Camera Selection ===
    cam_options = ["Kamera 0", "Kamera 1", "Kamera 2", "IP/RTSP Kamera"]
    cam_dropdown = ctk.CTkComboBox(app, values=cam_options, width=350)
    cam_dropdown.pack(pady=5)
    cam_dropdown.set("Kamera 0")
    

    
    def on_start():
        cam_sel = cam_dropdown.get()
        if cam_sel == "IP/RTSP Kamera":
            dialog = ctk.CTkInputDialog(text="IP/RTSP Kamera Linkini Girin (Örn: rtsp://... veya http://...):", title="Kamera Linki")
            cam_src = dialog.get_input()
            if not cam_src:
                return # cancelled
        else:
            cam_src = int(cam_sel.split()[-1]) # Extracts 0, 1, or 2
            
        start_attendance_session(subject_dropdown.get(), week_dropdown.get(), teacher_id, cam_src)
        
    ctk.CTkButton(app, text="Kamerayı Başlat",
                  command=on_start,
                  width=350, height=40).pack(pady=20)
    
    if not master:
        app.mainloop()


if __name__ == "__main__":
    open_attendance_window()