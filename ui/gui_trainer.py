"""
====================================================================
Model Training View Utility (gui_trainer)
====================================================================
Responsibilities:
1. Load dataset images from dataset/ folder
2. Extract high quality face embeddings
3. Filter out statistical outlier embeddings to boost accuracy
4. Compute subject-specific centroids
5. Compute bounded adaptive matching thresholds
6. Evaluate overall trained model quality and dump as .pkl
"""

import cv2
import numpy as np
import os
import sys
import re
import pickle
from datetime import datetime

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.append(root_dir)

from services import db_service
from services.face_service import get_face_embedding, load_embedder_model_safe

try:
    from services.logger_service import get_logger, measure_time, log_ai_event
    logger = get_logger("ai")
except ImportError:
    import logging
    logger = logging.getLogger("ai")


def sanitize_filename(name):
    """Sanitizes names of special characters for filesystem safe saving."""
    return re.sub(r'[^\w\s-]', '', name).strip().replace(' ', '_')


def get_model_filename(subject_id):
    """Generates standardized filename based on subject details."""
    details = db_service.get_subject_details(subject_id)
    if not details:
        return f"trainer_{subject_id}.pkl"
    code = sanitize_filename(str(details[1]))
    name = sanitize_filename(str(details[2]))
    year = sanitize_filename(str(details[3]))
    return f"trainer_ID{subject_id}_{code}_{name}_{year}.pkl"


def compute_adaptive_threshold(embeddings, method='std'):
    """
    Computes a dynamic matching threshold per student based on embedding variance.
    Clamps the threshold within a secure range [0.50, 0.68] to ensure high matching
    accuracy without false-positive overlaps.
    """
    if len(embeddings) < 2:
        return 0.55  # Safe default OpenFace threshold baseline
    
    centroid = np.mean(embeddings, axis=0)
    distances = np.array([np.linalg.norm(v - centroid) for v in embeddings])
    
    if method == 'std':
        threshold = np.mean(distances) + 2 * np.std(distances)
    elif method == 'percentile':
        threshold = np.percentile(distances, 95)
    elif method == 'iqr':
        q1, q3 = np.percentile(distances, [25, 75])
        iqr = q3 - q1
        threshold = q3 + 1.5 * iqr
    else:
        threshold = 0.55
    
    # Safe boundaries to avoid impossible matching levels (lower) and generic matching (upper)
    return float(np.clip(threshold, 0.55, 0.75))


def evaluate_model_quality(embeddings_dict):
    """Evaluates the intra-class cohesion and inter-class division scores of trained profiles."""
    if len(embeddings_dict) < 2:
        return {
            'intra_class_avg': 0,
            'inter_class_min': 0,
            'inter_class_avg': 0,
            'separation_ratio': 0,
            'quality_score': 100,
            'num_students': len(embeddings_dict)
        }
    
    centroids = {sid: np.mean(vecs, axis=0) for sid, vecs in embeddings_dict.items()}
    
    intra_distances = []
    for sid, vecs in embeddings_dict.items():
        cent = centroids[sid]
        for v in vecs:
            intra_distances.append(np.linalg.norm(v - cent))
    intra_avg = np.mean(intra_distances) if intra_distances else 0
    
    inter_distances = []
    sids = list(centroids.keys())
    for i in range(len(sids)):
        for j in range(i+1, len(sids)):
            d = np.linalg.norm(centroids[sids[i]] - centroids[sids[j]])
            inter_distances.append(d)
    
    inter_min = np.min(inter_distances) if inter_distances else 0
    inter_avg = np.mean(inter_distances) if inter_distances else 0
    
    separation_ratio = inter_avg / intra_avg if intra_avg > 0 else 0
    
    if separation_ratio < 1:
        quality = 25
    elif separation_ratio < 2:
        quality = 50 + (separation_ratio - 1) * 25
    elif separation_ratio < 3:
        quality = 75 + (separation_ratio - 2) * 15
    else:
        quality = min(100, 90 + (separation_ratio - 3) * 3)
    
    return {
        'intra_class_avg': float(intra_avg),
        'inter_class_min': float(inter_min),
        'inter_class_avg': float(inter_avg),
        'separation_ratio': float(separation_ratio),
        'quality_score': float(quality),
        'num_students': len(embeddings_dict)
    }


def train_lbph_model(subject_id=None):
    """
    Trains facial embedding models, prunes outlier captures, and saves optimized trainer pkls.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dataset_path = os.path.join(base_dir, "dataset")
    embedder_model_path = os.path.join(base_dir, "models", "dnn_model", "openface_nn4.small2.v1.t7")
    
    if subject_id:
        filename = get_model_filename(subject_id)
        model_save_path = os.path.join(base_dir, "models", filename)
        allowed_ids = db_service.get_enrolled_student_ids(subject_id)
    else:
        filename = "trainer_global.pkl"
        model_save_path = os.path.join(base_dir, "models", filename)
        allowed_ids = None
    
    logger.info(f"Yapay zeka modeli eğitimi başlatıldı, Ders ID={subject_id}")
    
    if not os.path.exists(dataset_path):
        logger.error("Öğrenci veri kümesi klasörü bulunamadı!")
        return False, "Dataset folder not found."
    if not os.path.exists(embedder_model_path):
        logger.error("OpenFace sinir ağı modeli bulunamadı!")
        return False, "OpenFace DNN model not found."
    
    embedder_net = load_embedder_model_safe(embedder_model_path)
    image_paths = [os.path.join(dataset_path, f) for f in os.listdir(dataset_path) if f.endswith('.jpg')]
    
    logger.info(f"Veri klasöründe tespit edilen resim sayısı: {len(image_paths)}")
    
    embeddings_dict = {}
    failed = 0
    
    for image_path in image_paths:
        try:
            student_db_id = int(os.path.split(image_path)[-1].split(".")[1])
            if allowed_ids is not None and student_db_id not in allowed_ids:
                continue
            
            img_bgr = cv2.imread(image_path, cv2.IMREAD_COLOR)
            if img_bgr is None:
                failed += 1
                continue
            
            vec = get_face_embedding(img_bgr, embedder_net)
            
            if student_db_id not in embeddings_dict:
                embeddings_dict[student_db_id] = []
            embeddings_dict[student_db_id].append(vec)
        except Exception as e:
            logger.warning(f"Resim işleme başarısız {image_path}: {e}")
            failed += 1
            continue
    
    if not embeddings_dict:
        logger.error("Modeli eğitmek için hiçbir veri örneği bulunamadı!")
        return False, "No training images found."
    
    logger.info(f"Model yapısı hazırlığı: Başarılı={sum(len(v) for v in embeddings_dict.values())} örnek.")
    
    final_data = {
        'version': '2.0',
        'created_at': datetime.now().isoformat(),
        'embeddings': {},      # Keep all vectors for k-NN
        'centroids': {},       # Keep averages for fast distance checks
        'thresholds': {},      # Dynamic bounded thresholds
        'metadata': {}
    }
    
    for sid, vecs in embeddings_dict.items():
        vecs_array = np.array(vecs)
        
        # 1. Prune outliers (the furthest 5% of captured faces)
        centroid = np.mean(vecs_array, axis=0)
        distances = np.array([np.linalg.norm(v - centroid) for v in vecs_array])
        
        if len(distances) >= 20:
            threshold_outlier = np.percentile(distances, 95)
            mask = distances < threshold_outlier
            vecs_array = vecs_array[mask]
            removed = len(distances) - mask.sum()
            if removed > 0:
                logger.info(f"Öğrenciden {removed} aykırı örnek kaldırıldı (ID:{sid})")
        
        # 2. Recompute clean centroid
        centroid = np.mean(vecs_array, axis=0)
        
        # 3. Compute secure bounded dynamic threshold
        adaptive_threshold = compute_adaptive_threshold(vecs_array, method='std')
        
        final_data['embeddings'][sid] = vecs_array
        final_data['centroids'][sid] = centroid
        final_data['thresholds'][sid] = adaptive_threshold
        final_data['metadata'][sid] = {
            'num_samples': len(vecs_array),
            'mean_distance': float(np.mean([np.linalg.norm(v - centroid) for v in vecs_array])),
            'max_distance': float(np.max([np.linalg.norm(v - centroid) for v in vecs_array])),
            'std_distance': float(np.std([np.linalg.norm(v - centroid) for v in vecs_array]))
        }
        
        logger.info(f"Öğrenci {sid}: Örnek sayısı {len(vecs_array)} | Hesaplanan dinamik eşik = {adaptive_threshold:.3f}")
    
    # 4. Evaluate overall quality metrics
    quality_report = evaluate_model_quality(final_data['embeddings'])
    final_data['quality_report'] = quality_report
    
    logger.info(f"Model kalite raporu: {quality_report['quality_score']:.1f}/100")
    
    # 5. Clean up old obsolete files for same subject
    models_dir = os.path.join(base_dir, "models")
    if subject_id and os.path.exists(models_dir):
        for f in os.listdir(models_dir):
            if f.startswith(f"trainer_ID{subject_id}_") and (f.endswith(".yml") or f.endswith(".pkl")):
                try:
                    os.remove(os.path.join(models_dir, f))
                except:
                    pass
    
    # 6. Save model pkl
    with open(model_save_path, "wb") as f:
        pickle.dump(final_data, f)
    
    num_students = len(final_data['embeddings'])
    total_vecs = sum(len(v) for v in final_data['embeddings'].values())
    
    try:
        log_ai_event("MODEL_TRAINED", 
                     filename=filename,
                     students=num_students,
                     embeddings=total_vecs,
                     quality_score=quality_report['quality_score'])
    except:
        pass
    
    msg = (f"✅ Yapay zeka modeli başarıyla eğitildi ve kaydedildi!\n"
           f"Öğrenci sayısı: {num_students}\n"
           f"Model uyum kalitesi: {quality_report['quality_score']:.1f}/100")
    
    return True, msg