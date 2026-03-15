from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from config import Config
from datetime import datetime, timedelta
import random
import string
from apscheduler.schedulers.background import BackgroundScheduler
from pytz import timezone
from sqlalchemy import Enum
from enum import Enum as PyEnum
from chatbot.chatbot_engine import find_faq_answer
import smtplib
from email.mime.text import MIMEText

# ---------------------------
# Logging configuration
# ---------------------------
import logging

logging.basicConfig(
    filename='app.log',           # Log file name
    level=logging.INFO,           # Minimum level to log (INFO, ERROR, WARNING)
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# ---------------------------
# EMAIL OTP FUNCTION
# ---------------------------
def send_email_otp(to_email, otp):
    msg = MIMEText(f"Your password reset OTP is: {otp}")
    msg['Subject'] = "Password Reset OTP"
    msg['From'] = "yourgmail@gmail.com"
    msg['To'] = to_email

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login("yourgmail@gmail.com", "your_16_digit_app_password")
        server.send_message(msg)
        server.quit()
    except Exception as e:
        logging.error(f"Error sending OTP email to {to_email}: {e}")

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
    notes = db.Column(db.Text, nullable=True)
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

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.String(50))
    clinician_id = db.Column(db.String(50))
    appointment_date = db.Column(db.Date)
    appointment_time = db.Column(db.String(50))
    appointment_type = db.Column(db.String(50))
    notes = db.Column(db.Text)
    status = db.Column(db.String(50), default="scheduled")


# ---------------------------
# SYSTEM SETTINGS MODEL
# ---------------------------

class AppSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    clinic_phone = db.Column(db.String(20), default="+91 98765 43210")
    support_email = db.Column(db.String(100), default="support@orthoguide.com")
    admin_phone = db.Column(db.String(20), default="+91 98765 43210")
    admin_email = db.Column(db.String(100), default="admin@orthoguide.com")
    system_support_email = db.Column(db.String(100), default="support-admin@orthoguide.com")
    system_version = db.Column(db.String(20), default="2.5.0")
    clinic_name = db.Column(db.String(100), default="OrthoGuide Clinic")

with app.app_context():
    db.create_all()

    if not AppSettings.query.first():
        settings = AppSettings()
        db.session.add(settings)
        db.session.commit()

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
            logging.error(f"Error committing notifications: {e}")

    logging.info("Daily reminders sent!")
# ---------------------------
# HOME
# ---------------------------

@app.route("/")
def home():
    return {"message": "OrthoGuide Backend Running"}

# ---------------------------
# SUPPORT INFO
# ---------------------------

@app.route("/support/info", methods=["GET"])
def support_info():
    settings = AppSettings.query.first()

    return jsonify({
        "clinic_phone": settings.clinic_phone,
        "support_email": settings.support_email,
        "system_version": settings.system_version
    })

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

        clinician = Clinician.query.filter_by(clinician_id=appointment.clinician_id).first()
        clinician_name = clinician.name if clinician else None

        return {
            "date": str(appointment.appointment_date),
            "time": time,
            "type": appointment.appointment_type,
            "clinician_name": clinician_name
        }

    return None

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
    role = data.get("role")

    if role == "admin":

        admin = Admin.query.filter_by(admin_id=user_id).first()

        if admin and bcrypt.check_password_hash(admin.password, password):
            return jsonify({
                "role": "admin",
                "user_id": admin.admin_id,
                "name": admin.name
            })

        return jsonify({"error": "Invalid admin credentials"}), 401


    elif role == "clinician":

        clinician = Clinician.query.filter_by(clinician_id=user_id).first()

        if not clinician:
            return jsonify({"error": "Clinician not found"}), 404

        if not bcrypt.check_password_hash(clinician.password, password):
            return jsonify({"error": "Invalid password"}), 401

        if not clinician.is_active:
            return jsonify({"error": "Clinician inactive"}), 403

        return jsonify({
            "role": "clinician",
            "user_id": clinician.clinician_id,
            "name": clinician.name
        })


    elif role == "patient":

        patient = Patient.query.filter_by(patient_id=user_id).first()

        if not patient:
            return jsonify({"error": "Patient not found"}), 404

        if not bcrypt.check_password_hash(patient.password, password):
            return jsonify({"error": "Incorrect password"}), 401

        if not patient.is_active:
            return jsonify({"error": "Patient inactive"}), 403

        consent = PatientConsent.query.filter_by(patient_id=patient.patient_id).first()

        return jsonify({
            "role": "patient",
            "user_id": patient.patient_id,
            "name": patient.name,
            "consent_given": consent.consent_given if consent else False
        })

    return jsonify({"error": "Invalid role"}), 400


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
# CLINICIAN LOGIN
# ---------------------------

@app.route("/clinician/login", methods=["POST"])
def clinician_login():
    data = request.get_json()

    clinician_id = data.get("clinician_id")
    password = data.get("password")

    clinician = Clinician.query.filter_by(clinician_id=clinician_id).first()

    if not clinician:
        return jsonify({"message": "Clinician not found"}), 404

    if not bcrypt.check_password_hash(clinician.password, password):
        return jsonify({"message": "Invalid credentials"}), 401

    return jsonify({
        "message": "Login successful",
        "clinician_id": clinician.clinician_id,
        "name": clinician.name,
        "role": clinician.role
    }), 200

# ---------------------------
# GET CLINICIAN PROFILE
# ---------------------------

@app.route("/clinician/profile/<clinician_id>", methods=["GET"])
def get_clinician_profile(clinician_id):

    clinician = Clinician.query.filter_by(clinician_id=clinician_id).first()

    if not clinician:
        return jsonify({"error": "Clinician not found"}), 404

    return jsonify({
        "clinician_id": clinician.clinician_id,
        "name": clinician.name,
        "role": clinician.role,
        "email": clinician.email,
        "phone_number": clinician.phone_number
    })


# ---------------------------
# UPDATE CLINICIAN PROFILE
# ---------------------------

@app.route("/clinician/update_profile", methods=["POST"])
def clinician_update_profile():
    data = request.get_json()
    clinician_id = data.get("clinician_id")

    clinician = Clinician.query.filter_by(clinician_id=clinician_id).first()
    if not clinician:
        return jsonify({"error": "Clinician not found"}), 404

    new_name = data.get("name")
    new_role = data.get("role")
    new_email = data.get("email")
    new_phone = data.get("phone_number")

    if new_email and new_email != clinician.email:
        if Clinician.query.filter_by(email=new_email).first():
            return jsonify({"error": "Email already in use"}), 400
        clinician.email = new_email

    if new_name:
        clinician.name = new_name

    if new_role:
        clinician.role = new_role

    if new_phone:
        clinician.phone_number = new_phone

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error updating profile for clinician {clinician_id}: {e}")
        return jsonify({"error": "Failed to update profile"}), 500

    return jsonify({"message": "Profile updated successfully"})


# ---------------------------
# CHANGE CLINICIAN PASSWORD
# ---------------------------

@app.route("/clinician/change_password", methods=["POST"])
def clinician_change_password():

    data = request.get_json()
    clinician_id = data.get("clinician_id")
    clinician = Clinician.query.filter_by(clinician_id=clinician_id).first()

    if not clinician:
        return jsonify({"error": "Clinician not found"}), 404

    if not bcrypt.check_password_hash(clinician.password, data.get("old_password")):
        return jsonify({"error": "Old password incorrect"}), 401

    if data.get("new_password") != data.get("confirm_password"):
        return jsonify({"error": "Passwords do not match"}), 400

    clinician.password = bcrypt.generate_password_hash(
        data.get("new_password")
    ).decode("utf-8")

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error updating password for clinician {clinician_id}: {e}")
        return jsonify({"error": "Failed to update password"}), 500

    return jsonify({"message": "Password updated successfully"})


# ---------------------------
# DEACTIVATE CLINICIAN ACCOUNT
# ---------------------------

@app.route("/clinician/deactivate_account", methods=["POST"])
def clinician_deactivate_account():
    data = request.get_json()
    clinician_id = data.get("clinician_id")

    clinician = Clinician.query.filter_by(clinician_id=clinician_id).first()
    if not clinician:
        return jsonify({"error": "Clinician not found"}), 404

    clinician.is_active = False

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error deactivating clinician account {clinician_id}: {e}")
        return jsonify({"error": "Failed to deactivate account"}), 500

    return jsonify({"message": "Account deactivated successfully"})

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
        logging.error(f"Error saving consent for patient {patient_id}: {e}")
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
        logging.error(f"Error updating password for patient {patient_id}: {e}")
        return jsonify({"error": "Failed to update password"}), 500

    return jsonify({"message": "Password updated successfully"})
# ---------------------------
# GET PATIENT PROFILE
# ---------------------------

@app.route("/patient/profile/<patient_id>", methods=["GET"])
def get_patient_profile(patient_id):

    patient = Patient.query.filter_by(patient_id=patient_id).first()

    if not patient:
        return jsonify({"error": "Patient not found"}), 404

    return jsonify({
        "patient_id": patient.patient_id,
        "name": patient.name,
        "email": patient.email,
        "phone_number": patient.phone_number
    })
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
        logging.error(f"Error updating profile for patient {patient_id}: {e}")
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
        logging.error(f"Error deleting patient account {patient_id}: {e}")
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
        logging.error(f"Error saving OTP for {email}: {e}")
        return jsonify({"error": "Failed to generate OTP"}), 500

    #print("OTP:", otp)
    send_email_otp(email, otp)
    return jsonify({"message": "OTP sent to registered email"})


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
        logging.error(f"Error cleaning up expired OTPs: {e}")
        return jsonify({"error": "Failed to cleanup expired OTPs"}), 500

    # Verify OTP
    record = PasswordResetOTP.query.filter_by(email=email, otp=otp).first()

    if not record:
        return jsonify({"error": "Invalid OTP"}), 400

    if record.expires_at < datetime.utcnow():
        return jsonify({"error": "OTP expired"}), 400

    record.verified = True
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error verifying OTP for {email}: {e}")
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
        logging.error(f"Error updating password for {email}: {e}")
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

@app.route("/admin/system_settings", methods=["GET"])
def get_system_settings():
    settings = AppSettings.query.first()

    return jsonify({
        "clinic_phone": settings.clinic_phone,
        "support_email": settings.support_email,
        "admin_phone": settings.admin_phone,
        "admin_email": settings.admin_email,
        "system_support_email": settings.system_support_email,
        "system_version": settings.system_version,
        "clinic_name": settings.clinic_name
    })


@app.route("/admin/system_settings", methods=["POST"])
def update_system_settings():
    data = request.get_json()
    settings = AppSettings.query.first()

    if not settings:
        settings = AppSettings()
        db.session.add(settings)

    settings.clinic_phone = data.get("clinic_phone", settings.clinic_phone)
    settings.support_email = data.get("support_email", settings.support_email)
    settings.admin_phone = data.get("admin_phone", settings.admin_phone)
    settings.admin_email = data.get("admin_email", settings.admin_email)
    settings.system_support_email = data.get("system_support_email", settings.system_support_email)
    settings.system_version = data.get("system_version", settings.system_version)
    settings.clinic_name = data.get("clinic_name", settings.clinic_name)

    db.session.commit()

    return jsonify({"message": "System settings updated successfully"})

# ---------------------------
# GET ALL CLINICIANS
# ---------------------------

@app.route("/admin/clinicians", methods=["GET"])
def get_all_clinicians():

    clinicians = Clinician.query.all()

    result = []

    for c in clinicians:
        result.append({
            "clinician_id": c.clinician_id,
            "name": c.name,
            "role": c.role,
            "email": c.email,
            "phone_number": c.phone_number,
            "is_active": c.is_active
        })

    return jsonify(result)


# ---------------------------
# CREATE CLINICIAN
# ---------------------------

@app.route("/admin/create_clinician", methods=["POST"])
def create_clinician():

    data = request.get_json()

    if Clinician.query.filter_by(clinician_id=data.get("clinician_id")).first():
        return jsonify({"error": "Clinician ID already exists"}), 400

    if Clinician.query.filter_by(email=data.get("email")).first():
        return jsonify({"error": "Email already exists"}), 400

    hashed_pw = bcrypt.generate_password_hash(
        data.get("phone_number")
    ).decode("utf-8")

    clinician = Clinician(
        clinician_id=data.get("clinician_id"),
        name=data.get("name"),
        role=data.get("role"),
        email=data.get("email"),
        phone_number=data.get("phone_number"),
        password=hashed_pw
    )

    db.session.add(clinician)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    return jsonify({"message": "Clinician created successfully"})


# ---------------------------
# DEACTIVATE CLINICIAN
# ---------------------------

@app.route("/admin/clinician/deactivate", methods=["POST"])
def deactivate_clinician():

    data = request.get_json()

    clinician = Clinician.query.filter_by(
        clinician_id=data.get("clinician_id")
    ).first()

    if not clinician:
        return jsonify({"error": "Clinician not found"}), 404

    clinician.is_active = False

    db.session.commit()

    return jsonify({"message": "Clinician deactivated"})


# ---------------------------
# RESET CLINICIAN PASSWORD
# ---------------------------

@app.route("/admin/clinician/reset_password", methods=["POST"])
def reset_clinician_password():

    data = request.get_json()

    clinician = Clinician.query.filter_by(
        clinician_id=data.get("clinician_id")
    ).first()

    if not clinician:
        return jsonify({"error": "Clinician not found"}), 404

    new_pw = bcrypt.generate_password_hash(
        clinician.phone_number
    ).decode("utf-8")

    clinician.password = new_pw

    db.session.commit()

    return jsonify({"message": "Password reset to phone number"})


# ---------------------------
# GET ALL PATIENTS
# ---------------------------

@app.route("/admin/patients", methods=["GET"])
def get_all_patients():

    patients = Patient.query.all()

    result = []

    for p in patients:
        result.append({
            "patient_id": p.patient_id,
            "name": p.name,
            "email": p.email,
            "phone_number": p.phone_number,
            "status": p.status,
            "treatment_stage": p.treatment_stage,
            "is_active": p.is_active
        })

    return jsonify(result)


# ---------------------------
# DEACTIVATE PATIENT
# ---------------------------

@app.route("/admin/patient/deactivate", methods=["POST"])
def deactivate_patient():

    data = request.get_json()

    patient = Patient.query.filter_by(
        patient_id=data.get("patient_id")
    ).first()

    if not patient:
        return jsonify({"error": "Patient not found"}), 404

    patient.is_active = False

    db.session.commit()

    return jsonify({"message": "Patient deactivated"})


# ---------------------------
# RESET PATIENT PASSWORD
# ---------------------------

@app.route("/admin/patient/reset_password", methods=["POST"])
def reset_patient_password():

    data = request.get_json()

    patient = Patient.query.filter_by(
        patient_id=data.get("patient_id")
    ).first()

    if not patient:
        return jsonify({"error": "Patient not found"}), 404

    new_pw = bcrypt.generate_password_hash(
        patient.phone_number
    ).decode("utf-8")

    patient.password = new_pw

    db.session.commit()

    return jsonify({"message": "Patient password reset to phone number"})

# ---------------------------
# CREATE PATIENT
# ---------------------------

@app.route("/clinician/create_patient", methods=["POST"])
def create_patient():

    data = request.get_json()

    if Patient.query.filter_by(patient_id=data.get("patient_id")).first():
        return jsonify({"error": "Patient ID already exists"}), 400
    
    if Patient.query.filter_by(email=data.get("email")).first():
        return jsonify({"error": "Email already exists"}), 400

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
        logging.error(f"Error creating patient {data.get('patient_id')}: {e}")
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
    time_str = data.get("time", "NA")
    if time_str:
        try:
            datetime.strptime(time_str, "%H:%M")  # expects 24-hour format like 14:30
        except ValueError:
            return jsonify({"error": "Invalid time format (HH:MM expected)"}), 400
    else:
        time_str = "NA"
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
# CLINICIAN DASHBOARD
# ---------------------------

@app.route("/clinician/dashboard/<clinician_id>", methods=["GET"])
def clinician_dashboard(clinician_id):
    clinician = Clinician.query.filter_by(clinician_id=clinician_id).first()

    if not clinician:
        return jsonify({"error": "Clinician not found"}), 404

    patients = Patient.query.filter_by(created_by_clinician=clinician_id).all()

    total_patients = len(patients)
    active_patients = len([p for p in patients if p.is_active])
    priority_patients_count = len([p for p in patients if p.status in ["attention", "critical"]])

    priority_patients = []

    for p in patients:

        # Get latest issue notification
        latest_issue = PatientNotifications.query.filter(
            PatientNotifications.patient_id == p.patient_id,
            PatientNotifications.type == NotificationType.REPORT_ISSUE
        ).order_by(PatientNotifications.created_at.desc()).first()

        status = p.status

        if latest_issue and latest_issue.clinician_label:
            status = latest_issue.clinician_label.value

        if status in ["attention", "critical"]:

            next_app = get_next_appointment(p.patient_id)

            priority_patients.append({
                "patient_id": p.patient_id,
                "name": p.name,
                "treatment_stage": p.treatment_stage,
                "status": status,
                "next_appointment": next_app,
                "has_appointment": True if next_app else False
            })

    return jsonify({
        "clinician_id": clinician.clinician_id,
        "clinician_name": clinician.name,
        "clinic_name": "OrthoGuide Clinic",
        "total_patients": total_patients,
        "active_patients": active_patients,
        "priority_patients_count": priority_patients_count,
        "priority_patients": priority_patients
    })

@app.route("/clinician/patient/<patient_id>", methods=["GET"])
def clinician_patient_profile(patient_id):

    patient = Patient.query.filter_by(patient_id=patient_id).first()

    if not patient:
        return jsonify({"error": "Patient not found"}), 404

    next_appointment = get_next_appointment(patient_id)

    latest_history = TreatmentHistory.query.filter_by(
        patient_id=patient_id
    ).order_by(TreatmentHistory.updated_at.desc()).first()

    latest_note = latest_history.notes if latest_history and latest_history.notes else ""

    return jsonify({
        "patient_id": patient.patient_id,
        "name": patient.name,
        "treatment_stage": patient.treatment_stage,
        "status": patient.status,
        "latest_note": latest_note,
        "next_appointment": next_appointment
    })

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
        clinician = Clinician.query.filter_by(clinician_id=a.clinician_id).first()
        clinician_name = clinician.name if clinician else None

        upcoming_list.append({
            "date": str(a.appointment_date),
            "time": time,
            "type": a.appointment_type,
            "status": a.status,
            "clinician_name": clinician_name
        })

    past_list = []

    for a in past:
        clinician = Clinician.query.filter_by(clinician_id=a.clinician_id).first()
        clinician_name = clinician.name if clinician else None   

        past_list.append({
            "date": str(a.appointment_date),
            "type": a.appointment_type,
            "status": "completed",
            "clinician_name": clinician_name
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
    issues = data.get("issues", [])

    # ----------------------------
    # Map issues to severity
    # ----------------------------
    ISSUE_SEVERITY = {
        "Loose Bracket / Band": 6,
        "Poking Wire": 7,
        "Lost Aligner": 5,
        "Severe Pain": 9,
        "Swollen Gums": 6,
        "Broken Appliance": 8
    }

    # If frontend sends issues list and severity not sent explicitly
    if issues and severity is None:
        severity = max([ISSUE_SEVERITY.get(i, 5) for i in issues])

    # If severity comes as string from frontend, convert safely
    if severity is not None:
        try:
            severity = int(severity)
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid severity format"}), 400

    # If issues selected, use them as message
    message = ", ".join(issues) if issues else message

    # ----------------------------
    # Validate notification type
    # ----------------------------
    if type_ not in [e.value for e in NotificationType]:
        return jsonify({"error": "Invalid notification type"}), 400

    clinician_label = None

    # ----------------------------
    # Handle report issue severity + patient status update
    # ----------------------------
    if type_ == NotificationType.REPORT_ISSUE.value:
        if severity is None or not (1 <= severity <= 10):
            return jsonify({"error": "Invalid severity (1-10 required)"}), 400

        clinician_label = (
            ClinicianLabel.ATTENTION
            if severity <= 6
            else ClinicianLabel.CRITICAL
        )

        # Update patient status so clinician dashboard can show attention/critical
        patient = Patient.query.filter_by(patient_id=patient_id).first()
        if patient:
            patient.status = "attention" if severity <= 6 else "critical"
            patient.updated_at = datetime.utcnow()

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
        logging.error(f"Error adding notification for {patient_id}: {e}")
        return jsonify({"error": "Failed to add notification"}), 500

    logging.info(f"Notification added for patient {patient_id}, type={type_}, severity={severity}")

    return jsonify({
        "message": "Notification added successfully",
        "clinician_label": clinician_label.value if clinician_label else None
    })


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

@app.route("/patient/notification/settings/<patient_id>", methods=["GET"])
def get_notification_settings(patient_id):
    settings = PatientNotificationSettings.query.filter_by(patient_id=patient_id).first()

    if not settings:
        return jsonify({
            "patient_id": patient_id,
            "oral_hygiene": True,
            "appliance_care": True,
            "appointment": True
        })

    return jsonify({
        "patient_id": patient_id,
        "oral_hygiene": settings.oral_hygiene,
        "appliance_care": settings.appliance_care,
        "appointment": settings.appointment
    })


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

    logging.info(f"Notification settings updated for patient {patient_id}: { {field: getattr(settings, field) for field in ['oral_hygiene','appliance_care','appointment']} }")
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
        logging.error(f"Error marking notification {notif_id} as read: {e}")
        return jsonify({"error": "Failed to mark notification"}), 500
    
    logging.info(f"Notification {notif_id} marked as read for patient {notif.patient_id}")
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
            PasswordResetOTP.query.filter(
                (PasswordResetOTP.expires_at < datetime.utcnow()) |
                ((PasswordResetOTP.verified == True) &
                 (PasswordResetOTP.expires_at < datetime.utcnow() - timedelta(days=1)))
            ).delete()
            db.session.commit()
            logging.info("Expired OTPs cleaned up.")
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error cleaning up expired OTPs: {e}")

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

@app.route("/chatbot", methods=["POST"])
def chatbot():
    data = request.get_json()
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({"reply": "Please enter a message."}), 400

    results = find_faq_answer(user_message)
    reply = results[0]["answer"] if results else "Sorry, I don't have an answer for that."
    
    return jsonify({
        "reply": reply,
        "source": "FAQ"
    })

# ---------------------------
# ADMIN SETTINGS APIs
# ---------------------------

@app.route("/admin/profile/<admin_id>", methods=["GET"])
def get_admin_profile(admin_id):

    admin = Admin.query.filter_by(admin_id=admin_id).first()

    if not admin:
        return jsonify({"error": "Admin not found"}), 404

    return jsonify({
        "admin_id": admin.admin_id,
        "name": admin.name,
        "email": admin.email,
        "phone_number": admin.phone_number
    })


@app.route("/admin/profile/update", methods=["POST"])
def update_admin_profile():

    data = request.get_json()

    admin = Admin.query.filter_by(admin_id=data.get("admin_id")).first()

    if not admin:
        return jsonify({"error": "Admin not found"}), 404

    admin.name = data.get("name")
    admin.email = data.get("email")
    admin.phone_number = data.get("phone_number")

    db.session.commit()

    return jsonify({"message": "Profile updated successfully"})


@app.route("/admin/change_password", methods=["POST"])
def change_admin_password():

    data = request.get_json()

    admin = Admin.query.filter_by(admin_id=data.get("admin_id")).first()

    if not admin:
        return jsonify({"error": "Admin not found"}), 404

    if not bcrypt.check_password_hash(admin.password, data.get("old_password")):
        return jsonify({"error": "Old password incorrect"}), 400

    new_pw = bcrypt.generate_password_hash(
        data.get("new_password")
    ).decode("utf-8")

    admin.password = new_pw

    db.session.commit()

    return jsonify({"message": "Password changed successfully"})

# ---------------------------
# SYSTEM SUPPORT INFO
# ---------------------------

@app.route("/system/support", methods=["GET"])
def get_system_support():
    settings = AppSettings.query.first()

    return jsonify({
        "admin_phone": settings.admin_phone,
        "support_email": settings.system_support_email,
        "app_version": settings.system_version
    })

# ---------------------------
# RUN SERVER
# ---------------------------

if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    if not scheduler.running:
        scheduler.start()

    print("Server starting on http://127.0.0.1:5000", flush=True)
    app.run(debug=False, host="0.0.0.0", port=5000, use_reloader=False)