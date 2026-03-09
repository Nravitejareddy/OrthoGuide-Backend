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

# Admin Table
class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.String(50), unique=True)
    password = db.Column(db.String(255))

    def __repr__(self):
        return f"<Admin {self.admin_id}>"

# Clinician Table
class Clinician(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    clinician_id = db.Column(db.String(50), unique=True)
    name = db.Column(db.String(100))
    phone_number = db.Column(db.String(15))
    password = db.Column(db.String(255))

# Patient Table
class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.String(50), unique=True)
    name = db.Column(db.String(100))
    phone_number = db.Column(db.String(15))
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(255))
    status = db.Column(db.String(50), default="on track")  # on track, attention, critical
    created_by_clinician = db.Column(db.String(50))  # clinician_id

# Create tables
with app.app_context():
    db.create_all()

# ---------------------------
# Home Route
# ---------------------------

@app.route("/")
def home():
    return {"message": "OrthoGuide Backend Running"}

# ---------------------------
# Unified Login API (Admin & Clinician)
# ---------------------------
@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    user_id = data.get("user_id")   # Can be admin_id or clinician_id
    password = data.get("password") # Raw password input

    # Try Admin first
    admin = Admin.query.filter_by(admin_id=user_id).first()
    if admin and bcrypt.check_password_hash(admin.password, password):
        return jsonify({
            "message": "Login successful",
            "role": "admin",
            "user_id": admin.admin_id
        }), 200

    # Try Clinician
    clinician = Clinician.query.filter_by(clinician_id=user_id).first()
    if clinician and bcrypt.check_password_hash(clinician.password, password):
        return jsonify({
            "message": "Login successful",
            "role": "clinician",
            "user_id": clinician.clinician_id,
            "name": clinician.name
        }), 200

    # Invalid credentials
    return jsonify({"error": "Invalid credentials"}), 401

# ---------------------------
# Admin creates Clinician
# ---------------------------
@app.route("/admin/create_clinician", methods=["POST"])
def create_clinician():
    data = request.get_json()
    
    admin_id = data.get("admin_id")
    password = data.get("password")
    
    # Verify admin login
    admin = Admin.query.filter_by(admin_id=admin_id).first()
    if not admin or not bcrypt.check_password_hash(admin.password, password):
        return jsonify({"error": "Invalid admin credentials"}), 401

    # Clinician details
    clinician_id = data.get("clinician_id")
    name = data.get("name")
    phone_number = data.get("phone_number")
    
    # Default password = phone_number
    default_password = bcrypt.generate_password_hash(phone_number).decode("utf-8")
    
    # Check if clinician already exists
    existing = Clinician.query.filter_by(clinician_id=clinician_id).first()
    if existing:
        return jsonify({"error": "Clinician already exists"}), 400
    
    clinician = Clinician(
        clinician_id=clinician_id,
        name=name,
        phone_number=phone_number,
        password=default_password
    )
    
    db.session.add(clinician)
    db.session.commit()
    
    return jsonify({"message": f"Clinician {name} created successfully"}), 201

# ---------------------------
# Create Patient (by Admin or Clinician)
# ---------------------------
@app.route("/create_patient", methods=["POST"])
def create_patient():
    data = request.get_json()

    # Determine who is creating the patient
    admin_id = data.get("admin_id")
    clinician_id = data.get("clinician_id")
    password = data.get("password")  # raw password (admin or clinician)

    creator_name = None

    # Admin creating patient
    if admin_id:
        admin = Admin.query.filter_by(admin_id=admin_id).first()
        if not admin or not bcrypt.check_password_hash(admin.password, password):
            return jsonify({"error": "Invalid admin credentials"}), 401
        creator_name = f"Admin {admin_id}"

    # Clinician creating patient
    elif clinician_id:
        clinician = Clinician.query.filter_by(clinician_id=clinician_id).first()
        if not clinician or not bcrypt.check_password_hash(clinician.password, password):
            return jsonify({"error": "Invalid clinician credentials"}), 401
        creator_name = f"Clinician {clinician_id}"

    else:
        return jsonify({"error": "Creator credentials missing"}), 400

    # Patient details
    patient_id = data.get("patient_id")
    name = data.get("name")
    phone_number = data.get("phone_number")
    email = data.get("email")
    status = data.get("status", "on track")  # default "on track"

    # Default password = phone_number
    default_password = bcrypt.generate_password_hash(phone_number).decode("utf-8")

    # Check if patient already exists
    existing_patient = Patient.query.filter_by(patient_id=patient_id).first()
    if existing_patient:
        return jsonify({"error": "Patient already exists"}), 400

    # Create patient
    patient = Patient(
        patient_id=patient_id,
        name=name,
        phone_number=phone_number,
        email=email,
        password=default_password,
        status=status,
        created_by_clinician=clinician_id if clinician_id else None
    )

    db.session.add(patient)
    db.session.commit()

    return jsonify({"message": f"Patient {name} created successfully by {creator_name}"}), 201

# ---------------------------
# Dashboard API (Admin)
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
    }), 200

# ---------------------------
# Run Server
# ---------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)