from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from config import Config
from datetime import datetime, timedelta
import random
import string
import os
from apscheduler.schedulers.background import BackgroundScheduler
from pytz import timezone
from sqlalchemy import Enum
from enum import Enum as PyEnum
import json
from difflib import get_close_matches
from chatbot.ai_engine import ask_ai

PATIENT_STAGES = [
    "Pre-treatment",
    "Bonding / First Trays",
    "Alignment Phase",
    "Bite Correction",
    "Finishing and Detailing",
    "Debonding and Retention"
]

class NotificationType(PyEnum):
    ORAL_HYGIENE = "oral_hygiene"
    APPLIANCE_CARE = "appliance_care"
    APPOINTMENT = "appointment"
    REPORT_ISSUE = "report_issue"

class ClinicianLabel(PyEnum):
    ATTENTION = "attention"
    CRITICAL = "critical"

app = Flask(__name__)
app.config.from_object(Config)

# ---------------------------
# LOAD FAQ JSON
# ---------------------------
faq_file = os.path.join("chatbot", "orthodontic_faqs.json")
try:
    with open(faq_file, "r", encoding="utf-8") as f:
        FAQS = json.load(f)
except Exception as e:
    print(f"Error loading {faq_file}: {e}")
    FAQS = []
    
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
CORS(app)

# ---------------------------
# DATABASE MODELS
# ---------------------------

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.String(50), unique=True)
    name = db.Column(db.String(100))
    password = db.Column(db.String(255))
    email = db.Column(db.String(100))
    phone_number = db.Column(db.String(15))


class Clinician(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    clinician_id = db.Column(db.String(50), unique=True)
    name = db.Column(db.String(100))
    role = db.Column(db.String(50))
    phone_number = db.Column(db.String(15))
    email = db.Column(db.String(100))
    password = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)


class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.String(50), unique=True)
    name = db.Column(db.String(100))
    phone_number = db.Column(db.String(15))
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(255))
    status = db.Column(db.String(50), default="on track")
    treatment_stage = db.Column(db.String(100), default="Pre-treatment")
    created_by_clinician = db.Column(db.String(50))
    is_active = db.Column(db.Boolean, default=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PatientConsent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.String(50))
    consent_given = db.Column(db.Boolean, default=False)
    consent_date = db.Column(db.DateTime, default=datetime.utcnow)


class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.String(50))
    clinician_id = db.Column(db.String(50))
    appointment_date = db.Column(db.Date)
    appointment_time = db.Column(db.String(50))
    appointment_type = db.Column(db.String(50))
    notes = db.Column(db.Text)
    status = db.Column(db.String(50), default="scheduled")


class TreatmentHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.String(50))
    stage = db.Column(db.String(100))
    status = db.Column(db.String(50))
    updated_by = db.Column(db.String(50))
    notes = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)


class PasswordResetOTP(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100))
    otp = db.Column(db.String(6))
    expires_at = db.Column(db.DateTime)
    verified = db.Column(db.Boolean, default=False)

class PatientNotifications(db.Model):
    __tablename__ = "patient_notifications"

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.String(50), nullable=False)
    type = db.Column(
        Enum(NotificationType, name="notification_type_enum"),
        nullable=False
    )
    message = db.Column(db.Text, nullable=False)
    related_appointment_id = db.Column(db.Integer, nullable=True)
    report_severity = db.Column(db.Integer, nullable=True)
    clinician_label = db.Column(
    Enum(ClinicianLabel, name="clinician_label_enum"),
    nullable=True
)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp())

class PatientNotificationSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.String(50), nullable=False, unique=True)
    oral_hygiene = db.Column(db.Boolean, default=True)
    appliance_care = db.Column(db.Boolean, default=True)
    appointment = db.Column(db.Boolean, default=True)

with app.app_context():
    db.create_all()

# ---------------------------
# DAILY REMINDER FUNCTION
# ---------------------------

def send_daily_reminders():
    with app.app_context():
        patients = Patient.query.filter_by(is_active=True).all()

        for patient in patients:
            settings = PatientNotificationSettings.query.filter_by(patient_id=patient.patient_id).first()

            if not settings:
                # If no settings exist, assume all ON
                settings = PatientNotificationSettings(patient_id=patient.patient_id)
                db.session.add(settings)

            # Oral hygiene
            if settings.oral_hygiene:
                notif = PatientNotifications(
                    patient_id=patient.patient_id,
                    type=NotificationType.ORAL_HYGIENE,
                    message="Time to maintain your daily oral care!"
                )
                db.session.add(notif)

            # Appliance care
            if settings.appliance_care:
                notif = PatientNotifications(
                    patient_id=patient.patient_id,
                    type=NotificationType.APPLIANCE_CARE,
                    message="Check your appliance for any issues and clean it properly!"
                )
                db.session.add(notif)

            # Appointment reminders
            if settings.appointment:
                next_app = get_next_appointment(patient.patient_id)
                if next_app:
                    notif = PatientNotifications(
                        patient_id=patient.patient_id,
                        type=NotificationType.APPOINTMENT,
                        message=f"Upcoming appointment on {next_app['date']} at {next_app['time']}"
                    )
                    db.session.add(notif)

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Error committing notifications: {e}")

    print("Daily reminders sent!")
# ---------------------------
# HOME
# ---------------------------

@app.route("/")
def home():
    return {"message": "OrthoGuide Backend Running"}

# ---------------------------
# HELPER FUNCTION
# ---------------------------

def get_next_appointment(patient_id):

    today = datetime.utcnow().date()

    appointment = Appointment.query.filter(
        Appointment.patient_id == patient_id,
        Appointment.appointment_date >= today
    ).order_by(Appointment.appointment_date.asc()).first()

    if appointment:

        time = appointment.appointment_time if appointment.appointment_time else "NA"

        return {
            "date": str(appointment.appointment_date),
            "time": time,
            "type": appointment.appointment_type
        }

    return None

# ---------------------------
# CHATBOT HELPER
# ---------------------------

def find_faq_answer(user_message, limit=1):
    """
    Find the closest matching FAQ based on keywords or question similarity.
    Returns the answer if found, else a default reply.
    """
    if not FAQS:
        return "Sorry, I don't have FAQs right now."

    # Normalize message
    msg = user_message.lower()

    # First try keyword matching
    keyword_matches = []
    for faq in FAQS:
        if any(kw.lower() in msg for kw in faq.get("keywords", [])):
            keyword_matches.append(faq)

    if keyword_matches:
        return keyword_matches[0]["answer"]

    # Fallback: match question text similarity
    questions = [faq["question"] for faq in FAQS]
    matches = get_close_matches(user_message, questions, n=limit, cutoff=0.6)

    if matches:
        for faq in FAQS:
            if faq["question"] == matches[0]:
                return faq["answer"]

    # Default reply
    return "Sorry, I could not find an answer. Please contact your clinician."
# ---------------------------
# LOGIN
# ---------------------------

@app.route("/login", methods=["POST"])
def login():

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request"}), 400

    user_id = data.get("user_id")
    password = data.get("password")

    admin = Admin.query.filter_by(admin_id=user_id).first()
    if admin and bcrypt.check_password_hash(admin.password, password):
        return jsonify({
            "role": "admin",
            "user_id": admin.admin_id,
            "name": admin.name
        })

    clinician = Clinician.query.filter_by(clinician_id=user_id).first()
    if clinician and bcrypt.check_password_hash(clinician.password, password):

        if not clinician.is_active:
            return jsonify({"error": "Clinician inactive"}), 403

        return jsonify({
            "role": "clinician",
            "user_id": clinician.clinician_id,
            "name": clinician.name
        })

    patient = Patient.query.filter_by(patient_id=user_id).first()

    if patient and bcrypt.check_password_hash(patient.password, password):

        if not patient.is_active:
            return jsonify({"error": "Patient inactive"}), 403

        consent = PatientConsent.query.filter_by(patient_id=patient.patient_id).first()

        return jsonify({
            "role": "patient",
            "user_id": patient.patient_id,
            "name": patient.name,
            "consent_given": consent.consent_given if consent else False
        })

    return jsonify({"error": "Invalid credentials"}), 401


# ---------------------------
# PATIENT LOGIN
# ---------------------------

@app.route("/patient/login", methods=["POST"])
def patient_login():

    data = request.get_json()

    patient = Patient.query.filter_by(patient_id=data.get("patient_id")).first()

    if not patient:
        return jsonify({"error": "Patient not found"}), 404

    if not bcrypt.check_password_hash(patient.password, data.get("password")):
        return jsonify({"error": "Incorrect password"}), 401

    if not patient.is_active:
        return jsonify({"error": "Patient account inactive"}), 403

    consent = PatientConsent.query.filter_by(patient_id=patient.patient_id).first()

    return jsonify({
        "role": "patient",
        "patient_id": patient.patient_id,
        "name": patient.name,
        "status": patient.status,
        "treatment_stage": patient.treatment_stage,
        "consent_given": consent.consent_given if consent else False
    })


# ---------------------------
# SAVE CONSENT
# ---------------------------

@app.route("/patient/consent", methods=["POST"])
def patient_consent():
    data = request.get_json()
    patient_id = data.get("patient_id")

    existing = PatientConsent.query.filter_by(patient_id=patient_id).first()
    if existing:
        return jsonify({"message": "Consent already recorded"})

    consent = PatientConsent(
        patient_id=patient_id,
        consent_given=True
    )

    db.session.add(consent)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()  # undo the failed DB operation
        print(f"Error saving consent for patient {patient_id}: {e}")
        return jsonify({"error": "Failed to save consent"}), 500

    return jsonify({"message": "Consent saved successfully"})


# ---------------------------
# CHANGE PASSWORD
# ---------------------------

@app.route("/patient/change_password", methods=["POST"])
def patient_change_password():

    data = request.get_json()
    patient_id = data.get("patient_id")
    patient = Patient.query.filter_by(patient_id=patient_id).first()

    if not patient:
        return jsonify({"error": "Patient not found"}), 404

    if not bcrypt.check_password_hash(patient.password, data.get("old_password")):
        return jsonify({"error": "Old password incorrect"}), 401

    if data.get("new_password") != data.get("confirm_password"):
        return jsonify({"error": "Passwords do not match"}), 400

    patient.password = bcrypt.generate_password_hash(
        data.get("new_password")
    ).decode("utf-8")

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()  # undo any partial changes
        print(f"Error updating password for patient {patient_id}: {e}")
        return jsonify({"error": "Failed to update password"}), 500

    return jsonify({"message": "Password updated successfully"})

# ---------------------------
# UPDATE PATIENT PROFILE
# ---------------------------

@app.route("/patient/update_profile", methods=["POST"])
def patient_update_profile():
    data = request.get_json()
    patient_id = data.get("patient_id")
    
    patient = Patient.query.filter_by(patient_id=patient_id).first()
    if not patient:
        return jsonify({"error": "Patient not found"}), 404

    # Update fields if provided
    new_name = data.get("name")
    new_email = data.get("email")
    new_phone = data.get("phone_number")

    if new_email and new_email != patient.email:
        # Check if email already exists
        if Patient.query.filter_by(email=new_email).first():
            return jsonify({"error": "Email already in use"}), 400
        patient.email = new_email

    if new_name:
        patient.name = new_name

    if new_phone:
        patient.phone_number = new_phone

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()  # undo any partial changes
        print(f"Error updating profile for patient {patient_id}: {e}")
        return jsonify({"error": "Failed to update profile"}), 500

    return jsonify({"message": "Profile updated successfully"})

# ---------------------------
# DELETE PATIENT ACCOUNT
# ---------------------------

@app.route("/patient/delete_account", methods=["POST"])
def patient_delete_account():
    data = request.get_json()
    patient_id = data.get("patient_id")

    patient = Patient.query.filter_by(patient_id=patient_id).first()
    if not patient:
        return jsonify({"error": "Patient not found"}), 404

    patient.is_active = False

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting patient account {patient_id}: {e}")
        return jsonify({"error": "Failed to delete account"}), 500

    return jsonify({"message": "Account deleted successfully"})

# ---------------------------
# FORGOT PASSWORD
# ---------------------------

@app.route("/patient/forgot_password", methods=["POST"])
def forgot_password():

    data = request.get_json()
    email = data.get("email")

    patient = Patient.query.filter_by(email=email).first()

    if not patient:
        return jsonify({"error": "Email not found"}), 404

    # DELETE OLD OTPs FOR THIS EMAIL
    PasswordResetOTP.query.filter_by(email=email).delete()
    db.session.commit()

    otp = ''.join(random.choices(string.digits, k=6))

    otp_record = PasswordResetOTP(
        email=email,
        otp=otp,
        expires_at=datetime.utcnow() + timedelta(minutes=5),
        verified=False
    )

    db.session.add(otp_record)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error saving OTP for {email}: {e}")
        return jsonify({"error": "Failed to generate OTP"}), 500

    print("OTP:", otp)

    return jsonify({"message": "OTP sent"})


# ---------------------------
# VERIFY OTP
# ---------------------------

@app.route("/patient/verify_otp", methods=["POST"])
def verify_otp():

    data = request.get_json()
    email = data.get("email")
    otp = data.get("otp")

    # Cleanup expired OTPs
    try:
        PasswordResetOTP.query.filter(
            PasswordResetOTP.expires_at < datetime.utcnow()
        ).delete()
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error cleaning up expired OTPs: {e}")
        return jsonify({"error": "Failed to cleanup expired OTPs"}), 500

    # Verify OTP
    record = PasswordResetOTP.query.filter_by(email=email, otp=otp).first()

    if not record:
        return jsonify({"error": "Invalid OTP"}), 400

    record.verified = True
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error verifying OTP for {email}: {e}")
        return jsonify({"error": "Failed to verify OTP"}), 500

    return jsonify({"message": "OTP verified"})

# ---------------------------
# RESET PASSWORD
# ---------------------------

@app.route("/patient/reset_password", methods=["POST"])
def reset_password():

    data = request.get_json()
    email = data.get("email")

    # Check for verified OTP
    record = PasswordResetOTP.query.filter_by(email=email, verified=True).first()
    if not record:
        return jsonify({"error": "OTP verification required"}), 400

    if data.get("new_password") != data.get("confirm_password"):
        return jsonify({"error": "Passwords do not match"}), 400

    # Find patient
    patient = Patient.query.filter_by(email=email).first()
    if not patient:
        return jsonify({"error": "Patient not found"}), 404

    # Update password safely
    try:
        patient.password = bcrypt.generate_password_hash(
            data.get("new_password")
        ).decode("utf-8")
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error updating password for {email}: {e}")
        return jsonify({"error": "Failed to update password"}), 500

    # Delete OTPs safely
    try:
        PasswordResetOTP.query.filter_by(email=email).delete()
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting OTPs for {email}: {e}")
        # Not critical to block password update, just log

    return jsonify({"message": "Password reset successful"})
# ---------------------------
# ADMIN DASHBOARD
# ---------------------------

@app.route("/admin/dashboard")
def admin_dashboard():

    return jsonify({
        "total_clinicians": Clinician.query.count(),
        "total_patients": Patient.query.count(),
        "active_cases": Patient.query.filter(
            Patient.is_active==True,
            Patient.status.in_(["attention", "critical"])
        ).count()
    })

# ---------------------------
# CREATE PATIENT
# ---------------------------

@app.route("/clinician/create_patient", methods=["POST"])
def create_patient():

    data = request.get_json()

    if Patient.query.filter_by(patient_id=data.get("patient_id")).first():
        return jsonify({"error": "Patient ID already exists"}), 400

    hashed_pw = bcrypt.generate_password_hash(
        data.get("phone_number")
    ).decode("utf-8")

    patient = Patient(
        patient_id=data.get("patient_id"),
        name=data.get("name"),
        email=data.get("email"),
        phone_number=data.get("phone_number"),
        password=hashed_pw,
        created_by_clinician=data.get("clinician_id")
    )

    db.session.add(patient)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error creating patient {data.get('patient_id')}: {e}")
        return jsonify({"error": "Failed to create patient"}), 500

    return jsonify({"message": "Patient account created"})
# ---------------------------
# UPDATE PATIENT
# ---------------------------

@app.route("/clinician/update_patient", methods=["POST"])
def update_patient():

    valid_stages = PATIENT_STAGES

    valid_status = ["on track", "attention", "critical"]

    data = request.get_json()

    patient = Patient.query.filter_by(patient_id=data.get("patient_id")).first()

    if not patient:
        return jsonify({"error": "Patient not found"}), 404

    stage = data.get("stage", patient.treatment_stage)
    if stage not in valid_stages:
        return jsonify({"error": "Invalid stage"}), 400

    status = data.get("status", patient.status)
    if status not in valid_status:
        return jsonify({"error": "Invalid status"}), 400

    patient.treatment_stage = stage
    patient.status = status

    history = TreatmentHistory(
        patient_id=patient.patient_id,
        stage=stage,
        status=status,
        updated_by=data.get("clinician_id"),
        notes=data.get("notes", "")
    )

    db.session.add(history)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error updating patient {patient.patient_id}: {e}")
        return jsonify({"error": "Failed to update patient"}), 500

    return jsonify({"message": "Patient updated"})
# ---------------------------
# SCHEDULE APPOINTMENT
# ---------------------------

@app.route("/clinician/schedule_appointment", methods=["POST"])
def schedule_appointment():

    data = request.get_json()

    patient = Patient.query.filter_by(patient_id=data.get("patient_id")).first()
    if not patient:
        return jsonify({"error": "Patient does not exist"}), 404

    # --------------------------
    # Validate appointment date
    # --------------------------
    try:
        date_obj = datetime.strptime(data.get("date"), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid date format (YYYY-MM-DD required)"}), 400

    # --------------------------
    # Validate appointment time (HH:MM)
    # --------------------------
    time_str = data.get("time")
    if time_str:
        try:
            datetime.strptime(time_str, "%H:%M")  # expects 24-hour format like 14:30
        except ValueError:
            return jsonify({"error": "Invalid time format (HH:MM expected)"}), 400

    # --------------------------
    # Create Appointment object
    # --------------------------
    appointment = Appointment(
        patient_id=data.get("patient_id"),
        clinician_id=data.get("clinician_id"),
        appointment_date=date_obj,
        appointment_time=time_str,
        appointment_type=data.get("type"),
        notes=data.get("notes", "")
    )

    db.session.add(appointment)

    # --------------------------
    # Commit with error handling
    # --------------------------
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    return jsonify({"message": "Appointment scheduled"})

# ---------------------------
# PATIENT DASHBOARD
# ---------------------------

@app.route("/patient/dashboard/<patient_id>")
def patient_dashboard(patient_id):

    patient = Patient.query.filter_by(patient_id=patient_id).first()

    if not patient:
        return jsonify({"error": "Patient not found"}), 404

    stages = PATIENT_STAGES

    current_index = stages.index(patient.treatment_stage) if patient.treatment_stage in stages else 0
    progress = int(((current_index + 1) / len(stages)) * 100)

    appointment = get_next_appointment(patient_id)

    return jsonify({
        "name": patient.name,
        "treatment_stage": patient.treatment_stage,
        "progress_percent": progress,
        "next_appointment": appointment
    })


# ---------------------------
# PATIENT PROGRESS
# ---------------------------

@app.route("/patient/progress/<patient_id>")
def patient_progress(patient_id):

    patient = Patient.query.filter_by(patient_id=patient_id).first()

    if not patient:
        return jsonify({"error": "Patient not found"}), 404

    stages = PATIENT_STAGES
    current_stage = patient.treatment_stage

    result = []

    for stage in stages:

        status = "pending"

        if stage == current_stage:
            status = "current"

        history = TreatmentHistory.query.filter_by(
            patient_id=patient_id,
            stage=stage
        ).first()

        if history:
            status = "done"

        result.append({
            "stage": stage,
            "status": status
        })

    completed = len([r for r in result if r["status"] == "done"])
    percent = int((completed / len(stages)) * 100)

    return jsonify({
        "progress_percent": percent,
        "stages": result
    })


# ---------------------------
# PATIENT APPOINTMENTS
# ---------------------------

@app.route("/patient/appointments/<patient_id>")
def patient_appointments(patient_id):

    today = datetime.utcnow().date()

    upcoming = Appointment.query.filter(
        Appointment.patient_id == patient_id,
        Appointment.appointment_date >= today
    ).all()

    past = Appointment.query.filter(
        Appointment.patient_id == patient_id,
        Appointment.appointment_date < today
    ).all()

    upcoming_list = []

    for a in upcoming:

        time = a.appointment_time if a.appointment_time else "NA"

        upcoming_list.append({
            "date": str(a.appointment_date),
            "time": time,
            "type": a.appointment_type,
            "status": a.status
        })

    past_list = []

    for a in past:

        past_list.append({
            "date": str(a.appointment_date),
            "type": a.appointment_type,
            "status": "completed"
        })

    return jsonify({
        "upcoming": upcoming_list,
        "past": past_list
    })

# ---------------------------
# PATIENT NOTIFICATIONS / CARE REMINDERS
# ---------------------------

@app.route("/patient/notification/add", methods=["POST"])
def add_notification():
    data = request.get_json()

    patient_id = data.get("patient_id")
    type_ = data.get("type")
    message = data.get("message")
    severity = data.get("severity")
    appointment_id = data.get("appointment_id")

    # ----------------------------
    # Validate notification type
    # ----------------------------
    if type_ not in [e.value for e in NotificationType]:
        return jsonify({"error": "Invalid notification type"}), 400

    clinician_label = None

    # Validate severity only for report_issue
    if type_ == NotificationType.REPORT_ISSUE.value:
        if severity is None or not isinstance(severity, int) or not (1 <= severity <= 10):
            return jsonify({"error": "Invalid severity (1-10 required)"}), 400

        clinician_label = (
            ClinicianLabel.ATTENTION
            if severity <= 6
            else ClinicianLabel.CRITICAL
        )

    notif = PatientNotifications(
        patient_id=patient_id,
        type=NotificationType(type_),
        message=message,
        related_appointment_id=appointment_id,
        report_severity=severity,
        clinician_label=clinician_label
    )

    db.session.add(notif)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error adding notification for {patient_id}: {e}")
        return jsonify({"error": "Failed to add notification"}), 500

    return jsonify({"message": "Notification added successfully"})



@app.route("/patient/notifications/<patient_id>")
def get_notifications(patient_id):
    filters = request.args.getlist("type")  # ?type=oral_hygiene&type=appointment
    query = PatientNotifications.query.filter_by(patient_id=patient_id)

    if filters:
         valid_filters = [f for f in filters if f in [e.value for e in NotificationType]]
         query = query.filter(
             PatientNotifications.type.in_([NotificationType(v) for v in valid_filters])
             )

    notifications = query.order_by(PatientNotifications.created_at.desc()).all()

    result = []
    for n in notifications:
        result.append({
            "id": n.id,
            "type": n.type.value,
            "message": n.message,
            "appointment_id": n.related_appointment_id,
            "report_severity": n.report_severity,
            "clinician_label": n.clinician_label.value if n.clinician_label else None,
            "is_read": n.is_read,
            "created_at": n.created_at.strftime("%Y-%m-%d %H:%M:%S")
        })

    return jsonify(result)

@app.route("/patient/notification/settings", methods=["POST"])
def update_notification_settings():
    data = request.get_json()
    patient_id = data.get("patient_id")

    settings = PatientNotificationSettings.query.filter_by(patient_id=patient_id).first()
    if not settings:
        settings = PatientNotificationSettings(patient_id=patient_id)
        db.session.add(settings)

    for field in ["oral_hygiene", "appliance_care", "appointment"]:
        if field in data:
            setattr(settings, field, bool(data[field]))

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error updating notification settings for patient {patient_id}: {e}")
        return jsonify({"error": "Failed to update settings"}), 500

    return jsonify({"message": "Settings updated successfully"})


@app.route("/patient/notification/read/<int:notif_id>", methods=["POST"])
def mark_notification_read(notif_id):
    notif = PatientNotifications.query.get(notif_id)
    if not notif:
        return jsonify({"error": "Notification not found"}), 404

    notif.is_read = True

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error marking notification {notif_id} as read: {e}")
        return jsonify({"error": "Failed to mark notification"}), 500

    return jsonify({"message": "Notification marked as read"})
# ---------------------------
# SCHEDULER SETUP
# ---------------------------

scheduler = BackgroundScheduler()

# Daily reminders at 7:30 AM IST
scheduler.add_job(
    id='daily_reminders',
    func=send_daily_reminders,
    trigger='cron',
    hour=7,
    minute=30,
    timezone=timezone('Asia/Kolkata')
)

# Optional: OTP cleanup at midnight IST
def cleanup_expired_otps():
    with app.app_context():
        try:
            PasswordResetOTP.query.filter(PasswordResetOTP.expires_at < datetime.utcnow()).delete()
            db.session.commit()
            print("Expired OTPs cleaned up.")
        except Exception as e:
            db.session.rollback()
            print(f"Error cleaning up expired OTPs: {e}")

scheduler.add_job(
    id='cleanup_otps',
    func=cleanup_expired_otps,
    trigger='cron',
    hour=0,
    minute=0,
    timezone=timezone('Asia/Kolkata')
)

# ---------------------------
# CHATBOT ENDPOINT USING SCORING
# ---------------------------

from chatbot.chatbot_engine import find_faq_answer  # put at the top of your file

@app.route("/chatbot", methods=["POST"])
def chatbot():
    data = request.get_json()
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({"reply": "Please enter a message."}), 400

    ai_reply = ask_ai(user_message)

    if ai_reply:
        return jsonify({
            "reply": ai_reply,
            "source": "AI"
        })

    answers = find_faq_answer(user_message, top_n=1)
    top_answer = answers[0]

    return jsonify({
        "reply": top_answer["answer"],
        "score": top_answer["score"],
        "source": "FAQ"
    })

# ---------------------------
# RUN SERVER
# ---------------------------

if __name__ == "__main__":
    with app.app_context():
        db.create_all()  # make sure tables exist before scheduler
    scheduler.start()
    app.run(debug=True, host="0.0.0.0", port=5000)