from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from config import Config
from datetime import datetime, timedelta
import random
import string

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


with app.app_context():
    db.create_all()

# ---------------------------
# HOME
# ---------------------------

@app.route("/")
def home():
    return {"message": "OrthoGuide Backend Running"}

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
        return jsonify({"role": "admin", "user_id": admin.admin_id, "name": admin.name})

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
            "consent_given": True if consent else False
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
        "consent_given": True if consent else False
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

    patient.password = bcrypt.generate_password_hash(data.get("new_password")).decode("utf-8")

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

    record = PasswordResetOTP.query.filter_by(email=email, otp=otp).first()

    if not record:
        return jsonify({"error": "Invalid OTP"}), 400

    if datetime.utcnow() > record.expires_at:
        return jsonify({"error": "OTP expired"}), 400

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

    if not patient:
        return jsonify({"error": "Email not found"}), 404

    patient.password = bcrypt.generate_password_hash(data.get("new_password")).decode("utf-8")

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

    hashed_pw = bcrypt.generate_password_hash(data.get("phone_number")).decode("utf-8")

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
# RUN SERVER
# ---------------------------

if __name__ == "__main__":
    app.run(debug=True)