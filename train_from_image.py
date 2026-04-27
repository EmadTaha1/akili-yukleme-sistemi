import cv2
import numpy as np
import os

# 1. إعداد المصنفات والنموذج الحالي
faceCascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
recognizer = cv2.face.LBPHFaceRecognizer_create()

# قراءة نموذج التدريب الحالي (مهم جداً!)
if os.path.exists('trainer.yml'):
    recognizer.read('trainer.yml')
    print("[INFO] Mevcut model yüklendi. Güncellenecek...")
else:
    print("[ERROR] 'trainer.yml' bulunamadı! Önce ana modeli eğitmelisiniz.")
    exit()

image_path = r"C:\Users\qwedc\OneDrive\Desktop\bitirme proje\new_faces\Mutaseim\mutaseim.jpg" 
new_user_name = "mutaseim" # هنا نضع اسم الأستاذة
new_user_id = 8 # هنا نضع الرقم 9، لأن قائمتك السابقة تنتهي عند 8


# 3. قراءة الصورة واكتشاف الوجه
if not os.path.exists(image_path):
    print(f"[ERROR] Fotoğraf bulunamadı: {image_path}")
    exit()

img = cv2.imread(image_path)
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
faces = faceCascade.detectMultiScale(gray, 1.2, 5)

# 4. إذا تم اكتشاف وجه واحد دقيق
if len(faces) == 1:
    x, y, w, h = faces[0]
    roi_gray = gray[y:y+h, x:x+w]
    
    # تحضير البيانات للشكل الذي يفهمه recognizer
    faces_data = [roi_gray]
    ids_data = np.array([new_user_id])
    
    # 5. التحديث السحري (Update بدلاً من Train)
    recognizer.update(faces_data, ids_data)
    
    # حفظ النموذج المحدث
    recognizer.write('trainer.yml')
    print(f"[SUCCESS] {new_user_name} (ID: {new_user_id}) modele eklendi ve trainer.yml güncellendi!")
    print(f"[INFO] Artık ana sistemi çalıştırıp test edebilirsiniz.")

else:
    print(f"[ERROR] Fotoğrafta net bir yüz bulunamadı veya birden fazla yüz var (Yüz sayısı: {len(faces)}).")