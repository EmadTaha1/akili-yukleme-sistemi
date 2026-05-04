import urllib.request
import os

def download_dnn_models():
    """
    Downloads the pre-trained Caffe models for OpenCV DNN face detection.
    """
    model_dir = "dnn_model"
    if not os.path.exists(model_dir):
        os.makedirs(model_dir)

    # URLs for the official OpenCV pre-trained face detection models
    prototxt_url = "https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/face_detector/deploy.prototxt"
    caffemodel_url = "https://raw.githubusercontent.com/opencv/opencv_3rdparty/dnn_samples_face_detector_20170830/res10_300x300_ssd_iter_140000.caffemodel"

    prototxt_path = os.path.join(model_dir, "deploy.prototxt")
    caffemodel_path = os.path.join(model_dir, "res10_300x300_ssd_iter_140000.caffemodel")

    print("[INFO] Downloading deploy.prototxt...")
    urllib.request.urlretrieve(prototxt_url, prototxt_path)

    print("[INFO] Downloading res10_300x300_ssd_iter_140000.caffemodel...")
    urllib.request.urlretrieve(caffemodel_url, caffemodel_path)

    print(f"[SUCCESS] DNN Models downloaded successfully into '{model_dir}' folder.")

if __name__ == "__main__":
    download_dnn_models()