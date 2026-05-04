import cv2
import os
import shutil
import numpy as np

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
                    cv2.rectangle(img, (startX, startY), (endX, endY), (255, 0, 0), 2)
                    count += 1
                    cv2.imwrite(os.path.join(dataset_dir, f"User.{uni_id}.{count}.jpg"), gray_face)
                    if count >= 100: break
            cv2.imshow('Face Capture', img)
            if cv2.waitKey(10) & 0xFF == 27 or count >= 100: break
    finally:
        cam.release()
        cv2.destroyAllWindows()
    return count >= 100
