from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from config import Config
from datetime import datetime, timedelta
import random
import string
from apscheduler.schedulers.background import BackgroundScheduler

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

class PatientNotification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.String(50), nullable=False)
    type = db.Column(db.Enum('oral_hygiene', 'appliance_care', 'appointment', 'report_issue', native_enum=False), nullable=False)
    message = db.Column(db.Text, nullable=False)
    related_appointment_id = db.Column(db.Integer, nullable=True)
    report_severity = db.Column(db.Integer, nullable=True)  # 1-10
    clinician_label = db.Column(db.Enum('attention', 'critical'), nullable=True)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

# ---------------------------
# DAILY REMINDER FUNCTION
# ---------------------------

def send_daily_reminders():
    with app.app_context():
        patients = Patient.query.filter_by(is_active=True).all()
        for patient in patients:
            # Oral hygiene reminder (toggle ON assumed)
            notif = PatientNotification(
                patient_id=patient.patient_id,
                type='oral_hygiene',
                message="Time to maintain your daily oral care!"
            )
            db.session.add(notif)
        db.session.commit()
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

    existing = PatientConsent.query.filter_by(patient_id=data.get("patient_id")).first()

    if existing:
        return jsonify({"message": "Consent already recorded"})

    consent = PatientConsent(
        patient_id=data.get("patient_id"),
        consent_given=True
    )

    db.session.add(consent)
    db.session.commit()

    return jsonify({"message": "Consent saved successfully"})


# ---------------------------
# CHANGE PASSWORD
# ---------------------------

@app.route("/patient/change_password", methods=["POST"])
def patient_change_password():

    data = request.get_json()

    patient = Patient.query.filter_by(patient_id=data.get("patient_id")).first()

    if not patient:
        return jsonify({"error": "Patient not found"}), 404

    if not bcrypt.check_password_hash(patient.password, data.get("old_password")):
        return jsonify({"error": "Old password incorrect"}), 401

    if data.get("new_password") != data.get("confirm_password"):
        return jsonify({"error": "Passwords do not match"}), 400

    patient.password = bcrypt.generate_password_hash(
        data.get("new_password")
    ).decode("utf-8")

    db.session.commit()

    return jsonify({"message": "Password updated successfully"})


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

    otp = ''.join(random.choices(string.digits, k=6))

    otp_record = PasswordResetOTP(
        email=email,
        otp=otp,
        expires_at=datetime.utcnow() + timedelta(minutes=5),
        verified=False
    )

    db.session.add(otp_record)
    db.session.commit()

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

    PasswordResetOTP.query.filter(
        PasswordResetOTP.expires_at < datetime.utcnow()
    ).delete()
    db.session.commit()

    record = PasswordResetOTP.query.filter_by(email=email, otp=otp).first()

    if not record:
        return jsonify({"error": "Invalid OTP"}), 400

    record.verified = True
    db.session.commit()

    return jsonify({"message": "OTP verified"})


# ---------------------------
# RESET PASSWORD
# ---------------------------

@app.route("/patient/reset_password", methods=["POST"])
def reset_password():

    data = request.get_json()
    email = data.get("email")

    record = PasswordResetOTP.query.filter_by(email=email, verified=True).first()

    if not record:
        return jsonify({"error": "OTP verification required"}), 400

    if data.get("new_password") != data.get("confirm_password"):
        return jsonify({"error": "Passwords do not match"}), 400

    patient = Patient.query.filter_by(email=email).first()

    patient.password = bcrypt.generate_password_hash(
        data.get("new_password")
    ).decode("utf-8")

    db.session.commit()

    PasswordResetOTP.query.filter_by(email=email).delete()
    db.session.commit()

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
    db.session.commit()

    return jsonify({"message": "Patient account created"})


# ---------------------------
# UPDATE PATIENT
# ---------------------------

@app.route("/clinician/update_patient", methods=["POST"])
def update_patient():

    valid_stages = [
        "Pre-treatment",
        "Bonding / First Trays",
        "Alignment Phase",
        "Bite Correction",
        "Finishing and Detailing",
        "Debonding and Retention"
    ]

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
    db.session.commit()

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

    try:
        date_obj = datetime.strptime(data.get("date"), "%Y-%m-%d").date()
    except:
        return jsonify({"error": "Invalid date format (YYYY-MM-DD required)"}), 400

    appointment = Appointment(
        patient_id=data.get("patient_id"),
        clinician_id=data.get("clinician_id"),
        appointment_date=date_obj,
        appointment_time=data.get("time"),
        appointment_type=data.get("type"),
        notes=data.get("notes", "")
    )

    db.session.add(appointment)
    db.session.commit()

    return jsonify({"message": "Appointment scheduled"})


# ---------------------------
# PATIENT DASHBOARD
# ---------------------------

@app.route("/patient/dashboard/<patient_id>")
def patient_dashboard(patient_id):

    patient = Patient.query.filter_by(patient_id=patient_id).first()

    if not patient:
        return jsonify({"error": "Patient not found"}), 404

    stages = [
        "Pre-treatment",
        "Bonding / First Trays",
        "Alignment Phase",
        "Bite Correction",
        "Finishing and Detailing",
        "Debonding and Retention"
    ]

    current_index = stages.index(patient.treatment_stage) if patient.treatment_stage in stages else 0
    progress = int(((current_index) / len(stages)) * 100)

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

    stages = [
        "Initial Consultation",
        "Bonding / First Trays",
        "Alignment Phase",
        "Bite Correction",
        "Finishing and Detailing",
        "Debonding and Retention"
    ]

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
    type_ = data.get("type")  # 'oral_hygiene', 'appliance_care', 'appointment', 'report_issue'
    message = data.get("message")
    severity = data.get("severity")  # optional, only for report_issue
    appointment_id = data.get("appointment_id")  # optional

    clinician_label = None
    if type_ == "report_issue" and severity:
        clinician_label = "attention" if severity <= 6 else "critical"

    notif = PatientNotification(
        patient_id=patient_id,
        type=type_,
        message=message,
        related_appointment_id=appointment_id,
        report_severity=severity,
        clinician_label=clinician_label
    )
    db.session.add(notif)
    db.session.commit()

    return jsonify({"message": "Notification added successfully"})

@app.route("/patient/notifications/<patient_id>")
def get_notifications(patient_id):
    filters = request.args.getlist("type")  # ?type=oral_hygiene&type=appointment
    query = PatientNotification.query.filter_by(patient_id=patient_id)

    if filters:
        query = query.filter(PatientNotification.type.in_(filters))

    notifications = query.order_by(PatientNotification.created_at.desc()).all()

    result = []
    for n in notifications:
        result.append({
            "id": n.id,
            "type": n.type,
            "message": n.message,
            "appointment_id": n.related_appointment_id,
            "report_severity": n.report_severity,
            "clinician_label": n.clinician_label,
            "is_read": n.is_read,
            "created_at": n.created_at.strftime("%Y-%m-%d %H:%M:%S")
        })

    return jsonify(result)

@app.route("/patient/notification/read/<int:notif_id>", methods=["POST"])
def mark_notification_read(notif_id):
    notif = PatientNotification.query.get(notif_id)
    if not notif:
        return jsonify({"error": "Notification not found"}), 404
    notif.is_read = True
    db.session.commit()
    return jsonify({"message": "Notification marked as read"})

scheduler = BackgroundScheduler()
scheduler.add_job(
    id='daily_reminders',
    func=send_daily_reminders,
    trigger='cron',
    hour=2,    # UTC hour (for 7:30 AM IST)
    minute=0
)
scheduler.start()
# ---------------------------
# RUN SERVER
# ---------------------------

if __name__ == "__main__":
    app.run(debug=True)