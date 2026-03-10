from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
CORS(app)

# ---------------------------
# Database Models
# ---------------------------

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.String(50), unique=True)
    name = db.Column(db.String(100))
    password = db.Column(db.String(255))
    email = db.Column(db.String(100))
    phone_number = db.Column(db.String(15))

    def __repr__(self):
        return f"<Admin {self.admin_id}>"

class Clinician(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    clinician_id = db.Column(db.String(50), unique=True)
    name = db.Column(db.String(100))
    role = db.Column(db.String(50))
    phone_number = db.Column(db.String(15))
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
    created_by_clinician = db.Column(db.String(50))
    is_active = db.Column(db.Boolean, default=True)

with app.app_context():
    db.create_all()

# ---------------------------
# Home Route
# ---------------------------

@app.route("/")
def home():
    return {"message": "OrthoGuide Backend Running"}

# ---------------------------
# Login
# ---------------------------

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    user_id = data.get("user_id")
    password = data.get("password")

    # Admin login
    admin = Admin.query.filter_by(admin_id=user_id).first()
    if admin and bcrypt.check_password_hash(admin.password, password):
        return jsonify({
            "message": "Login successful",
            "role": "admin",
            "user_id": admin.admin_id,
            "name": admin.name
        }), 200

    # Clinician login
    clinician = Clinician.query.filter_by(clinician_id=user_id).first()
    if clinician and bcrypt.check_password_hash(clinician.password, password):

        if not clinician.is_active:
            return jsonify({"error": "Clinician account is inactive"}), 403

        return jsonify({
            "message": "Login successful",
            "role": "clinician",
            "user_id": clinician.clinician_id,
            "name": clinician.name,
            "role_name": clinician.role,
            "is_active": clinician.is_active
        }), 200

    # Patient login
    patient = Patient.query.filter_by(patient_id=user_id).first()
    if patient and bcrypt.check_password_hash(patient.password, password):

        if not patient.is_active:
            return jsonify({"error": "Patient account is inactive"}), 403

        return jsonify({
            "message": "Login successful",
            "role": "patient",
            "user_id": patient.patient_id,
            "name": patient.name,
            "status": patient.status
        }), 200

    return jsonify({"error": "Invalid credentials"}), 401


# ---------------------------
# ADMIN PROFILE
# ---------------------------

@app.route("/admin/get_profile", methods=["POST"])
def get_admin_profile():

    data = request.get_json()

    admin = Admin.query.filter_by(admin_id=data.get("admin_id")).first()

    if not admin:
        return jsonify({"error": "Admin not found"}), 404

    return jsonify({
        "admin_id": admin.admin_id,
        "name": admin.name,
        "email": admin.email,
        "phone_number": admin.phone_number
    }), 200


# ---------------------------
# ADMIN UPDATE PROFILE
# ---------------------------

@app.route("/admin/update_profile", methods=["POST"])
def admin_update_profile():

    data = request.get_json()

    admin = Admin.query.filter_by(admin_id=data.get("admin_id")).first()

    if not admin:
        return jsonify({"error": "Admin not found"}), 404

    if not bcrypt.check_password_hash(admin.password, data.get("password")):
        return jsonify({"error": "Invalid admin credentials"}), 401

    admin.name = data.get("name", admin.name)
    admin.email = data.get("email", admin.email)
    admin.phone_number = data.get("phone_number", admin.phone_number)

    db.session.commit()

    return jsonify({"message": "Admin profile updated successfully"}), 200


# ---------------------------
# ADMIN CHANGE PASSWORD
# ---------------------------

@app.route("/admin/change_password", methods=["POST"])
def admin_change_password():

    data = request.get_json()

    admin = Admin.query.filter_by(admin_id=data.get("admin_id")).first()

    if not admin:
        return jsonify({"error": "Admin not found"}), 404

    if not bcrypt.check_password_hash(admin.password, data.get("current_password")):
        return jsonify({"error": "Current password incorrect"}), 401

    if data.get("new_password") != data.get("confirm_password"):
        return jsonify({"error": "Passwords do not match"}), 400

    admin.password = bcrypt.generate_password_hash(data.get("new_password")).decode("utf-8")

    db.session.commit()

    return jsonify({"message": "Password updated successfully"}), 200


# ---------------------------
# HELP & SUPPORT API
# ---------------------------

@app.route("/system/support", methods=["GET"])
def system_support():

    return jsonify({
        "technical_support_phone": "+91 9876543210",
        "support_email": "support@orthoguide.com",
        "system_version": "2.5.0"
    }), 200


# ---------------------------
# ADMIN DASHBOARD
# ---------------------------

@app.route("/admin/dashboard", methods=["GET"])
def admin_dashboard():

    total_clinicians = Clinician.query.count()
    total_patients = Patient.query.count()

    active_cases = Patient.query.filter(
        Patient.status.in_(["attention","critical"])
    ).count()

    return jsonify({
        "total_clinicians": total_clinicians,
        "total_patients": total_patients,
        "active_cases": active_cases
    }), 200


# ---------------------------
# RUN SERVER
# ---------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)