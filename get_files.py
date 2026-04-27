import cv2
import shutil
import os

# تحديد المسارات المطلوبة
xml_files = [
    "haarcascade_frontalface_default.xml",
    "haarcascade_smile.xml",
    "haarcascade_eye.xml"
]

# الحصول على مسار المكتبة في جهازك
cv2_path = os.path.dirname(cv2.__file__)
cascade_path = os.path.join(cv2_path, 'data')

# نسخ الملفات لمجلد المشروع الرئيسي
for file in xml_files:
    src = os.path.join(cascade_path, file)
    if os.path.exists(src):
        shutil.copy(src, ".")
        print(f"Done: {file} copied!")
    else:
        print(f"Error: {file} not found in OpenCV path.")