# OrthoGuide AI - Backend (Flask Service)

The OrthoGuide Backend is the central API layer that manages clinical data, patient monitoring schedules, and AI-driven interactions. It uses a robust micro-service architecture to handle complex orthodontic workflows.

---

## 🚀 Key Features
- **OTP Verification:** Secure verification logic for password resets and signup verification.
- **AI Chatbot Engine:** Integrates with local Ollama instances and falls back to a custom FAQ engine.
- **Task Automation:** 
  - `send_daily_reminders`: Automatically notifies patients about tray shifts and oral hygiene.
  - `cleanup_expired_otps`: Keeps the database secure by purging old verification codes.
- **Comprehensive API:** 2000+ lines of Python logic covering Patients, Clinicians, Appointments, and Incident Reporting.

---

## 🛠 Tech Stack
- **Framework:** Flask 3.x
- **ORM:** Flask-SQLAlchemy (MySQL)
- **Hashing:** Flask-Bcrypt
- **Cross-Origin:** Flask-CORS
- **Scheduling:** APScheduler
- **Server:** Gunicorn (Recommended for Production)

---

## 📦 Installation & Setup

1. **Environment Setup:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

2. **Dependency Installation:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Database Configuration:**
   - Update `config.py` with your MySQL credentials:
     ```python
     SQLALCHEMY_DATABASE_URI = "mysql+pymysql://user:pass@localhost/orthoguide"
     ```

4. **SMTP Configuration (Emails):**
   - Open `app.py` and search for `send_email_otp`.
   - Update the `sender_email` and `app_password` with your verified Google App Password.

5. **Run Server:**
   ```bash
   python app.py
   ```

---

## 📊 Database Schema
The backend manages the following primary models:
- `Admin`: System-level administrative access.
- `Clinician`: Professional users managing multiple patients and schedules.
- `Patient`: Core user model tracking compliance, tray progression, and history.
- `Appointment`: Clinical scheduling and session tracking.
- `ChatMessage`: Persistent history for AI diagnostic conversations.
- `PatientNotifications`: Log of automated and manual alerts.

---

## 🛠 API Endpoints (Highlights)
- `POST /login`: Primary authentication for all roles.
- `POST /send_otp`: Triggers professional HTML email verification.
- `POST /patient/report_issue`: Allows patients to send photos/descriptions of appliance issues.
- `GET /clinician/dashboard/<id>`: Fetches aggregate data for clinical oversight.

---

**OrthoGuide Backend** - *The Intelligent Heart of Orthodontic Practice.*
