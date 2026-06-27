# AI-Based Smart Face Attendance & Multi-Factor Authentication System

This is a Flask-based attendance system using facial recognition, geofencing, emotion tracking, and liveness detection.

##  Core System Logic

### 1. Geofenced Boundaries
The system validates employee location when marking attendance using the Haversine formula to compute distance.
* **Designated Office Coordinates**: Latitude `19.98381430077873`, Longitude `73.75877028302833`.
* **Allowed Distance Limit**: Maximum 500 meters. Attendance is blocked if the distance exceeds this limit.

### 2. Time-Based Action Status Brackets
Every attendance event is classified into specific statuses based on arrival and departure times:
* **Mark In**:
  * Before 09:00 AM: `Early Entry`
  * 09:00 AM – 09:15 AM: `on time entry`
  * After 09:15 AM: `Late Entry` 
* **Break Out**:
  * Before 12:00 PM: `Early Break`
  * 12:00 PM – 12:15 PM: `On time Break`
  * After 12:15 PM: `Late Break`
* **Break In**:
  * Break duration > 1.0 hr: `Long Break`
  * Before 01:00 PM (and <= 1hr): `early Break return`
  * 01:00 PM – 01:15 PM: `On time Break retuen`
  * After 01:15 PM: `late Break return`
* **Mark Out**:
  * Before 06:00 PM: `Early Departure`
  * 06:00 PM – 06:15 PM: `on time Departure`
  * After 06:15 PM: `Late Departure`

### 3. Net Hours & Overtime Rules
* **Working Hours**: Calculated as Total Duration (Mark In to Mark Out) minus Actual Break Duration (Break Out to Break In).
* **Weekday Schedule (Monday – Saturday)**:
  * **Full Day**: Net hours $\ge$ 8.0 hours.
  * **Half Day**: Net hours $\ge$ 4.0 hours and $<$ 8.0 hours.
  * **Short Day**: Net hours $<$ 4.0 hours.
* **Sunday Schedule**:
  * All hours worked on Sunday are logged entirely as **Overtime hours** (working hours remain `0.0`).

### 4. Background Auto-Finalization Flow
When the Admin Dashboard loads, incomplete sessions are finalized:
* **Mark In only (No Break Out/In, No Mark Out)**: Status becomes `incomplete_session`, `admin_approval` with `pending` status.
* **Mark In + Break Out only**: Status becomes `incomplete_session`. Approved as `full_day` if hours $\ge$ 8.0, `half_day` if $\ge$ 4.0, else `pending` admin approval.
* **Mark In + Break Out + Break In (No Mark Out)**: Status becomes `incomplete_session`, `pending` admin approval.

### 5. Biometrics & Spoof Detection
* **Facial Matching**: Uses `face_recognition` (dlib) with a match distance tolerance of `0.45`.
* **Liveness Assessment**: 
  * DeepFace Quality Check
  * Sharpness Variance (Laplacian filters)
  * Light Reflective Glare (HSV channel standard deviation)
  * OpenCV Blink Cascade
* **Emotion Tracking**: Evaluates mood during each check-in/out event via DeepFace, recording it in the database.

### 6. Dashboards Overview

**Admin Dashboard:**
* **Real-time Statistics:** Calculates and displays today's present/absent counts, overall punctuality trends, and aggregate emotion metrics categorized by department.
* **Employee Management:** Interface to register employees (capturing initial biometric face templates and profile images), update user details, or delete accounts.
* **Pending Approvals Queue:** Allows administrators to manually override incomplete sessions triggered by missing check-outs, assigning `full_day`, `half_day`, or `absent`.
* **Attendance Reports:** Lookup tool to fetch historic attendance records and view individual employee performance over time.

**Employee Dashboard:**
* **Biometric Attendance Terminal:** Live camera interface connecting to the `/api/mark_attendance` endpoint, handling spoof detection and geofencing checks before committing timestamps.
* **Personal Analytics:** Tracks historical Full, Half, and Short day counts, overtime hours, and a 7-day personal emotion trend summary.
* **Email Verification Logs:** Queries the internal `email_report` SQL View to show a timeline of dispatched attendance alerts to the user's registered email.

### 7. TrackHub AI Chatbot & Predictive Analytics
* **TrackHub**: Embedded dashboard chatbot for querying attendance history, working hours, and analytics (handled by `analytics.py`).
* **Predictive Absences**: Random Forest logic (in `analytics.py`) flags employees at high risk of absenteeism over the next 7 days based on recent data.

### 8. MFA Recovery
Administrators use MFA recovery via Security Questions, PINs, or a Master Recovery Key (`ADMIN-MFA-RECOVERY-KEY-2026`). Employees use email verification links.

##  Setup & Run
1. Install dependencies: `pip install -r requirements.txt`
2. Create `.env` file with `SECRET_KEY`, `MAIL_SERVER`, `MAIL_USERNAME`, `MAIL_PASSWORD`, etc.
3. Initialize the database: `python init_db.py` (Default Admin: `admin` / `admin123`)
4. Start application: `python app.py` (Runs on `http://localhost:5000`)
