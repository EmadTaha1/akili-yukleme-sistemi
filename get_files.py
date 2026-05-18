import cv2
import shutil
import os

# Define required paths
xml_files = [
    "haarcascade_frontalface_default.xml",
    "haarcascade_smile.xml",
    "haarcascade_eye.xml"
]

# Get OpenCV library path on your device
cv2_path = os.path.dirname(cv2.__file__)
cascade_path = os.path.join(cv2_path, 'data')

# Copy files to the main project directory
for file in xml_files:
    src = os.path.join(cascade_path, file)
    if os.path.exists(src):
        shutil.copy(src, ".")
        print(f"Done: {file} copied!")
    else:
        print(f"Error: {file} not found in OpenCV path.")