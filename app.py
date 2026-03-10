from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from config import Config
from datetime import datetime

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
    email = db.Column(db.String(100))  # NEW: purely for display
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


class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.String(50))
    clinician_id = db.Column(db.String(50))
    appointment_date = db.Column(db.Date)
    appointment_time = db.Column(db.String(50))
    appointment_type = db.Column(db.String(50))
    notes = db.Column(db.Text)
    status = db.Column(db.String(50), default="scheduled")


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
    user_id = data.get("user_id")
    password = data.get("password")

    admin = Admin.query.filter_by(admin_id=user_id).first()
    if admin and bcrypt.check_password_hash(admin.password, password):
        return jsonify({"role": "admin", "user_id": admin.admin_id, "name": admin.name})

    clinician = Clinician.query.filter_by(clinician_id=user_id).first()
    if clinician and bcrypt.check_password_hash(clinician.password, password):
        if not clinician.is_active:
            return jsonify({"error": "Clinician inactive"}), 403
        return jsonify({"role": "clinician", "user_id": clinician.clinician_id, "name": clinician.name})

    patient = Patient.query.filter_by(patient_id=user_id).first()
    if patient and bcrypt.check_password_hash(patient.password, password):
        if not patient.is_active:
            return jsonify({"error": "Patient inactive"}), 403
        return jsonify({"role": "patient", "user_id": patient.patient_id, "name": patient.name})

    return jsonify({"error": "Invalid credentials"}), 401

# ---------------------------
# ADMIN DASHBOARD
# ---------------------------

@app.route("/admin/dashboard", methods=["GET"])
def admin_dashboard():
    total_clinicians = Clinician.query.count()
    total_patients = Patient.query.count()
    active_cases = Patient.query.filter(Patient.status.in_(["attention", "critical"])).count()
    return jsonify({
        "total_clinicians": total_clinicians,
        "total_patients": total_patients,
        "active_cases": active_cases
    })

# ---------------------------
# CLINICIAN DASHBOARD
# ---------------------------

@app.route("/clinician/dashboard", methods=["POST"])
def clinician_dashboard():
    data = request.get_json()
    clinician_id = data.get("clinician_id")

    total_patients = Patient.query.filter_by(created_by_clinician=clinician_id).count()
    active_cases = Patient.query.filter(Patient.created_by_clinician==clinician_id, Patient.is_active==True).count()
    priority_cases = Patient.query.filter(Patient.created_by_clinician==clinician_id, Patient.status.in_(["attention", "critical"])).count()

    priority_patients = Patient.query.filter(
        Patient.created_by_clinician==clinician_id,
        Patient.status.in_(["attention", "critical"]),
        ~Patient.patient_id.in_(db.session.query(Appointment.patient_id))
    ).limit(5).all()

    patient_list = [{"patient_id": p.patient_id, "name": p.name, "status": p.status, "stage": p.treatment_stage} for p in priority_patients]

    return jsonify({
        "total_patients": total_patients,
        "active_cases": active_cases,
        "priority_cases": priority_cases,
        "priority_patients": patient_list
    })

# ---------------------------
# CREATE PATIENT
# ---------------------------

@app.route("/clinician/create_patient", methods=["POST"])
def create_patient():
    data = request.get_json()
    hashed_pw = bcrypt.generate_password_hash(data.get("password")).decode("utf-8")
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
# PATIENT SEARCH + FILTER
# ---------------------------

@app.route("/clinician/patients", methods=["POST"])
def clinician_patients():
    data = request.get_json()
    clinician_id = data.get("clinician_id")
    search = data.get("search", "")
    status = data.get("status", "all")

    query = Patient.query.filter_by(created_by_clinician=clinician_id)
    if status != "all":
        query = query.filter(Patient.status==status)
    if search:
        query = query.filter((Patient.name.like(f"%{search}%")) | (Patient.patient_id.like(f"%{search}%")))

    patients = query.all()
    result = []
    for p in patients:
        appointment = Appointment.query.filter_by(patient_id=p.patient_id).first()
        appointment_status = "Appointment Scheduled" if appointment else "No Appointment Scheduled"
        result.append({
            "patient_id": p.patient_id,
            "name": p.name,
            "stage": p.treatment_stage,
            "status": p.status,
            "appointment_status": appointment_status
        })
    return jsonify(result)

# ---------------------------
# PATIENT PROFILE
# ---------------------------

@app.route("/clinician/patient_profile", methods=["POST"])
def patient_profile():
    data = request.get_json()
    patient = Patient.query.filter_by(patient_id=data.get("patient_id")).first()
    appointment = Appointment.query.filter_by(patient_id=patient.patient_id).order_by(Appointment.id.desc()).first()

    appointment_data = None
    if appointment:
        appointment_data = {
            "id": appointment.id,
            "date": str(appointment.appointment_date),
            "time": appointment.appointment_time,
            "type": appointment.appointment_type,
            "notes": appointment.notes
        }

    return jsonify({
        "patient_id": patient.patient_id,
        "name": patient.name,
        "stage": patient.treatment_stage,
        "status": patient.status,
        "appointment": appointment_data
    })

# ---------------------------
# UPDATE PATIENT
# ---------------------------

@app.route("/clinician/update_patient", methods=["POST"])
def update_patient():
    data = request.get_json()
    patient = Patient.query.filter_by(patient_id=data.get("patient_id")).first()
    patient.treatment_stage = data.get("stage", patient.treatment_stage)
    patient.status = data.get("status", patient.status)
    db.session.commit()
    return jsonify({"message": "Patient updated"})

# ---------------------------
# SCHEDULE APPOINTMENT
# ---------------------------

@app.route("/clinician/schedule_appointment", methods=["POST"])
def schedule_appointment():
    data = request.get_json()
    date_obj = datetime.strptime(data.get("date"), "%Y-%m-%d").date()
    appointment = Appointment(
        patient_id=data.get("patient_id"),
        clinician_id=data.get("clinician_id"),
        appointment_date=date_obj,
        appointment_time=data.get("time"),
        appointment_type=data.get("type"),
        notes=data.get("notes")
    )
    db.session.add(appointment)
    db.session.commit()
    return jsonify({"message": "Appointment scheduled"})

# ---------------------------
# RESCHEDULE APPOINTMENT
# ---------------------------

@app.route("/clinician/reschedule_appointment", methods=["POST"])
def reschedule_appointment():
    data = request.get_json()
    appointment = Appointment.query.get(data.get("appointment_id"))
    appointment.appointment_date = datetime.strptime(data.get("date"), "%Y-%m-%d").date()
    appointment.appointment_time = data.get("time")
    appointment.appointment_type = data.get("type")
    appointment.notes = data.get("notes")
    db.session.commit()
    return jsonify({"message": "Appointment rescheduled"})

# ---------------------------
# DELETE APPOINTMENT
# ---------------------------

@app.route("/clinician/delete_appointment", methods=["POST"])
def delete_appointment():
    data = request.get_json()
    appointment = Appointment.query.get(data.get("appointment_id"))
    if not appointment:
        return jsonify({"error": "Appointment not found"}), 404
    db.session.delete(appointment)
    db.session.commit()
    return jsonify({"message": "Appointment deleted"})

# ---------------------------
# SCHEDULE BY DATE
# ---------------------------

@app.route("/clinician/schedule_by_date", methods=["POST"])
def schedule_by_date():
    data = request.get_json()
    clinician_id = data.get("clinician_id")
    date = datetime.strptime(data.get("date"), "%Y-%m-%d").date()

    appointments = Appointment.query.filter_by(clinician_id=clinician_id, appointment_date=date).all()
    result = []
    for a in appointments:
        patient = Patient.query.filter_by(patient_id=a.patient_id).first()
        result.append({
            "appointment_id": a.id,
            "time": a.appointment_time if a.appointment_time else "TBD",
            "patient_name": patient.name,
            "patient_id": patient.patient_id,
            "stage": patient.treatment_stage,
            "appointment_type": a.appointment_type,
            "status": patient.status
        })

    result = sorted(result, key=lambda x: (x["time"] == "TBD", x["time"]))
    return jsonify(result)

# ---------------------------
# CLINICIAN PROFILE APIs
# ---------------------------

@app.route("/clinician/profile", methods=["POST"])
def get_clinician_profile():
    data = request.get_json()
    clinician = Clinician.query.filter_by(clinician_id=data.get("clinician_id")).first()
    if not clinician:
        return jsonify({"error": "Clinician not found"}), 404
    return jsonify({
        "clinician_id": clinician.clinician_id,
        "name": clinician.name,
        "role": clinician.role,
        "phone_number": clinician.phone_number,
        "email": clinician.email  # include email in response
    })


@app.route("/clinician/edit_profile", methods=["POST"])
def edit_clinician_profile():
    data = request.get_json()
    clinician = Clinician.query.filter_by(clinician_id=data.get("clinician_id")).first()
    if not clinician:
        return jsonify({"error": "Clinician not found"}), 404

    clinician.name = data.get("name", clinician.name)
    clinician.role = data.get("role", clinician.role)
    clinician.phone_number = data.get("phone_number", clinician.phone_number)
    clinician.email = data.get("email", clinician.email)  # allow editing email
    db.session.commit()
    return jsonify({"message": "Profile updated successfully"})


@app.route("/clinician/change_password", methods=["POST"])
def clinician_change_password():
    data = request.get_json()
    clinician = Clinician.query.filter_by(clinician_id=data.get("clinician_id")).first()
    if not clinician:
        return jsonify({"error": "Clinician not found"}), 404

    if not bcrypt.check_password_hash(clinician.password, data.get("old_password")):
        return jsonify({"error": "Old password incorrect"}), 401

    if data.get("new_password") != data.get("confirm_password"):
        return jsonify({"error": "Passwords do not match"}), 400

    clinician.password = bcrypt.generate_password_hash(data.get("new_password")).decode("utf-8")
    db.session.commit()
    return jsonify({"message": "Password updated successfully"})


@app.route("/clinician/deactivate_account", methods=["POST"])
def clinician_deactivate_account():
    data = request.get_json()
    clinician = Clinician.query.filter_by(clinician_id=data.get("clinician_id")).first()
    if not clinician:
        return jsonify({"error": "Clinician not found"}), 404
    clinician.is_active = False
    db.session.commit()
    return jsonify({"message": "Account deactivated"})


# ---------------------------
# SYSTEM SUPPORT
# ---------------------------

@app.route("/system/support", methods=["GET"])
def system_support():
    return jsonify({
        "technical_support_phone": "+919876543210",
        "support_email": "support@orthoguide.com",
        "system_version": "2.5.0"
    })

# ---------------------------
# RUN SERVER
# ---------------------------

if __name__ == "__main__":
    app.run(debug=True)