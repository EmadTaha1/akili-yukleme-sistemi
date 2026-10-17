# 🎓 Akıllı Yükleme Sistemi — Smart Attendance System

A desktop application with a companion mobile app for automated student attendance tracking using **facial recognition**, built as a university graduation project.

---

## 🧠 How It Works

```
[Desktop App]  →  Camera + Face Recognition (95% accuracy)
      ↓
[Flask API]    →  REST endpoints over local WiFi
      ↓
[Mobile App]   →  Teacher monitors sessions & views reports
```

The **desktop app** handles all AI processing (camera, face recognition, model training).  
The **mobile app** allows teachers to monitor attendance sessions and view reports from their phone.

---

## ✨ Features

### Desktop App
- 🔐 Teacher login & registration with password recovery
- 📸 Student enrollment via webcam (face capture)
- 🤖 Real-time facial recognition attendance (OpenCV + DNN)
- 📚 Subject & student management (manual + Excel upload)
- 📊 Attendance reports with PDF export
- 📧 Email notifications for absent students
- 🔒 Automatic backup system

### Mobile App (Flutter)
- 📱 Teacher login synced with desktop account
- 📋 View assigned subjects and enrolled students
- ✅ Monitor live attendance sessions in real-time
- 📈 Attendance reports and statistics

---

## 🛠️ Tech Stack

| Component | Technology |
|---|---|
| Desktop UI | Python + Tkinter |
| Face Recognition | OpenCV + DNN (OpenFace) |
| Database | SQLite |
| API Server | Flask + Flask-CORS |
| Mobile App | Flutter (Dart) |

---

## 🚀 Getting Started

### Prerequisites
- Python 3.9+
- Webcam
- (For mobile) Flutter SDK

### Installation

```bash
# Clone the repository
git clone https://github.com/EmadTaha1/akili-yukleme-sistemi.git
cd akili-yukleme-sistemi

# Install Python dependencies
pip install -r requirements.txt

# Run the desktop application
python main.py
```

### Running the API Server (for mobile app)
```bash
python api_server.py
```

---

## 📁 Project Structure

```
├── main.py                  # App entry point
├── api_server.py            # Flask REST API for mobile app
├── services/
│   ├── auth_service.py      # Teacher authentication
│   ├── face_service.py      # Face recognition engine
│   ├── db_service.py        # Database operations
│   ├── model_trainer.py     # Face model training
│   ├── notification_service.py  # Email notifications
│   ├── backup_service.py    # Auto database backup
│   ├── stats_service.py     # Attendance statistics
│   └── logger_service.py    # System logging
├── ui/
│   ├── main_dashboard.py    # Main dashboard
│   ├── gui_login.py         # Login screen
│   ├── gui_attendance_session.py  # Live attendance
│   ├── gui_student_enrollment.py  # Student enrollment
│   ├── gui_subject_setup.py # Subject management
│   ├── gui_reports.py       # Reports viewer
│   └── gui_trainer.py       # Model training UI
├── database/
│   └── database_setup.py    # DB schema & initialization
├── models/                  # Trained face recognition models
├── mobile_app/              # Flutter mobile application
└── requirements.txt
```

---

## 📱 Mobile App Setup

See [mobile_app/README.md](mobile_app/README.md) for Flutter setup instructions.

---

## 👨‍💻 Author

**Emad Taha** — Graduation Project 2026
