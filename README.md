# 👤 AI-Based Smart Face Attendance System

An advanced, premium-tier **AI-Based Smart Face Attendance & Multi-Factor Authentication (MFA)** application built using Python, Flask, DeepFace, SQLite, and Chart.js. This system replaces traditional attendance systems with biometric facial recognition, liveness/anti-spoofing verification, emotion tracking, automatic notifications, and an integrated AI chatbot companion.

---

## 🌟 Key Features

### 💻 Dashboards & Administration
* **Admin Control Center**:
  * Real-time metrics overview (Punctuality rate, present/absent ratios, and predictive analytics).
  * Interactive **All Employees** list with search and detailed inspector modals.
  * **Editable Employee Profiles**: Modify full name, username, email, department, mobile, and custom profile pictures dynamically.
  * **Detailed Attendance Report Finder**: Check historical stats for any specific date with smart alerts for **Sunday Holidays** and **Not Registered** statuses (for dates before an employee joined).
  * Outbound Email log verification interface.
* **Employee Workspace**:
  * Personalized profile details displaying biometric avatars side-by-side.
  * Easy-to-use self-attendance marker (Clock In, Break Out, Break In, Clock Out) utilizing live camera feed.
  * Weekly attendance progress tracking line charts and monthly summaries.
  * Private history date viewer and interactive AI chatbot.

### 🤖 AI-Biometrics & Analytics
* **Biometric Face Verification**: Uses standard `VGG-Face` deep learning models for high-accuracy match checks against registered records.
* **Anti-Spoofing Protection**: Built-in 2D liveness classification check to prevent attendance logging attempts using printed photographs or digital screens.
* **Emotion Tracking**: Identifies current mood (Happy, Sad, Angry, Neutral, etc.) during attendance scanning and displays emotion frequencies via doughnut charts.
* **TrackHub AI Assistant**: An embedded chatbot companion integrated into both dashboards to answer context-aware natural language queries about attendance history, policies, or daily aggregates.

### 🔒 Security & Password Recovery
* **Dual-Path Password Reset System**:
  * **Employees**: Quick recovery via automatic secure email links.
  * **Administrators**: Role-based MFA question, unique PIN validation, and fallback emergency Master Recovery Keys.

---

## 🛠️ Technology Stack

* **Backend**: Python 3.x, Flask, SQLAlchemy (SQLite database)
* **Frontend**: HTML5, Vanilla CSS3 (Custom Glassmorphism layout), Vanilla JavaScript
* **AI & Computer Vision**: OpenCV (`cv2`), DeepFace (`VGG-Face`, `Emotion`), Face Recognition
* **Charts & Analytics**: Chart.js
* **Mailing**: Flask-Mail

---

## 📁 Repository Structure

```
AI-MFA-System/
│
├── instance/                  # SQLite active database
├── face_encodings/            # Saved biometric facial signature files (.npy)
├── uploads/                   # Securely stored employee profile and face photographs
│
├── templates/                 # Jinja2 HTML Views
│   ├── base.html              # Central layout & global footer
│   ├── home.html              # Main welcome / portal directory
│   ├── login.html             # Multi-role authentication entrypoint
│   ├── register_employee.html # Employee onboarding form with facial enrollment
│   ├── admin_dashboard.html   # Main control page for administrators
│   └── employee_dashboard.html# Main workspace page for employees
│
├── static/
│   ├── css/style.css          # Core custom styles (Dark Theme/Glassmorphic accents)
│   └── js/
│       ├── admin_dashboard.js # Admin interactive widgets and AJAX forms
│       ├── employee_dashboard.js # Employee camera hooks & charts
│       ├── home.js            # General homepage animations
│       └── register_employee.js # Biometric registration frame
│
├── app.py                     # Main application entry point & DeepFace caching
├── routes.py                  # Core backend endpoints, APIs, and route structures
├── models.py                  # SQLAlchemy Database schema definitions
├── config.py                  # Environment config parser
├── email_service.py           # Email dispatch helper functions
├── analytics.py               # AI TrackHub chatbot logic & predictive pipelines
├── emotion_detection.py       # DeepFace emotion recognition framework
├── spoof_detection.py         # Anti-spoofing/Liveness assessment module
├── face_recognition_module.py # Face extraction & similarity matching
├── requirements.txt           # Python packages listing
└── .env                       # App secrets & SMTP configuration
```

---

## ⚙️ Installation & Seeding

### 1. Prerequisite Packages
Make sure you have CMake and C++ Build Tools installed on your OS for `face_recognition` compilation, then clone the repository:
```bash
pip install -r requirements.txt
```

### 2. Configure Environment `.env`
Create a `.env` file in the root directory and specify your SMTP server, database settings, and Flask keys:
```env
FLASK_APP=app.py
FLASK_ENV=development
SECRET_KEY=your_flask_secret_key_here

# Flask-Mail SMTP Settings
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
```

### 3. Initialize & Seed Database
Initialize database tables, establish relations, and seed the default administrator credentials along with recovery PINs:
```bash
python init_db.py
```
* Default Admin Username: `admin`
* Default Admin Password: `Admin@123`
* Admin Screte PIN: `ADMIN-MFA-RECOVERY-KEY-2026`

---

## 🚀 Running the System

Start the Flask server locally:
```bash
python app.py
```
The server will automatically cash VGG-Face and Emotion recognition models and run on:
👉 **[http://localhost:5000](http://localhost:5000)**

---

## 📜 License
This application is distributed under the terms of the **MIT License**.

© 2026 AI-Based Smart Face Attendance System. All rights reserved.
