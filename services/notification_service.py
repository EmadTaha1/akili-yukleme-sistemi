import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_absence_email(teacher_email, teacher_app_password, student_email, student_name, subject_name, date, week_number):
    """
    Sends an absence notification email to a student.
    Returns (success_boolean, error_message).
    """
    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = teacher_email
        msg['To'] = student_email
        msg['Subject'] = f"Yoklama Bildirimi: {subject_name} ({date})"
        
        text = f"""Merhaba {student_name},\n\n{date} tarihinde ({week_number}. Hafta) işlenen {subject_name} dersinde 'Yok' yazıldınız.\nLütfen durumunuzu kontrol edin veya bir hata olduğunu düşünüyorsanız öğretmeninizle iletişime geçin.\n\nİyi çalışmalar,\nAkıllı Yoklama Sistemi"""
        
        html = f"""
        <html>
          <body style="font-family: Arial, sans-serif; background-color: #f4f4f9; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 8px rgba(0,0,0,0.1);">
              <div style="background-color: #b82121; color: #ffffff; padding: 20px; text-align: center;">
                <h2 style="margin: 0; font-size: 24px;">Yoklama Bildirimi</h2>
              </div>
              <div style="padding: 30px;">
                <p style="font-size: 16px; color: #333;">Merhaba <strong>{student_name}</strong>,</p>
                <p style="font-size: 16px; color: #555; line-height: 1.6;">
                  Aşağıda detayları verilen derse <strong style="color: #b82121;">katılmadığınız (Yok)</strong> tespit edilmiştir:
                </p>
                <div style="background-color: #f9f9f9; border-left: 4px solid #b82121; padding: 15px; margin: 20px 0;">
                  <p style="margin: 5px 0;"><strong>Ders:</strong> {subject_name}</p>
                  <p style="margin: 5px 0;"><strong>Tarih:</strong> {date}</p>
                  <p style="margin: 5px 0;"><strong>Hafta:</strong> {week_number}. Hafta</p>
                </div>
                <p style="font-size: 14px; color: #777; line-height: 1.5;">
                  Lütfen devamsızlık durumunuzu kontrol ediniz. Eğer bu bildirimde bir hata olduğunu düşünüyorsanız, en kısa sürede ders öğretmeninizle iletişime geçiniz.
                </p>
                <br>
                <p style="font-size: 14px; color: #333;">İyi çalışmalar,<br><strong>Akıllı Yoklama Sistemi</strong></p>
              </div>
            </div>
          </body>
        </html>
        """
        
        msg.attach(MIMEText(text, 'plain', 'utf-8'))
        msg.attach(MIMEText(html, 'html', 'utf-8'))
        
        # Connect to Gmail SMTP server
        server = None
        try:
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(teacher_email, teacher_app_password)
            server.send_message(msg)
            return True, ""
        finally:
            if server:
                server.quit()
    except Exception as e:
        return False, str(e)
