from flask import Flask, request, jsonify
import re
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from config import Config
from datetime import datetime, timedelta, UTC
import random
import string
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
from pytz import timezone
from sqlalchemy import func, or_, and_, desc, Enum
from enum import Enum as PyEnum
from chatbot.chatbot_engine import find_faq_answer
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
# Scheduler initialization (will be started in main block)
scheduler = BackgroundScheduler()

logging.basicConfig(
    filename='app.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)

# ---------------------------
# EMAIL OTP FUNCTION
# ---------------------------
def send_email_otp(to_email, otp, user_id="N/A", name="User", role="User"):
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"OrthoGuide - Your Verification Code: {otp}"
    msg['From'] = "orthoguide.ai@gmail.com"
    msg['To'] = to_email

    # Professional HTML Template with Green and White theme
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        .container {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 600px; margin: auto; border: 1px solid #e0e0e0; border-radius: 12px; overflow: hidden; }}
        .header {{ background-color: #10B981; color: white; padding: 30px; text-align: center; }}
        .content {{ padding: 30px; line-height: 1.6; color: #333333; background-color: #ffffff; }}
        .otp-container {{ background-color: #f0fdf4; border: 2px dashed #10B981; border-radius: 8px; padding: 20px; text-align: center; margin: 25px 0; }}
        .otp {{ font-size: 36px; font-weight: bold; color: #059669; letter-spacing: 8px; margin: 0; }}
        .footer {{ background-color: #f9fafb; padding: 20px; font-size: 12px; color: #6b7280; text-align: center; border-top: 1px solid #f3f4f6; }}
        .info-card {{ background-color: #f9fafb; padding: 15px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #10B981; }}
        .label {{ color: #6b7280; font-size: 13px; margin-bottom: 2px; }}
        .value {{ color: #111827; font-weight: 600; margin-bottom: 10px; }}
        .brand {{ color: #10B981; font-weight: bold; text-transform: uppercase; letter-spacing: 1px; }}
    </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div style="font-size: 24px; font-weight: bold;">ORTHOGUIDE</div>
                <div style="font-size: 14px; opacity: 0.9;">Secure Verification</div>
            </div>
            <div class="content">
                <p style="font-size: 18px; margin-top: 0;">Hello <strong>{name}</strong>,</p>
                <p>You requested a verification code for your <span class="brand">OrthoGuide</span> account. Please use the 6-digit code below to proceed:</p>
                
                <div class="otp-container">
                    <div class="otp">{otp}</div>
                </div>
                
                <div class="info-card">
                    <div class="label">ACCOUNT ID</div>
                    <div class="value">{user_id}</div>
                    
                    <div class="label">ACCOUNT ROLE</div>
                    <div class="value">{role.capitalize()}</div>
                    
                    <div class="label">REQUESTED BY</div>
                    <div class="value">System Admin / Dr. Ortho Admin</div>
                </div>
                
                <p style="font-size: 14px; color: #6b7280;">This code is valid for 5 minutes. If you did not request this, please secure your account immediately.</p>
            </div>
            <div class="footer">
                <p>&copy; 2026 OrthoGuide AI. All rights reserved.</p>
                <p>This is an automated message. Please do not reply to this email.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    parts = MIMEText(html_content, 'html')
    msg.attach(parts)

    print(f"\n[DEBUG] OTP for {to_email}: {otp}\n", flush=True)
    logging.info(f"Generated OTP for {to_email}: {otp}")

    sender_email = "orthoguide.ai@gmail.com"
    app_password = "yynyheghqecpjgds"

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, app_password)
        server.send_message(msg)
        server.quit()
        logging.info(f"Email sent successfully to {to_email}")
    except Exception as e:
        logging.error(f"Error sending OTP email to {to_email}: {e}")

def send_patient_update_notification(to_email, name, stage, status, doctor_name="Your Orthodontist"):
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"OrthoGuide - Treatment Updated: {stage}"
    msg['From'] = "orthoguide.ai@gmail.com"
    msg['To'] = to_email

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        .container {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 600px; margin: auto; border: 1px solid #e0e0e0; border-radius: 12px; overflow: hidden; }}
        .header {{ background-color: #10B981; color: white; padding: 30px; text-align: center; }}
        .content {{ padding: 30px; line-height: 1.6; color: #333333; background-color: #ffffff; }}
        .footer {{ background-color: #f9fafb; padding: 20px; font-size: 12px; color: #6b7280; text-align: center; border-top: 1px solid #f3f4f6; }}
        .info-card {{ background-color: #f9fafb; padding: 15px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #10B981; }}
        .label {{ color: #6b7280; font-size: 13px; margin-bottom: 2px; }}
        .value {{ color: #111827; font-weight: 600; margin-bottom: 10px; }}
        .brand {{ color: #10B981; font-weight: bold; text-transform: uppercase; letter-spacing: 1px; }}
    </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div style="font-size: 24px; font-weight: bold;">ORTHOGUIDE</div>
                <div style="font-size: 14px; opacity: 0.9;">Treatment Update</div>
            </div>
            <div class="content">
                <p style="font-size: 18px; margin-top: 0;">Hello <strong>{name}</strong>,</p>
                <p>Your doctor has updated your treatment details at <span class="brand">OrthoGuide</span>. Here is the latest status of your journey:</p>
                
                <div class="info-card">
                    <div class="label">NEW TREATMENT STAGE</div>
                    <div class="value">{stage}</div>
                    
                    <div class="label">CURRENT STATUS</div>
                    <div class="value" style="color: {'#10B981' if status == 'on track' else '#F59E0B' if status == 'attention' else '#EF4444'}; text-transform: uppercase;">{status}</div>
                    
                    <div class="label">UPDATED BY</div>
                    <div class="value">Dr. {doctor_name}</div>
                </div>
                
                <p>Log in to your dashboard to see your updated treatment timeline and care instructions.</p>
                <p style="font-size: 14px; color: #6b7280;">Keep wearing your aligners consistently for the best results!</p>
            </div>
            <div class="footer">
                <p>&copy; 2026 OrthoGuide AI. All rights reserved.</p>
                <p>This is an automated message. Please do not reply to this email.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    parts = MIMEText(html_content, 'html')
    msg.attach(parts)

    sender_email = "orthoguide.ai@gmail.com"
    app_password = "yynyheghqecpjgds"

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, app_password)
        server.send_message(msg)
        server.quit()
        logging.info(f"Update email sent successfully to {to_email}")
    except Exception as e:
        logging.error(f"Error sending update email to {to_email}: {e}")
def send_welcome_email(to_email, name, user_id, password, role, creator_name="OrthoGuide Admin"):
    msg = MIMEMultipart('alternative')
    msg['Subject'] = "Welcome to OrthoGuide - Your Account Credentials"
    msg['From'] = "orthoguide.ai@gmail.com"
    msg['To'] = to_email

    # Professional Welcome Email Template
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        .container {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 600px; margin: auto; border: 1px solid #e0e0e0; border-radius: 12px; overflow: hidden; }}
        .header {{ background-color: #10B981; color: white; padding: 30px; text-align: center; }}
        .content {{ padding: 30px; line-height: 1.6; color: #333333; background-color: #ffffff; }}
        .info-card {{ background-color: #f9fafb; padding: 15px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #10B981; }}
        .label {{ color: #6b7280; font-size: 13px; margin-bottom: 2px; }}
        .value {{ color: #111827; font-weight: 600; margin-bottom: 10px; }}
        .brand {{ color: #10B981; font-weight: bold; text-transform: uppercase; letter-spacing: 1px; }}
        .footer {{ background-color: #f9fafb; padding: 20px; font-size: 12px; color: #6b7280; text-align: center; border-top: 1px solid #f3f4f6; }}
    </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div style="font-size: 24px; font-weight: bold;">ORTHOGUIDE</div>
                <div style="font-size: 14px; opacity: 0.9;">Welcome to the Platform</div>
            </div>
            <div class="content">
                <p style="font-size: 18px; margin-top: 0;">Hello <strong>{name}</strong>,</p>
                <p>Welcome to <span class="brand">OrthoGuide</span>! An account has been created for you by <strong>{creator_name}</strong>. You can now log in using the credentials below:</p>
                
                <div class="info-card">
                    <div class="label">USER ID / LOGIN ID</div>
                    <div class="value">{user_id}</div>
                    
                    <div class="label">REGISTERED EMAIL</div>
                    <div class="value">{to_email}</div>
                    
                    <div class="label">TEMPORARY PASSWORD</div>
                    <div class="value">{password}</div>
                    
                    <div class="label">ACCOUNT ROLE</div>
                    <div class="value">{role.upper()}</div>
                </div>
                
                <p>Please log in and change your password immediately in your profile settings for security reasons.</p>
                <p style="font-size: 14px; color: #6b7280;">We are excited to have you on board!</p>
            </div>
            <div class="footer">
                <p>&copy; 2026 OrthoGuide AI. All rights reserved.</p>
                <p>This is an automated message. Please do not reply to this email.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    parts = MIMEText(html_content, 'html')
    msg.attach(parts)

    sender_email = "orthoguide.ai@gmail.com"
    app_password = "yynyheghqecpjgds"

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, app_password)
        server.send_message(msg)
        server.quit()
        logging.info(f"Welcome email sent successfully to {to_email}")
    except Exception as e:
        logging.error(f"Error sending welcome email to {to_email}: {e}")

PATIENT_STAGES = [
    "Initial Consultation",
    "Bonding / First Trays",
    "Alignment Phase",
    "Bite Correction",
    "Finishing & Detailing",
    "Debonding & Retention"
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

@app.before_request
def log_request_info():
    logging.info(f"Request: {request.method} {request.url}")
    if request.method in ["POST", "PUT"]:
        try:
             logging.info(f"Body: {request.get_json(silent=True)}")
        except Exception:
             pass

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
CORS(app, resources={r"/*": {"origins": "*"}})

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
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))


class Clinician(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    clinician_id = db.Column(db.String(50), unique=True)
    name = db.Column(db.String(100))
    role = db.Column(db.String(50))
    phone_number = db.Column(db.String(15))
    email = db.Column(db.String(100))
    password = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)
    clinic_address = db.Column(db.String(255), nullable=True)
    license_number = db.Column(db.String(50), nullable=True)
    specialization = db.Column(db.String(100), default="Orthodontics")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))


class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.String(50), unique=True)
    name = db.Column(db.String(100))
    phone_number = db.Column(db.String(15))
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(255))
    status = db.Column(db.String(50), default="on track")
    treatment_stage = db.Column(db.String(100), default="Initial Consultation")
    created_by_clinician = db.Column(db.String(50))
    is_active = db.Column(db.Boolean, default=True)
    notes = db.Column(db.Text, nullable=True)
    address = db.Column(db.String(255), nullable=True)
    current_tray = db.Column(db.Integer, default=1)
    total_trays = db.Column(db.Integer, default=6)
    compliance_rate = db.Column(db.Float, default=98.0)
    start_date = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    def __init__(self, **kwargs):
        super(Patient, self).__init__(**kwargs)


class PatientConsent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.String(50))
    consent_given = db.Column(db.Boolean, default=False)
    consent_date = db.Column(db.DateTime, default=lambda: datetime.now(UTC))


class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.String(50))
    clinician_id = db.Column(db.String(50))
    appointment_date = db.Column(db.Date)
    appointment_time = db.Column(db.String(50))
    appointment_type = db.Column(db.String(50))
    notes = db.Column(db.Text)
    status = db.Column(db.String(50), default="scheduled")

    def __init__(self, **kwargs):
        super(Appointment, self).__init__(**kwargs)


class TreatmentHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.String(50))
    stage = db.Column(db.String(100))
    status = db.Column(db.String(50))
    updated_by = db.Column(db.String(50))
    notes = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))


class PasswordResetOTP(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100))
    otp = db.Column(db.String(6))
    expires_at = db.Column(db.DateTime)
    verified = db.Column(db.Boolean, default=False)

class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(50), nullable=False)
    role = db.Column(db.String(20), default="patient") # patient, clinician, admin
    type = db.Column(db.String(50), nullable=False)
    message = db.Column(db.Text, nullable=False)
    related_appointment_id = db.Column(db.Integer, nullable=True)
    report_severity = db.Column(db.Integer, nullable=True)
    clinician_label = db.Column(
        Enum(ClinicianLabel, name="clinician_label_enum"),
        nullable=True
    )
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp())

    def __init__(self, **kwargs):
        super(Notification, self).__init__(**kwargs)

class PatientNotificationSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.String(50), nullable=False, unique=True)
    oral_hygiene = db.Column(db.Boolean, default=True)
    appliance_care = db.Column(db.Boolean, default=True)
    appointment = db.Column(db.Boolean, default=True)

# ---------------------------
# CHAT MESSAGE MODEL
# ---------------------------
class ChatMessage(db.Model):
    __tablename__ = 'patient_chat_history'
    
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.String(50), nullable=False)
    message = db.Column(db.Text, nullable=False)
    sender = db.Column(db.Enum('patient', 'bot', name='sender_enum'), nullable=False)
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp())

    def __init__(self, **kwargs):
        super(ChatMessage, self).__init__(**kwargs)

# ---------------------------
# SYSTEM SETTINGS MODEL
# ---------------------------

class AppSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    clinic_phone = db.Column(db.String(20), default="+91 7299053348")
    support_email = db.Column(db.String(100), default="prime@saveetha.com")
    admin_phone = db.Column(db.String(20), default="8939994248")
    admin_email = db.Column(db.String(100), default="admin@saveetha.com")
    system_support_email = db.Column(db.String(100), default="support-admin@orthoguide.com")
    system_support_phone = db.Column(db.String(20), default="+91 98765 43210")
    system_version = db.Column(db.String(20), default="1.0.0")
    clinic_name = db.Column(db.String(100), default="Saveetha Dental College & Hospital")
    
    # Feature Toggles
    enable_public_registration = db.Column(db.Boolean, default=False)
    ai_diagnostic_assistant = db.Column(db.Boolean, default=True)
    sms_reminders = db.Column(db.Boolean, default=True)
    maintenance_mode = db.Column(db.Boolean, default=False)

from sqlalchemy.dialects.mysql import LONGTEXT

class ReactivationRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.String(50), nullable=False)
    patient_name = db.Column(db.String(100), nullable=False)
    user_role = db.Column(db.String(20), nullable=False, default="patient") # patient, clinician
    contact_info = db.Column(db.String(100), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default="Pending") # Pending, Approved, Rejected
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))


class IssueReport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.String(50))
    issue_type = db.Column(db.String(100))
    description = db.Column(db.Text)
    photo_url = db.Column(LONGTEXT, nullable=True)
    severity = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(50), default="Pending")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

with app.app_context():
    db.create_all()

    if not AppSettings.query.first():
        settings = AppSettings()
        db.session.add(settings)
        db.session.commit()

# ---------------------------
# DAILY REMINDER FUNCTION
# ---------------------------

def send_daily_reminders(reminder_type, time_slot="Morning"):
    """
    reminder_type: 'oral_hygiene' or 'appliance_care'
    time_slot: 'Morning', 'Afternoon', 'Evening', 'Night'
    """
    with app.app_context():
        patients = Patient.query.filter_by(is_active=True).all()

        for patient in patients:
            settings = PatientNotificationSettings.query.filter_by(patient_id=patient.patient_id).first()
            if not settings:
                settings = PatientNotificationSettings(patient_id=patient.patient_id)
                db.session.add(settings)
                db.session.commit()

            message = ""
            if reminder_type == NotificationType.ORAL_HYGIENE.value and settings.oral_hygiene:
                if time_slot == "Morning":
                    message = "Time to brush and floss your teeth."
                elif time_slot == "Night":
                    message = "Night oral care reminder: brush and floss before sleeping."
            
            elif reminder_type == NotificationType.APPLIANCE_CARE.value and settings.appliance_care:
                if time_slot == "Afternoon":
                    message = "Clean your appliance or aligners to maintain hygiene."
                elif time_slot == "Night":
                    message = "Evening appliance care reminder: clean and store properly."

            if message:
                # Duplicate protection for daily reminders: check last 6 hours
                six_hours_ago = datetime.now(UTC) - timedelta(hours=6)
                exists = Notification.query.filter(
                    Notification.user_id == patient.patient_id,
                    Notification.type == reminder_type,
                    Notification.message == message,
                    Notification.created_at >= six_hours_ago
                ).first()

                if not exists:
                    notif = Notification(
                        user_id=patient.patient_id,
                        role="patient",
                        type=reminder_type,
                        message=message
                    )
                    db.session.add(notif)

        try:
            db.session.commit()
            logging.info(f"Daily reminders ({reminder_type} - {time_slot}) sent!")
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error committing daily reminders: {e}")

def send_appointment_notification(patient_id, appointment_id, action):
    """
    action: 'scheduled', 'rescheduled', 'cancelled'
    """
    with app.app_context():
        settings = PatientNotificationSettings.query.filter_by(patient_id=patient_id).first()
        if settings and not settings.appointment:
            return

        appt = Appointment.query.get(appointment_id)
        if not appt: return

        date_str = appt.appointment_date.strftime("%Y-%m-%d")
        time_str = appt.appointment_time or "TBD"
        
        message = ""
        if action == "scheduled":
            message = f"A new appointment has been scheduled for {date_str} at {time_str}."
        elif action == "rescheduled":
            message = f"Your appointment on {date_str} has been rescheduled to {time_str}."
        elif action == "cancelled":
            message = f"Your appointment on {date_str} has been cancelled."
        elif action == "completed":
            message = f"Your appointment on {date_str} at {time_str} has been marked as completed."

        # Duplicate protection: check if same notification sent in last 1 minute
        one_min_ago = datetime.now(UTC) - timedelta(minutes=1)
        exists = Notification.query.filter(
            Notification.user_id == patient_id,
            Notification.type == NotificationType.APPOINTMENT.value,
            Notification.message == message,
            Notification.created_at >= one_min_ago
        ).first()

        if not exists:
            notif = Notification(
                user_id=patient_id,
                role="patient",
                type=NotificationType.APPOINTMENT.value,
                message=message,
                related_appointment_id=appointment_id
            )
            db.session.add(notif)
            try:
                db.session.commit()
                logging.info(f"Appointment notification ({action}) sent to {patient_id}")
            except Exception as e:
                db.session.rollback()
                logging.error(f"Error sending appointment notification: {e}")
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
        "admin_phone": settings.admin_phone,
        "support_email": settings.system_support_email,
        "app_version": settings.system_version
    })

# ---------------------------
# HELPER FUNCTION
# ---------------------------

def get_next_appointment(patient_id):
    today = datetime.now().date()

    appointment = Appointment.query.filter(
        Appointment.patient_id == patient_id,
        Appointment.appointment_date >= today,
        func.lower(func.trim(Appointment.status)) != 'cancelled',
        func.lower(func.trim(Appointment.status)) != 'completed',
        func.lower(func.trim(Appointment.status)) != 'missed'
    ).order_by(Appointment.appointment_date.asc(), Appointment.appointment_time.asc()).first()

    if appointment:
        time = appointment.appointment_time if appointment.appointment_time else "NA"

        clinician = Clinician.query.filter_by(clinician_id=appointment.clinician_id).first()
        clinician_name = clinician.name if clinician else None

        return {
            "id": appointment.id,
            "date": str(appointment.appointment_date),
            "time": time,
            "type": appointment.appointment_type,
            "clinician_name": clinician_name,
            "notes": appointment.notes
        }

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
                "name": admin.name,
                "email": admin.email,
                "phone_number": admin.phone_number
            })

        return jsonify({"error": "Invalid admin credentials"}), 401


    elif role == "clinician":

        clinician = Clinician.query.filter_by(clinician_id=user_id).first()

        if not clinician:
            return jsonify({"error": "Clinician not found"}), 404

        if not bcrypt.check_password_hash(clinician.password, password):
            return jsonify({"error": "Invalid password"}), 401

        if clinician.is_active == False:
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

        if patient.is_active == False:
            return jsonify({"error": "Patient inactive"}), 403

        consent = PatientConsent.query.filter_by(patient_id=patient.patient_id).first()

        return jsonify({
            "role": "patient",
            "user_id": patient.patient_id,
            "name": patient.name,
            "consent_given": consent.consent_given if consent else False
        })

    return jsonify({"error": "Invalid role"}), 400

def is_strong_password(password):
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not any(char.isupper() for char in password):
        return False, "Password must contain at least one capital letter"
    if not any(char.isdigit() for char in password):
        return False, "Password must contain at least one number"
    if not any(not char.isalnum() for char in password):
        return False, "Password must contain at least one special character"
    return True, ""

# ---------------------------
# CHANGE PASSWORD
# ---------------------------

@app.route("/change_password", methods=["POST"])
def change_password():
    data = request.get_json()
    user_id = data.get("user_id")
    role = data.get("role")
    old_pw = data.get("old_password")
    new_pw = data.get("new_password")

    if not all([user_id, role, old_pw, new_pw]):
        return jsonify({"error": "Missing required fields"}), 400

    is_valid, error_msg = is_strong_password(new_pw)
    if not is_valid:
        return jsonify({"error": error_msg}), 400

    user = None
    if role == "admin":
        user = Admin.query.filter_by(admin_id=user_id).first()
    elif role == "clinician":
        user = Clinician.query.filter_by(clinician_id=user_id).first()
    elif role == "patient":
        user = Patient.query.filter_by(patient_id=user_id).first()

    if not user:
        return jsonify({"error": "User not found"}), 404

    if not bcrypt.check_password_hash(user.password, old_pw):
        return jsonify({"error": "Current password is incorrect"}), 401

    user.password = bcrypt.generate_password_hash(new_pw).decode('utf-8')
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    return jsonify({"message": "Password updated successfully"})

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

    if patient.is_active == False:
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

    if clinician.is_active == False:
        return jsonify({"message": "Clinician account inactive"}), 403

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
        "phone_number": clinician.phone_number,
        "clinic_address": clinician.clinic_address,
        "license_number": clinician.license_number,
        "specialization": clinician.specialization,
        "created_at": clinician.created_at.strftime("%B %d, %Y") if clinician.created_at else "N/A",
        "is_active": clinician.is_active
    })

@app.route("/patient/dashboard/<patient_id>", methods=["GET"])
def get_patient_dashboard_data(patient_id):
    try:
        patient = Patient.query.filter_by(patient_id=patient_id).first()
        if not patient:
            return jsonify({"error": "Patient not found"}), 404
        
        # Use global PATIENT_STAGES
        stages = PATIENT_STAGES
        
        # Next appointment
        appointment = get_next_appointment(patient_id)
        
        # Doctor name - Clinician who scheduled the appointment
        doctor_name = "Your Doctor"
        
        # Get latest scheduled or most recent appointment clinician
        logging.info(f"Fetching latest active appointment for patient {patient_id}...")
        latest_appt = Appointment.query.filter(
            Appointment.patient_id == patient_id,
            func.lower(func.trim(Appointment.status)) != 'cancelled'
        ).order_by(Appointment.appointment_date.desc()).first()
        logging.info(f"Latest appointment found for dashboard: {latest_appt.id if latest_appt else 'None'}")
        
        if latest_appt:
            clinician = Clinician.query.filter_by(clinician_id=latest_appt.clinician_id).first()
            if clinician:
                doctor_name = clinician.name
        elif patient.created_by_clinician:
            clinician = Clinician.query.filter_by(clinician_id=patient.created_by_clinician).first()
            if clinician:
                doctor_name = clinician.name

        # Calculate Progress
        current_stage_idx = 0
        try:
            # Robust matching: strip spaces and case-insensitive
            clean_patient_stage = (patient.treatment_stage or "").strip().lower()
            current_stage_idx = next(i for i, s in enumerate(stages) if s.strip().lower() == clean_patient_stage)
            current_index = current_stage_idx
        except (ValueError, StopIteration, AttributeError):
            current_stage_idx = 0
            current_index = 0
            
        progress = int(((current_index + 1) / len(stages)) * 100)
        
        # Timeline
        timeline = []
        for i, stage in enumerate(stages):
            status = "Upcoming"
            active = False
            if i < current_index:
                status = "Completed"
            elif i == current_index:
                status = "In Progress"
                active = True
            
            timeline.append({
                "phase": stage,
                "status": status,
                "active": active
            })

        # Generate daily tip based on treatment stage
        daily_tips = {
            "Initial Consultation": "Start your treatment journey! Remember to clean your teeth before putting on aligners.",
            "Bonding / First Trays": "Your braces/aligners are on! Avoid sticky foods and keep your hygiene game strong.",
            "Alignment Phase": "You're making progress! Teeth are starting to move into their ideal positions.",
            "Bite Correction": "Great work! We are now focused on making sure your upper and lower teeth meet perfectly.",
            "Finishing & Detailing": "Almost there! We are making the final micro-adjustments for your perfect smile.",
            "Debonding & Retention": "Treatment complete! Wear your retainers as directed to maintain your results."
        }
        daily_tip = daily_tips.get(patient.treatment_stage, "Keep wearing your aligners consistently for the best treatment outcome!")

        return jsonify({
            "name": patient.name,
            "treatment_phase": patient.treatment_stage,
            "treatment_stage": patient.treatment_stage,
            "current_stage_display": patient.treatment_stage,
            "current_stage_number": current_index + 1,
            "total_stages": len(stages),
            "current_tray": patient.current_tray,
            "total_trays": patient.total_trays,
            "compliance": f"{patient.compliance_rate}%",
            "progress_percent": progress,
            "next_appointment": appointment,
            "doctor_name": doctor_name,
            "timeline": timeline,
            "daily_tip": daily_tip
        })
    except Exception as e:
        logging.error(f"Error in get_patient_dashboard_data for {patient_id}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/patient/profile/<patient_id>", methods=["GET"])
def get_patient_profile_data(patient_id):
    try:
        patient = Patient.query.filter_by(patient_id=patient_id).first()
        if not patient:
            return jsonify({"error": "Patient not found"}), 404
        
        # Get doctor name and clinic info - Clinician who scheduled the appointment
        doctor_name = "Not Assigned"
        clinic_address = "No office address found"
        
        # Get latest scheduled or most recent appointment clinician
        logging.info(f"Fetching latest active appointment for profile of patient {patient_id}...")
        latest_appt = Appointment.query.filter(
            Appointment.patient_id == patient_id,
            func.lower(func.trim(Appointment.status)) != 'cancelled'
        ).order_by(Appointment.appointment_date.desc()).first()
        logging.info(f"Latest appointment found for profile: {latest_appt.id if latest_appt else 'None'}")
        
        if latest_appt:
            clinician = Clinician.query.filter_by(clinician_id=latest_appt.clinician_id).first()
            if clinician:
                doctor_name = clinician.name
                clinic_address = clinician.clinic_address or clinic_address
        elif patient.created_by_clinician:
            clinician = Clinician.query.filter_by(clinician_id=patient.created_by_clinician).first()
            if clinician:
                doctor_name = clinician.name
                clinic_address = clinician.clinic_address or clinic_address

        return jsonify({
            "patient_id": patient.patient_id,
            "name": patient.name,
            "email": patient.email,
            "phone": patient.phone_number,
            "address": patient.address,
            "status": patient.status,
            "treatment_stage": patient.treatment_stage,
            "is_active": patient.is_active,
            "current_tray": patient.current_tray,
            "total_trays": patient.total_trays,
            "compliance_rate": patient.compliance_rate,
            "compliance": str(patient.compliance_rate),
            "start_date": patient.start_date.strftime("%B %d, %Y") if patient.start_date else "N/A",
            "doctor_name": doctor_name,
            "clinic_address": clinic_address,
            "notes": patient.notes
        })
    except Exception as e:
        logging.error(f"Error in get_patient_profile_data for {patient_id}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/admin/profile/<admin_id>", methods=["GET"])
def get_admin_profile_data(admin_id):
    admin = Admin.query.filter_by(admin_id=admin_id).first()
    if not admin:
        return jsonify({"error": "Admin not found"}), 404

    return jsonify({
        "admin_id": admin.admin_id,
        "name": admin.name,
        "email": admin.email,
        "phone_number": admin.phone_number,
        "created_at": admin.created_at.strftime("%B %d, %Y") if admin.created_at else "N/A"
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
    new_clinic_address = data.get("clinic_address")
    new_license_number = data.get("license_number")
    new_specialization = data.get("specialization")

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

    if new_clinic_address:
        clinician.clinic_address = new_clinic_address

    if new_license_number:
        clinician.license_number = new_license_number

    if new_specialization:
        clinician.specialization = new_specialization

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

    is_valid, error_msg = is_strong_password(data.get("new_password"))
    if not is_valid:
        return jsonify({"error": error_msg}), 400

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

    is_valid, error_msg = is_strong_password(data.get("new_password"))
    if not is_valid:
        return jsonify({"error": error_msg}), 400

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
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
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
    send_email_otp(email, otp, user_id=patient.patient_id, name=patient.name, role="Patient")
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
            PasswordResetOTP.expires_at < datetime.now(UTC)
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

    if record.expires_at < datetime.now(UTC):
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
# PUBLIC STATS
# ---------------------------

@app.route("/public/stats")
def public_stats():
    try:
        total_patients = Patient.query.count()
        total_clinicians = Clinician.query.count()
        return jsonify({
            "total_patients": f"{total_patients}+" if total_patients > 0 else "0",
            "total_clinicians": f"{total_clinicians}+" if total_clinicians > 0 else "0",
            "satisfaction_rate": "99%",
            "support_available": "24/7"
        })
    except Exception as e:
        logging.error(f"Error fetching public stats: {e}")
        return jsonify({
            "total_patients": "10,000+",
            "total_clinicians": "500+",
            "satisfaction_rate": "99%",
            "support_available": "24/7"
        })

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

    phone = data.get("phone_number", "")
    default_pw = f"ortho@{phone[-4:]}" if len(phone) >= 4 else (phone if phone else "123456")
    hashed_pw = bcrypt.generate_password_hash(default_pw).decode("utf-8")

    clinician = Clinician(
        clinician_id=data.get("clinician_id"),
        name=data.get("name"),
        role=data.get("role"),
        email=data.get("email"),
        phone_number=data.get("phone_number"),
        password=hashed_pw,
        is_active=True
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

    phone = clinician.phone_number or ""
    default_pw = f"ortho@{phone[-4:]}" if len(phone) >= 4 else (phone if phone else "123456")
    new_pw = bcrypt.generate_password_hash(default_pw).decode("utf-8")

    clinician.password = new_pw

    db.session.commit()

    return jsonify({"message": f"Password reset successfully to '{default_pw}'"})


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

    phone = patient.phone_number or ""
    default_pw = f"ortho@{phone[-4:]}" if len(phone) >= 4 else (phone if phone else "123456")
    new_pw = bcrypt.generate_password_hash(default_pw).decode("utf-8")

    patient.password = new_pw

    db.session.commit()

    return jsonify({"message": f"Password reset successfully to '{default_pw}'"})

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

    phone = data.get("phone_number", "")
    default_pw = f"ortho@{phone[-4:]}" if len(phone) >= 4 else (phone if phone else "123456")
    hashed_pw = bcrypt.generate_password_hash(default_pw).decode("utf-8")

    patient = Patient(
        patient_id=data.get("patient_id"),
        name=data.get("name"),
        email=data.get("email"),
        phone_number=data.get("phone_number"),
        password=hashed_pw,
        created_by_clinician=data.get("clinician_id"),
        is_active=True
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

    # Robust matching: strip spaces and case-insensitive
    clean_stage = data.get("stage", "").strip().lower()
    stage = patient.treatment_stage
    if clean_stage:
        try:
            stage = next(s for s in valid_stages if s.strip().lower() == clean_stage)
        except StopIteration:
            return jsonify({"error": f"Invalid stage: {data.get('stage')}"}), 400

    status = data.get("status", patient.status).strip().lower()
    if status not in valid_status:
        return jsonify({"error": f"Invalid status: {status}"}), 400

    # Only notify if stage or status actualy changed
    is_changed = (stage != patient.treatment_stage) or (status != patient.status)

    patient.treatment_stage = stage
    patient.status = status
    patient.notes = data.get("notes", patient.notes)

    history = TreatmentHistory(
        patient_id=patient.patient_id,
        stage=stage,
        status=status,
        updated_by=data.get("clinician_id"),
        notes=data.get("notes", "")
    )
    db.session.add(history)

    if is_changed:
        # Create a notification for the patient
        notif_msg = f"Your treatment has been updated to '{stage}' and your status is now '{status}'."
        notification = Notification(
            user_id=patient.patient_id,
            role="patient",
            type="report_issue",
            message=notif_msg
        )
        db.session.add(notification)

    try:
        db.session.commit()
        # After successful commit, send email notification IF CHANGE OCCURRED
        if is_changed and patient.email:
            clinician = Clinician.query.filter_by(clinician_id=data.get("clinician_id")).first()
            doctor_name = clinician.name if clinician else "Your Orthodontist"
            
            send_patient_update_notification(
                to_email=patient.email,
                name=patient.name,
                stage=stage,
                status=status,
                doctor_name=doctor_name
            )
    except Exception as e:
        db.session.rollback()
        print(f"Error updating patient {patient.patient_id}: {e}")
        return jsonify({"error": "Failed to update patient"}), 500

    return jsonify({"message": "Patient updated and notified"})

# ---------------------------
# CLINICIAN DEACTIVATE PATIENT
# ---------------------------
@app.route("/clinician/patient/deactivate", methods=["POST"])
def clinician_deactivate_patient():
    data = request.get_json()
    patient = Patient.query.filter_by(patient_id=data.get("patient_id")).first()
    
    if not patient:
        return jsonify({"error": "Patient not found"}), 404
    
    patient.is_active = False
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to deactivate patient"}), 500
    
    return jsonify({"message": "Patient deactivated successfully"})


# ---------------------------
# SELF DEACTIVATE ACCOUNT
# ---------------------------
@app.route("/account/deactivate", methods=["POST"])
def self_deactivate_account():
    data = request.get_json()
    user_id = data.get("user_id")
    role = data.get("role")

    if role == "patient":
        user = Patient.query.filter_by(patient_id=user_id).first()
    elif role == "clinician":
        user = Clinician.query.filter_by(clinician_id=user_id).first()
    else:
        return jsonify({"error": "Invalid role"}), 400

    if not user:
        return jsonify({"error": "User not found"}), 404

    user.is_active = False

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to deactivate account"}), 500

    return jsonify({"message": "Account deactivated successfully"})


# ---------------------------
# SELF REACTIVATE ACCOUNT
# ---------------------------
@app.route("/account/reactivate", methods=["POST"])
def self_reactivate_account():
    data = request.get_json()
    user_id = data.get("user_id")
    role = data.get("role")

    if role == "patient":
        user = Patient.query.filter_by(patient_id=user_id).first()
    elif role == "clinician":
        user = Clinician.query.filter_by(clinician_id=user_id).first()
    else:
        return jsonify({"error": "Invalid role"}), 400

    if not user:
        return jsonify({"error": "User not found"}), 404

    user.is_active = True

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to reactivate account"}), 500

    return jsonify({"message": "Account reactivated successfully"})


# ---------------------------
# CLINICIAN SEND MESSAGE TO PATIENT
# ---------------------------
@app.route("/clinician/patient/send_message", methods=["POST"])
def clinician_send_message():
    data = request.get_json()
    patient = Patient.query.filter_by(patient_id=data.get("patient_id")).first()
    
    if not patient:
        return jsonify({"error": "Patient not found"}), 404
    
    # Create a notification for the patient using Notification model
    notification = Notification(
        user_id=patient.patient_id,
        role="patient",
        message=data.get("message", "You have a new message from your clinician."),
        type=NotificationType.APPOINTMENT.value
    )
    
    try:
        db.session.add(notification)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error sending message: {e}")
        return jsonify({"error": "Failed to send message"}), 500
    
    return jsonify({"message": "Message sent successfully"})

# ---------------------------
# SCHEDULE APPOINTMENT (Consolidated to /clinician/schedule/add)
# ---------------------------



@app.route("/appointment/delete/<int:appointment_id>", methods=["DELETE"])
def delete_appointment(appointment_id):
    try:
        logging.info(f"Cancellation request for appointment ID: {appointment_id}")
        appointment = Appointment.query.get(appointment_id)

        if not appointment:
            logging.warning(f"Appointment {appointment_id} not found for cancellation")
            return jsonify({"error": "Appointment not found"}), 404

        patient_id = appointment.patient_id
        
        # Consistent status check
        if func.lower(func.trim(appointment.status or "")) == 'cancelled':
            return jsonify({"message": "Appointment already cancelled"}), 200

        # Attempt notification, but don't crash if it fails
        try:
            send_appointment_notification(patient_id, appointment_id, "cancelled")
        except Exception as e:
            logging.error(f"Notification failure (non-blocking): {e}")
        
        # Mark as cancelled
        appointment.status = "cancelled"
        db.session.commit()

        logging.info(f"Successfully cancelled appointment {appointment_id} for patient {patient_id}")
        return jsonify({"message": "Appointment cancelled successfully"})
        
    except Exception as e:
        import traceback
        logging.error(f"CRITICAL ERROR in delete_appointment: {str(e)}")
        logging.error(traceback.format_exc())
        db.session.rollback()
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500

@app.route("/appointment/complete/<int:appointment_id>", methods=["POST"])
def complete_appointment(appointment_id):
    try:
        logging.info(f"Completion request for appointment ID: {appointment_id}")
        appointment = Appointment.query.get(appointment_id)

        if not appointment:
            logging.warning(f"Appointment {appointment_id} not found for completion")
            return jsonify({"error": "Appointment not found"}), 404

        patient_id = appointment.patient_id
        
        # Consistent status check
        if func.lower(func.trim(appointment.status or "")) == 'completed':
            return jsonify({"message": "Appointment already marked as completed"}), 200

        # Attempt notification, but don't crash if it fails
        try:
            send_appointment_notification(patient_id, appointment_id, "completed")
        except Exception as e:
            logging.error(f"Notification failure (non-blocking): {e}")
        
        # Mark as completed
        appointment.status = "completed"
        
        # Automatically update patient status to "on track"
        patient = Patient.query.filter_by(patient_id=patient_id).first()
        if patient:
            patient.status = "on track"
            logging.info(f"Automatically updated patient {patient_id} status to 'on track'")
        
        db.session.commit()

        logging.info(f"Successfully marked appointment {appointment_id} complete for patient {patient_id}")
        return jsonify({"message": "Appointment marked as completed successfully"})
        
    except Exception as e:
        import traceback
        logging.error(f"CRITICAL ERROR in complete_appointment: {str(e)}")
        logging.error(traceback.format_exc())
        db.session.rollback()
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500

@app.route("/appointment/reschedule", methods=["PUT"])
def reschedule_appointment():
    try:
        data = request.get_json()
        appointment_id = data.get("appointment_id")
        try:
            appointment_id = int(appointment_id)
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid appointment ID"}), 400

        appointment = Appointment.query.filter_by(id=appointment_id).first()

        if not appointment:
            return jsonify({"error": "Session record not found"}), 404

        # Safety Check: Don't reschedule if already cancelled
        if appointment.status == 'cancelled':
            return jsonify({"error": "Cannot reschedule an already cancelled session", "already_cancelled": True}), 200

        new_date_str = data.get("date")
        new_time = data.get("time")
        
        try:
            # Check if new_time is in 'HH:MM AM/PM' format or 'HH:MM'
            try:
                full_dt = datetime.strptime(f"{new_date_str} {new_time}", "%Y-%m-%d %I:%M %p")
            except ValueError:
                full_dt = datetime.strptime(f"{new_date_str} {new_time}", "%Y-%m-%d %H:%M")
            
            # Use Asia/Kolkata for consistency with scheduler
            tz = pytz.timezone('Asia/Kolkata')
            local_now = datetime.now(tz)
            localized_dt = tz.localize(full_dt)
            
            # Allow 'now' by subtracting a 1-minute grace period
            if localized_dt < local_now - timedelta(minutes=1):
                return jsonify({"error": "Cannot reschedule to a time in the past"}), 400
                
            new_date = full_dt.date()
        except ValueError:
            return jsonify({"error": "Invalid date or time format"}), 400

        # BUG FIX: Only add 'Rescheduled from' if the date actually changed. 
        # Don't clutter notes for just a time change or notes edit.
        is_date_changed = str(appointment.appointment_date) != str(new_date)
        base_notes = data.get("notes", "").strip() or appointment.notes or ""
        
        # Check if an active appointment already exists on the new target date
        existing_app = Appointment.query.filter(
            func.lower(func.trim(Appointment.patient_id)) == str(appointment.patient_id or "").lower().strip(),
            Appointment.appointment_date == new_date,
            func.lower(func.trim(Appointment.status)) != 'cancelled'
        ).filter(Appointment.id != appointment.id).first()
        
        if existing_app:
            logging.info(f"Found existing active appointment {existing_app.id} on {new_date_str}. Merging.")
            existing_app.appointment_time = new_time
            existing_app.status = "rescheduled"
            
            # Only prepend merge note if date changed
            if is_date_changed:
                existing_app.notes = f"Merged from rescheduled appointment {appointment.id}. Original notes: {base_notes}"
            else:
                existing_app.notes = base_notes
                
            appointment.status = "cancelled"
            
            db.session.commit()
            return jsonify({
                "message": "Appointment merged with existing one on the same day", 
                "rescheduled": True,
                "appointment_id": existing_app.id
            })

        # Only mark as 'rescheduled' if the date or time actually changed.
        # This prevents accidental purple labeling during initial confirm button clicks.
        has_changed = str(appointment.appointment_date) != str(new_date) or str(appointment.appointment_time) != str(new_time)
        
        appointment.appointment_date = new_date
        appointment.appointment_time = new_time
        
        if has_changed:
            appointment.status = "rescheduled"
            # Consistent note for history if date changed
            if is_date_changed:
                appointment.notes = f"Rescheduled from {appointment.appointment_date}. {base_notes}"
        
        db.session.commit()
        
        try:
            send_appointment_notification(appointment.patient_id, appointment.id, "rescheduled")
        except Exception as e:
            logging.error(f"Reschedule notification failure (non-blocking): {e}")

        return jsonify({
            "message": "Appointment rescheduled successfully", 
            "rescheduled": True,
            "appointment_id": appointment.id
        })
        
    except Exception as e:
        import traceback
        logging.error(f"CRITICAL ERROR in reschedule_appointment: {str(e)}")
        logging.error(traceback.format_exc())
        db.session.rollback()
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500


# ---------------------------
# CLINICIAN DASHBOARD
# ---------------------------



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

    # Get latest issue report
    latest_issue = IssueReport.query.filter_by(patient_id=patient_id).order_by(IssueReport.id.desc()).first()
    latest_issue_data = None
    if latest_issue:
        latest_issue_data = {
            "type": latest_issue.issue_type,
            "description": latest_issue.description,
            "photo_url": latest_issue.photo_url,
            "created_at": latest_issue.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }

    return jsonify({
        "patient_id": patient.patient_id,
        "name": patient.name,
        "treatment_stage": patient.treatment_stage,
        "status": patient.status,
        "latest_note": latest_note,
        "notes": patient.notes,
        "next_appointment": next_appointment,
        "reports": [
            {
                "id": r.id,
                "issue_type": r.issue_type,
                "description": r.description,
                "photo_url": r.photo_url,
                "severity": r.severity,
                "created_at": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "N/A"
            } for r in IssueReport.query.filter_by(patient_id=patient_id).order_by(IssueReport.created_at.desc()).all()
        ],
        "latest_issue": latest_issue_data
    })

# (Dashboard consolidated above)


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

    today = datetime.now().date()

    upcoming = Appointment.query.filter(
        Appointment.patient_id == patient_id,
        Appointment.appointment_date >= today,
        func.lower(func.trim(Appointment.status)).in_(['scheduled', 'rescheduled', 'confirmed'])
    ).order_by(Appointment.appointment_date.asc(), Appointment.appointment_time.asc()).all()

    past = Appointment.query.filter(
        Appointment.patient_id == patient_id,
        or_(
            Appointment.appointment_date < today,
            func.lower(func.trim(Appointment.status)).in_(['cancelled', 'completed', 'missed'])
        )
    ).order_by(Appointment.appointment_date.desc()).all()

    all_appointments = []

    for a in upcoming:
        time = a.appointment_time if a.appointment_time else "NA"
        clinician = Clinician.query.filter_by(clinician_id=a.clinician_id).first()
        clinician_name = clinician.name if clinician else None

        all_appointments.append({
            "id": a.id,
            "appointment_date": str(a.appointment_date),
            "appointment_time": time,
            "appointment_type": a.appointment_type,
            "status": a.status,
            "clinician_name": clinician_name
        })

    for a in past:
        clinician = Clinician.query.filter_by(clinician_id=a.clinician_id).first()
        clinician_name = clinician.name if clinician else None   

        all_appointments.append({
            "id": a.id,
            "appointment_date": str(a.appointment_date),
            "appointment_time": a.appointment_time if a.appointment_time else "NA",
            "appointment_type": a.appointment_type,
            "status": a.status.lower().strip() if a.status else "completed",
            "clinician_name": clinician_name
        })

    return jsonify(all_appointments)

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
            patient.updated_at = datetime.now(UTC)

    notif = Notification(
        user_id=patient_id,
        role="patient",
        type=type_ if isinstance(type_, str) else type_.value,
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


@app.route("/patient/notifications/<user_id>")
def get_notifications(user_id):
    role = request.args.get("role", "patient") # Default to patient for backward compatibility
    filters = request.args.getlist("type")
    
    query = Notification.query.filter_by(user_id=user_id, role=role)

    if filters:
         valid_filters = [f for f in filters] # Allow all strings for now since we use different types across roles
         query = query.filter(Notification.type.in_(valid_filters))

    notifications = query.order_by(Notification.created_at.desc()).all()

    result = []
    for n in notifications:
        # Handle both Enum and String for 'type'
        type_val = n.type.value if hasattr(n.type, 'value') else n.type
        
        result.append({
            "id": n.id,
            "type": type_val,
            "message": n.message,
            "appointment_id": n.related_appointment_id,
            "report_severity": n.report_severity,
            "clinician_label": n.clinician_label.value if n.clinician_label and hasattr(n.clinician_label, 'value') else n.clinician_label,
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
            "appointment": True,
            "session": True
        })

    return jsonify({
        "patient_id": patient_id,
        "oral_hygiene": settings.oral_hygiene,
        "appliance_care": settings.appliance_care,
        "appointment": settings.appointment,
        "session": settings.appointment
    })


@app.route("/patient/notification/settings", methods=["POST"])
def update_notification_settings():
    data = request.get_json()
    patient_id = data.get("patient_id")

    settings = PatientNotificationSettings.query.filter_by(patient_id=patient_id).first()
    if not settings:
        settings = PatientNotificationSettings(patient_id=patient_id)
        db.session.add(settings)

    # Recognize both 'session' (legacy/duplicate) and 'appointment' (new/standard)
    for field in ["oral_hygiene", "appliance_care", "session", "appointment"]:
        if field in data:
            db_field = "appointment" if field in ["session", "appointment"] else field
            setattr(settings, db_field, bool(data[field]))

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error updating notification settings for patient {patient_id}: {e}")
        return jsonify({"error": "Failed to update settings"}), 500

    logging.info(f"Notification settings updated for patient {patient_id}: { {field: getattr(settings, field) for field in ['oral_hygiene','appliance_care','appointment']} }")
    return jsonify({"message": "Settings updated successfully"})


@app.route("/notification/read/<int:notif_id>", methods=["POST"])
def mark_notification_read(notif_id):
    notif = Notification.query.get(notif_id)
    if not notif:
        return jsonify({"error": "Notification not found"}), 404

    notif.is_read = True

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error marking notification {notif_id} as read: {e}")
        return jsonify({"error": "Failed to mark notification"}), 500
    
    logging.info(f"Notification {notif_id} marked as read for user {notif.user_id}")
    return jsonify({"message": "Notification marked as read"})

@app.route("/admin/reactivation/read/<int:request_id>", methods=["POST"])
def mark_reactivation_request_read(request_id):
    req = ReactivationRequest.query.get(request_id)
    if not req:
        return jsonify({"error": "Reactivation request not found"}), 404

    req.is_read = True

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error marking reactivation request {request_id} as read: {e}")
        return jsonify({"error": "Failed to mark reactivation request"}), 500
    
    logging.info(f"Reactivation request {request_id} marked as read by admin")
    return jsonify({"message": "Reactivation request marked as read"})

@app.route("/notification/read_all", methods=["POST"])
def mark_all_notifications_read():
    data = request.get_json()
    user_id = data.get("user_id")
    role = data.get("role", "patient")

    if not user_id:
        return jsonify({"error": "User ID required"}), 400

    if role == "admin":
        # For admin, notifications are ReactivationRequests
        unread_notifs = ReactivationRequest.query.filter_by(is_read=False).all()
        for notif in unread_notifs:
            notif.is_read = True
    else:
        # Standard user notifications
        unread_notifs = Notification.query.filter_by(user_id=user_id, role=role, is_read=False).all()
        for notif in unread_notifs:
            notif.is_read = True

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error marking all notifications read for {user_id}: {e}")
        return jsonify({"error": "Failed to mark all read"}), 500

    return jsonify({"message": "All notifications marked as read"})

@app.route("/notifications/unread_count/<user_id>/<role>")
def get_unread_count(user_id, role):
    try:
        user_id_clean = str(user_id or "").strip()
        if role == "admin":
            # For admin, unread count comes from ReactivationRequests
            count = ReactivationRequest.query.filter_by(is_read=False).count()
        else:
            count = Notification.query.filter_by(
                user_id=user_id_clean, 
                role=role, 
                is_read=False
            ).count()
        return jsonify({
            "count": count,
            "unread_count": count
        })
    except Exception as e:
        import traceback
        logging.error(f"CRITICAL ERROR in get_unread_count: {str(e)}")
        logging.error(traceback.format_exc())
        return jsonify({"error": "Internal server error"}), 500
# ---------------------------
# SCHEDULER SETUP
# ---------------------------

# Use the global 'scheduler' instance defined at the top

# 1. Oral Hygiene - Morning (7:30 AM)
scheduler.add_job(
    id='oral_hygiene_morning',
    func=send_daily_reminders,
    args=['oral_hygiene', 'Morning'],
    trigger='cron',
    hour=7,
    minute=30,
    timezone=timezone('Asia/Kolkata')
)

# 2. Oral Hygiene - Night (9:30 PM)
scheduler.add_job(
    id='oral_hygiene_night',
    func=send_daily_reminders,
    args=['oral_hygiene', 'Night'],
    trigger='cron',
    hour=21,
    minute=30,
    timezone=timezone('Asia/Kolkata')
)

# 3. Appliance Care - Afternoon (2:00 PM)
scheduler.add_job(
    id='appliance_care_afternoon',
    func=send_daily_reminders,
    args=['appliance_care', 'Afternoon'],
    trigger='cron',
    hour=14,
    minute=0,
    timezone=timezone('Asia/Kolkata')
)

# 4. Appliance Care - Night (9:00 PM)
scheduler.add_job(
    id='appliance_care_night',
    func=send_daily_reminders,
    args=['appliance_care', 'Night'],
    trigger='cron',
    hour=21,
    minute=0,
    timezone=timezone('Asia/Kolkata')
)

# Optional: OTP cleanup at midnight IST
def cleanup_expired_otps():
    with app.app_context():
        try:
            PasswordResetOTP.query.filter(
                (PasswordResetOTP.expires_at < datetime.now(UTC)) |
                ((PasswordResetOTP.verified == True) &
                 (PasswordResetOTP.expires_at < datetime.now(UTC) - timedelta(days=1)))
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
# OTP & RESET PASSWORD APIs
# ---------------------------

@app.route('/signup', methods=['POST'])
def global_signup():
    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')
    role = data.get('role', 'patient').lower()
    
    if not all([name, email, password]):
        return jsonify({"error": "Name, email, and password are required"}), 400
        
    # Ensure email is unique
    if Patient.query.filter_by(email=email).first() or Clinician.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered"}), 400
        
    # Need to verify OTP before creating account?
    # Alternatively, the flow is: /send_otp -> /verify_otp -> /signup
    # Let's assume the frontend will only call this if OTP was verified.
    # We check if an OTP was verified for this email.
    reset_entry = PasswordResetOTP.query.filter_by(email=email, verified=True).first()
    if not reset_entry:
        return jsonify({"error": "Email not verified via OTP"}), 400
        
    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
    
    if role == 'clinician':
        clinician_id = f"C{random.randint(1000, 9999)}"
        new_clinician = Clinician(
            clinician_id=clinician_id,
            name=name,
            email=email,
            password=hashed_password,
            role="clinician"
        )
        db.session.add(new_clinician)
    else:
        patient_id = f"P{random.randint(1000, 9999)}"
        new_patient = Patient(
            patient_id=patient_id,
            name=name,
            email=email,
            password=hashed_password
        )
        db.session.add(new_patient)
        
    db.session.delete(reset_entry)
    db.session.commit()
    return jsonify({"message": "Account created successfully", "success": True})

def get_utc_now():
    """Returns a naive datetime object representing the current UTC time."""
    return datetime.now(UTC).replace(tzinfo=None)

@app.route('/send_otp', methods=['POST'])
def global_send_otp():
    data = request.get_json()
    email = data.get('email')
    action = data.get('action', 'reset')
    role_req = data.get('role', '').lower()
    
    if not email:
        return jsonify({"error": "Email is required"}), 400
    
    email = email.strip()
    logging.info(f"OTP Request for email: '{email}', action: {action}, role_req: {role_req}")
        
    patient = None
    clinician = None
    admin = None
    
    if role_req == 'patient':
        patient = Patient.query.filter_by(email=email).first()
    elif role_req == 'clinician':
        clinician = Clinician.query.filter_by(email=email).first()
    elif role_req == 'admin':
        admin = Admin.query.filter_by(email=email).first()
    else:
        # If role is NOT provided or unknown, search ALL tables
        patient = Patient.query.filter_by(email=email).first()
        clinician = Clinician.query.filter_by(email=email).first()
        admin = Admin.query.filter_by(email=email).first()
    
    if action == 'reset':
        if not patient and not clinician and not admin:
            return jsonify({"error": "Account not found with this email"}), 404
    elif action == 'signup':
        if patient or clinician or admin:
            return jsonify({"error": "Email already registered"}), 400

    otp = ''.join(random.choices(string.digits, k=6))
    logging.info(f"Generated OTP '{otp}' for email '{email}'")
    
    # DELETE OLD OTPs FOR THIS EMAIL (Ensure only one active record)
    try:
        deleted_count = PasswordResetOTP.query.filter_by(email=email).delete()
        db.session.commit()
        if deleted_count > 0:
            logging.info(f"Deleted {deleted_count} old OTP records for {email}")
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error deleting old OTPs for {email}: {e}")

    reset_entry = PasswordResetOTP(
        email=email,
        otp=otp,
        expires_at=get_utc_now() + timedelta(minutes=5),
        verified=False
    )
    db.session.add(reset_entry)
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Database error", "details": str(e)}), 500
        
    user_id = "N/A"
    name = "User"
    display_role = role_req.capitalize() if role_req else "User"
    
    if patient:
        user_id = patient.patient_id
        name = patient.name
        display_role = "Patient"
    elif clinician:
        user_id = clinician.clinician_id
        name = clinician.name
        display_role = "Clinician"
    elif admin:
        user_id = admin.admin_id
        name = admin.name
        display_role = "Administrator"

    send_email_otp(email, otp, user_id=user_id, name=name, role=display_role)
    
    return jsonify({"message": "OTP sent successfully"})

@app.route('/verify_otp', methods=['POST'])
def global_verify_otp():
    data = request.get_json()
    email = data.get('email')
    otp = data.get('otp')
    
    if not email or not otp:
        return jsonify({"error": "Email and OTP are required"}), 400
        
    email = email.strip()
    otp = str(otp).strip()
    
    logging.info(f"Verify OTP attempt: email='{email}', otp_received='{otp}'")
    
    # Cleanup expired OTPs
    try:
        now = get_utc_now()
        deleted = PasswordResetOTP.query.filter(
            PasswordResetOTP.expires_at < now
        ).delete()
        db.session.commit()
        if deleted > 0:
            logging.info(f"Cleaned up {deleted} expired OTP records")
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error cleaning up expired OTPs: {e}")
        # Non-blocking

    # Get the latest requested OTP for this email
    reset_entry = PasswordResetOTP.query.filter_by(email=email).order_by(PasswordResetOTP.id.desc()).first()
    
    if not reset_entry:
        logging.warning(f"No OTP record found for email: '{email}'")
        return jsonify({"error": "No OTP requested for this email"}), 400
    
    logging.info(f"Found OTP record for {email}: stored_otp='{reset_entry.otp}', expires_at='{reset_entry.expires_at}', current_time='{get_utc_now()}'")
        
    if reset_entry.expires_at < get_utc_now():
        logging.warning(f"OTP expired for {email}. Stored expiry: {reset_entry.expires_at}")
        return jsonify({"error": "OTP has expired"}), 400
        
    if str(reset_entry.otp).strip() != otp:
        logging.warning(f"OTP mismatch for {email}: stored='{reset_entry.otp}', received='{otp}'")
        return jsonify({"error": "Invalid OTP"}), 400
        
    reset_entry.verified = True
    db.session.commit()
    
    return jsonify({"message": "OTP verified successfully"})

@app.route('/reset_password', methods=['POST'])
def global_reset_password():
    data = request.get_json()
    email = data.get('email')
    new_password = data.get('new_password')
    role = data.get('role', '').lower()
    
    if not email or not new_password:
        return jsonify({"error": "Email and new password are required"}), 400
        
    is_valid, error_msg = is_strong_password(new_password)
    if not is_valid:
        return jsonify({"error": error_msg}), 400
        
    reset_entry = PasswordResetOTP.query.filter_by(email=email).first()
    if not reset_entry or not reset_entry.verified:
        return jsonify({"error": "Must verify OTP first"}), 400
        
    user = None
    if role == 'patient':
        user = Patient.query.filter_by(email=email).first()
    elif role == 'clinician':
        user = Clinician.query.filter_by(email=email).first()
    elif role == 'admin':
        user = Admin.query.filter_by(email=email).first()
    
    # Fallback search regardless of role if not found yet
    if not user:
        user = Patient.query.filter_by(email=email).first() or \
               Clinician.query.filter_by(email=email).first() or \
               Admin.query.filter_by(email=email).first()

    if not user:
        return jsonify({"error": "User not found"}), 404
        
    hashed_password = bcrypt.generate_password_hash(new_password).decode('utf-8')
    user.password = hashed_password
        
    db.session.delete(reset_entry)
    db.session.commit()
    
    return jsonify({"message": "Password reset successfully"})

# ---------------------------
# ADMIN SETTINGS APIs
# ---------------------------

# (Duplicate /admin/profile route consolidated above)


# (Removed duplicate /admin/profile/update route)



@app.route("/admin/change_password", methods=["POST"])
def change_admin_password():

    data = request.get_json()

    admin = Admin.query.filter_by(admin_id=data.get("admin_id")).first()

    if not admin:
        return jsonify({"error": "Admin not found"}), 404

    if not bcrypt.check_password_hash(admin.password, data.get("old_password")):
        return jsonify({"error": "Old password incorrect"}), 400

    new_pwd_plain = data.get("new_password")
    is_valid, error_msg = is_strong_password(new_pwd_plain)
    if not is_valid:
        return jsonify({"error": error_msg}), 400

    new_pw = bcrypt.generate_password_hash(
        new_pwd_plain
    ).decode("utf-8")

    admin.password = new_pw

    db.session.commit()

    return jsonify({"message": "Password changed successfully"})

# ---------------------------
# SYSTEM SUPPORT INFO
# ---------------------------

@app.route("/system/support", methods=["GET"])
def get_system_support():
    role = request.args.get("role", "patient")
    settings = AppSettings.query.first()

    if role == "patient" or role == "clinician":
        # Both patients and clinicians need the clinic-specific info now
        # But per requirements: 
        # Clinician gets Admin (College details)
        # Patient gets Clinic (Emergency details)
        
        if role == "patient":
            return jsonify({
                "admin_phone": settings.clinic_phone,
                "support_email": settings.support_email,
                "app_version": settings.system_version,
                "clinic_name": settings.clinic_name
            })
        else: # clinician
             return jsonify({
                "admin_phone": settings.admin_phone,
                "support_email": settings.admin_email,
                "app_version": settings.system_version,
                "clinic_name": settings.clinic_name
            })
    else: # admin
        return jsonify({
            "admin_phone": settings.system_support_phone,
            "support_email": settings.system_support_email,
            "app_version": settings.system_version,
            "clinic_name": "System Support"
        })

# ---------------------------
# NEW DASHBOARD ENDPOINTS
# ---------------------------

@app.route("/patient/report_issue", methods=["POST"])
def report_issue():
    data = request.get_json()
    patient_id = data.get("patient_id")
    issue_type = data.get("issue_type")
    description = data.get("description")
    severity = data.get("severity")

    # If severity not provided, default to a safe value or existing logic
    if severity is None:
        severity = 5

    try:
        logging.info(f"Incoming report for patient {patient_id}, type {issue_type}, severity {severity}")
        
        new_issue = IssueReport(
            patient_id=patient_id,
            issue_type=issue_type,
            description=description,
            photo_url=data.get("photo_url", ""),
            severity=severity
        )
        db.session.add(new_issue)
        logging.info("IssueReport added to session")

        # Find the patient to update status and add notes
        patient = Patient.query.filter_by(patient_id=patient_id).first()
        
        if patient:
            logging.info(f"Updating patient {patient.name} status")
            
            # User mapping: 1-7 (attention), 8-10 (critical)
            new_status = "attention" if severity <= 7 else "critical"
            patient.status = new_status
            patient.updated_at = datetime.now(UTC)

            logging.info(f"Updated patient {patient.name} status to {new_status}")

            if patient.created_by_clinician:
                logging.info(f"Creating clinician notification for {patient.created_by_clinician}")
                doctor_notif = Notification(
                    user_id=patient.created_by_clinician,
                    role="clinician",
                    type="report_issue",
                    message=f"Urgent: Patient {patient.name} ({patient_id}) reported a '{issue_type}' (Severity: {severity}): {description}",
                    report_severity=severity,
                    clinician_label=ClinicianLabel.ATTENTION if severity <= 7 else ClinicianLabel.CRITICAL
                )
                db.session.add(doctor_notif)

        # 3. Notify the Patient (Receipt)
        logging.info("Notifying patient")
        patient_notif = Notification(
            user_id=patient_id,
            role="patient",
            type="report_issue",
            message=f"Your report for '{issue_type}' (Severity: {severity}) has been received. Our team will review it shortly."
        )
        db.session.add(patient_notif)

        logging.info("Attempting db.session.commit()")
        db.session.commit()
        return jsonify({
            "message": "Issue reported and notifications sent.",
            "status_updated": patient.status if patient else "N/A"
        })
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error reporting issue for {patient_id}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/patient/care_guide/<patient_id>", methods=["GET"])
def get_care_guide(patient_id):
    """Get personalized care guide based on patient's treatment stage"""
    patient = Patient.query.filter_by(patient_id=patient_id).first()
    if not patient:
        return jsonify({"error": "Patient not found"}), 404
    
    # Base care tips for all patients
    care_tips = [
        {
            "icon": "clock",
            "title": "22-Hour Rule",
            "description": "You must wear your aligners for 22 hours every single day. Only take them out to eat, drink (anything other than water), and brush your teeth."
        },
        {
            "icon": "droplet",
            "title": "Cleaning Your Aligners",
            "description": "Brush your aligners gently with a soft toothbrush and clear, unscented antibacterial soap. Avoid toothpaste, as it can be abrasive and cloud the plastic."
        },
        {
            "icon": "shield",
            "title": "Keep Them Safe",
            "description": "Always keep your aligners in their case when they are not in your mouth. Never wrap them in a napkin, as they are easily thrown away."
        },
        {
            "icon": "alert",
            "title": "Hot Liquids Warning",
            "description": "Never drink hot tea, coffee, or hot water while wearing your aligners. The heat will warp the plastic and make them unusable."
        }
    ]
    
    # Add treatment-specific tips
    treatment_stage = patient.treatment_stage or "initial"
    
    if "phase" in treatment_stage.lower() or "1" in treatment_stage:
        care_tips.append({
            "icon": "info",
            "title": "Phase 1 Tip",
            "description": "During initial treatment, you may experience more discomfort. This is normal as your teeth begin to move. Use aligner chewies to help seat them properly."
        })
    else:
        care_tips.append({
            "icon": "info",
            "title": "Maintenance Tip",
            "description": "Remember to switch to new trays as instructed. Keep your old trays in a safe place in case you need to go back."
        })
    
    return jsonify({
        "tips": care_tips,
        "treatment_stage": treatment_stage
    })

# ---------------------------
# PATIENT ISSUES
# ---------------------------
@app.route("/patient/issues/<patient_id>", methods=["GET"])
def get_patient_issues(patient_id):
    issues = IssueReport.query.filter_by(patient_id=patient_id).all()
    result = [{
        "id": issue.id,
        "issue_type": issue.issue_type,
        "description": issue.description,
        "status": issue.status,
        "severity": issue.severity,
        "photo_url": issue.photo_url,
        "created_at": issue.created_at.strftime("%Y-%m-%d %H:%M") if issue.created_at else "N/A"
    } for issue in issues]
    return jsonify(result)

@app.route("/clinician/schedule/<clinician_id>", methods=["GET"])
def get_clinician_schedule(clinician_id):
    try:
        clinician_id_clean = str(clinician_id or "").strip().lower()
        date_str = request.args.get("date")
        
        logging.info(f"Schedule requested for clinician: {clinician_id_clean}")
        
        # Base query for active appointments assigned to THIS clinician
        query = Appointment.query.filter(
            func.lower(func.trim(Appointment.clinician_id)) == clinician_id_clean,
            func.lower(func.trim(Appointment.status)) != 'cancelled',
            func.lower(func.trim(Appointment.status)) != 'completed'
        )
        
        if date_str:
            try:
                target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                query = query.filter(Appointment.appointment_date == target_date)
            except ValueError:
                return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400
        
        appointments = query.order_by(Appointment.appointment_date.asc(), Appointment.appointment_time.asc()).all()
        
        result = []
        for apt in appointments:
            # Robust patient lookup - handle cases where patient_id might be numeric in DB but string in query
            p_id_cleaned = str(apt.patient_id or "").strip().lower()
            patient = Patient.query.filter(func.lower(func.trim(Patient.patient_id)) == p_id_cleaned).first()
            
            result.append({
                "id": apt.id,
                "patient_id": apt.patient_id,
                "patient_name": patient.name if patient else "Unknown Patient",
                "patient_status": patient.status if patient else "on track",
                "patient_stage": patient.treatment_stage if patient else "Initial Consultation",
                "appointment_date": str(apt.appointment_date),
                "appointment_time": apt.appointment_time,
                "appointment_type": apt.appointment_type,
                "notes": apt.notes,
                "status": apt.status
            })
        
        logging.info(f"Successfully retrieved {len(result)} appointments for clinician {clinician_id_clean}")
        return jsonify(result)
        
    except Exception as e:
        import traceback
        logging.error(f"CRITICAL ERROR in get_clinician_schedule: {str(e)}")
        logging.error(traceback.format_exc())
        return jsonify({"error": "Internal server error while fetching schedule"}), 500

@app.route("/clinician/patients/<clinician_id>", methods=["GET"])
def get_clinician_patients(clinician_id):
    try:
        patients = Patient.query.all()
        result = []
        today = datetime.now().date()
        clinician_id_clean = str(clinician_id or "").strip().lower()
        
        for p in patients:
            # Standardized patient_id for robust matching
            p_id_cleaned = str(p.patient_id or "").strip().lower()
            
            # Check for upcoming active appointments using consistent logic
            appt = Appointment.query.filter(
                func.lower(func.trim(Appointment.patient_id)) == p_id_cleaned,
                Appointment.appointment_date >= today,
                func.lower(func.trim(Appointment.status)) != 'cancelled',
                func.lower(func.trim(Appointment.status)) != 'completed'
            ).order_by(Appointment.appointment_date.asc()).first()
            
            is_my_appt = False
            if appt:
                appt_cid = (appt.clinician_id or "").strip().lower()
                is_my_appt = (appt_cid == clinician_id_clean)

            result.append({
                "patient_id": p.patient_id,
                "name": p.name,
                "email": p.email,
                "phone_number": p.phone_number,
                "status": p.status,
                "treatment_stage": p.treatment_stage,
                "is_active": p.is_active,
                "updated_at": p.updated_at.strftime("%Y-%m-%d") if p.updated_at else None,
                "has_appointment": appt is not None,
                "is_my_appointment": is_my_appt,
                "next_appointment_date": str(appt.appointment_date) if appt else None
            })
        return jsonify(result)
        
    except Exception as e:
        import traceback
        logging.error(f"CRITICAL ERROR in get_clinician_patients: {str(e)}")
        logging.error(traceback.format_exc())
        return jsonify({"error": "Internal server error while fetching patients"}), 500

# ---------------------------
# ADMIN USER ACTIONS
# ---------------------------

@app.route("/admin/user/update", methods=["POST"])
def admin_update_user():
    data = request.get_json()
    user_id = data.get("id")
    role = data.get("role")
    
    if role == "patient":
        user = Patient.query.filter_by(patient_id=user_id).first()
    elif role == "clinician":
        user = Clinician.query.filter_by(clinician_id=user_id).first()
    elif role == "admin":
        user = Admin.query.filter_by(admin_id=user_id).first()
    else:
        return jsonify({"error": "Invalid role"}), 400

    if not user:
        return jsonify({"error": "User not found"}), 404

    user.name = data.get("name", user.name)
    user.email = data.get("email", user.email)
    
    if hasattr(user, 'phone_number') and "phone_number" in data:
        user.phone_number = data["phone_number"]
    
    if role == "patient" and "treatment_stage" in data:
        user.treatment_stage = data["treatment_stage"]
        
    if role == "clinician" and "role_type" in data:
        # Map role_type from mobile to specialization in DB
        user.role = data["role_type"]

    if role in ["patient", "clinician"] and "status" in data:
        status_val = data.get("status")
        if status_val:
            user.status = status_val.lower()  # e.g. "on track", "attention", "critical"
            user.is_active = (status_val != "Inactive")
            
    if role == "patient" and "notes" in data:
        user.notes = data["notes"]

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    return jsonify({"message": "User updated successfully"})

@app.route("/admin/user/delete/<role>/<user_id>", methods=["DELETE"])
def admin_delete_user(role, user_id):
    if role == "patient":
        user = Patient.query.filter_by(patient_id=user_id).first()
        # Clean up related records for patient if needed, or just let cascade work
        # For simplicity in this demo, we'll just delete the user
    elif role == "clinician":
        user = Clinician.query.filter_by(clinician_id=user_id).first()
    elif role == "admin":
        user = Admin.query.filter_by(admin_id=user_id).first()
    else:
        return jsonify({"error": "Invalid role"}), 400

    if not user:
        return jsonify({"error": "User not found"}), 404

    try:
        # Soft-delete for patient/clinician, hard-delete for admin
        if role in ["patient", "clinician"]:
            user.is_active = False
        else:
            db.session.delete(user)
        
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    return jsonify({"message": "User deleted successfully"})


@app.route("/admin/user/reset_password", methods=["POST"])
def admin_reset_user_password():
    data = request.get_json()
    user_id = data.get("id")
    role = data.get("role")
    new_password = data.get("new_password")
    
    if role == "patient":
        user = Patient.query.filter_by(patient_id=user_id).first()
    elif role == "clinician":
        user = Clinician.query.filter_by(clinician_id=user_id).first()
    elif role == "admin":
        user = Admin.query.filter_by(admin_id=user_id).first()
    else:
        return jsonify({"error": "Invalid role"}), 400

    if not user:
        return jsonify({"error": "User not found"}), 404

    if new_password:
        pw_to_set = new_password
        msg = f"Password updated manually for {user.name}."
    else:
        # Fallback to default reset: ortho@last4digits
        phone = getattr(user, 'phone_number', '') or ''
        pw_to_set = f"ortho@{phone[-4:]}" if len(phone) >= 4 else (phone if phone else "123456")
        msg = f"Password reset successfully for {user.name}. The temporary passkey is '{pw_to_set}'."
    
    user.password = bcrypt.generate_password_hash(pw_to_set).decode("utf-8")
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    return jsonify({"message": msg})

@app.route("/admin/user/create", methods=["POST"])
def admin_create_user():
    data = request.get_json()
    role = data.get("role")
    user_id = data.get("id")
    
    if not role or not user_id:
        return jsonify({"error": "Role and ID are required"}), 400

    # Same passkey logic: ortho@last4 or default
    phone = data.get("phone_number", "")
    temp_pw = f"ortho@{phone[-4:]}" if len(phone) >= 4 else (phone if phone else "123456")
    hashed_pw = bcrypt.generate_password_hash(temp_pw).decode("utf-8")
    
    if role == "patient":
        if Patient.query.filter_by(patient_id=user_id).first():
            return jsonify({"error": "Patient ID already exists"}), 400
        if data.get("email") and Patient.query.filter_by(email=data.get("email")).first():
            return jsonify({"error": "Patient email already exists"}), 400
        new_user = Patient(
            patient_id=user_id,
            name=data.get("name"),
            email=data.get("email"),
            phone_number=data.get("phone_number"),
            password=hashed_pw,
            treatment_stage=data.get("treatment_stage") or "Initial Consultation",
            created_by_clinician=data.get("clinician_id"),
            is_active=True
        )
    elif role == "clinician":
        if Clinician.query.filter_by(clinician_id=user_id).first():
            return jsonify({"error": "Clinician ID already exists"}), 400
        if data.get("email") and Clinician.query.filter_by(email=data.get("email")).first():
            return jsonify({"error": "Clinician email already exists"}), 400
        new_user = Clinician(
            clinician_id=user_id,
            name=data.get("name"),
            role=data.get("role_type", "Assistant"),
            email=data.get("email"),
            phone_number=data.get("phone_number"),
            password=hashed_pw,
            is_active=True
        )
    elif role == "admin":
        if Admin.query.filter_by(admin_id=user_id).first():
            return jsonify({"error": "Admin ID already exists"}), 400
        if data.get("email") and Admin.query.filter_by(email=data.get("email")).first():
            return jsonify({"error": "Admin email already exists"}), 400
        new_user = Admin(
            admin_id=user_id,
            name=data.get("name"),
            email=data.get("email"),
            phone_number=data.get("phone_number"),
            password=hashed_pw
        )
    else:
        return jsonify({"error": "Invalid role"}), 400

    db.session.add(new_user)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    # Send welcome email with credentials (Non-blocking for account creation)
    try:
        send_welcome_email(
            to_email=data.get("email"),
            name=data.get("name"),
            user_id=user_id,
            password=temp_pw,
            role=role,
            creator_name=data.get("creator_name", "System Admin")
        )
    except Exception as e:
        logging.error(f"Failed to send welcome email for {user_id}: {e}")
        # We don't return error here because the account WAS created successfully in DB


    return jsonify({"message": f"{role.capitalize()} created successfully"})

@app.route("/admin/profile/update", methods=["POST"])
def admin_profile_update():
    data = request.get_json()
    # The frontend passes 'id', which for admins should be their admin_id (e.g. ADMIN001)
    admin_id = data.get("id") or data.get("admin_id")
    
    if not admin_id:
        return jsonify({"error": "Admin ID is required"}), 400

    admin = Admin.query.filter_by(admin_id=admin_id).first()
    if not admin:
        return jsonify({"error": f"Admin with ID {admin_id} not found"}), 404

    admin.name = data.get("name", admin.name)
    admin.email = data.get("email", admin.email)
    admin.phone_number = data.get("phone", data.get("phone_number", admin.phone_number))

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error updating admin profile for {admin_id}: {e}")
        return jsonify({"error": "Failed to update database"}), 500

    return jsonify({
        "message": "Profile updated successfully",
        "user": {
            "user_id": admin.admin_id, # return as user_id to match frontend expectations
            "name": admin.name,
            "email": admin.email,
            "role": "admin",
            "phone": admin.phone_number
        }
    })

@app.route("/admin/analytics/overview", methods=["GET"])
def admin_analytics_overview():
    # Only use database dates as they are now backfilled or real
    all_users_list = Patient.query.all() + Clinician.query.all() + Admin.query.all()
    
    patient_count = Patient.query.count()
    clinician_count = Clinician.query.count()
    admin_count = Admin.query.count()
    total_users = patient_count + clinician_count + admin_count

    active_patients = Patient.query.filter_by(is_active=True).count()
    active_clinicians = Clinician.query.filter_by(is_active=True).count()

    # Group by REAL database created_at
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    # We'll show "New Users" per month (this month's growth) which is better for a BarChart
    growth_map = {m: 0 for m in months}
    
    current_year = 2026
    
    for u in all_users_list:
        if u.created_at and u.created_at.year == current_year:
            m_idx = u.created_at.month - 1
            growth_map[months[m_idx]] += 1
        elif u.created_at and u.created_at.year < current_year:
            # Historically added users don't show as NEW this year, or can be in Jan
            growth_map["Jan"] += 1
        else:
            # Fallback if no date (though backfill should have fixed it)
            growth_map["Jan"] += 1

    monthly_data = []
    for m in months:
        # Non-cumulative: strictly how many added that month
        monthly_data.append({"month": m, "users": growth_map[m]})

    # Appointments today
    today = datetime.now().date()
    appts_today = Appointment.query.filter(
        Appointment.appointment_date == today,
        Appointment.status != 'cancelled'
    ).count()

    # Pending issues
    pending_issues = IssueReport.query.filter_by(status="Pending").count()

    return jsonify({
        "total_patients": patient_count,
        "total_clinicians": clinician_count,
        "active_patients": active_patients,
        "active_clinicians": active_clinicians,
        "total_admins": admin_count,
        "total_users": total_users,
        "appointments_today": appts_today,
        "pending_issues": pending_issues,
        "growth": monthly_data,
        "active_ai_usage": 94.5,
        "system_uptime": 99.99
    })

@app.route("/admin/users", methods=["GET"])
def get_all_users():
    patients = Patient.query.all()
    clinicians = Clinician.query.all()
    admins = Admin.query.all()
    
    patients_list = []
    for p in patients:
        patients_list.append({
            "id": p.patient_id, 
            "name": p.name, 
            "email": p.email, 
            "phone_number": p.phone_number,
            "role": "patient", 
            "treatment_stage": p.treatment_stage,
            "is_active": p.is_active,
            "status": "Active" if p.is_active else "Inactive", 
            "createdAt": p.created_at.strftime("%b %d, %Y") if p.created_at else "N/A"
        })

    clinicians_list = []
    for c in clinicians:
        clinicians_list.append({
            "id": c.clinician_id, 
            "name": c.name, 
            "email": c.email, 
            "phone_number": c.phone_number,
            "role": "clinician", 
            "role_type": c.role,
            "is_active": c.is_active,
            "status": "Active" if c.is_active else "Inactive", 
            "createdAt": c.created_at.strftime("%b %d, %Y") if c.created_at else "N/A"
        })

    admins_list = []
    for a in admins:
        admins_list.append({
            "id": a.admin_id, 
            "name": a.name, 
            "email": a.email, 
            "phone_number": a.phone_number,
            "role": "admin", 
            "is_active": True,
            "status": "Active", 
            "createdAt": a.created_at.strftime("%b %d, %Y") if a.created_at else "N/A"
        })
        
    return jsonify({
        "patients": patients_list,
        "clinicians": clinicians_list,
        "admins": admins_list
    })
    
@app.route("/admin/user/<role>/<user_id>", methods=["GET"])
def get_single_user(role, user_id):
    if role == "patient":
        user = Patient.query.filter_by(patient_id=user_id).first()
        if user:
            return jsonify({
                "id": user.patient_id,
                "name": user.name,
                "email": user.email,
                "phone_number": user.phone_number,
                "role": "patient",
                "treatment_stage": user.treatment_stage,
                "is_active": user.is_active,
                "status": "Active" if user.is_active else "Inactive"
            })
    elif role == "clinician":
        user = Clinician.query.filter_by(clinician_id=user_id).first()
        if user:
            return jsonify({
                "id": user.clinician_id,
                "name": user.name,
                "email": user.email,
                "phone_number": user.phone_number,
                "role": "clinician",
                "role_type": user.role,
                "is_active": user.is_active,
                "status": "Active" if user.is_active else "Inactive"
            })
    elif role == "admin":
        user = Admin.query.filter_by(admin_id=user_id).first()
        if user:
            return jsonify({
                "id": user.admin_id,
                "name": user.name,
                "email": user.email,
                "phone_number": user.phone_number,
                "role": "admin",
                "is_active": True,
                "status": "Active"
            })
            
    return jsonify({"error": "User not found"}), 404

@app.route("/admin/system_settings", methods=["GET", "POST"])
def manage_system_settings():
    settings = AppSettings.query.first()
    if not settings:
        settings = AppSettings()
        db.session.add(settings)
        db.session.commit()
    
    if request.method == "POST":
        data = request.get_json()
        settings.clinic_name = data.get("clinic_name", settings.clinic_name)
        settings.support_email = data.get("support_email", settings.support_email)
        settings.admin_phone = data.get("admin_phone", settings.admin_phone)
        
        # Toggles
        settings.enable_public_registration = data.get("enable_public_registration", settings.enable_public_registration)
        settings.ai_diagnostic_assistant = data.get("ai_diagnostic_assistant", settings.ai_diagnostic_assistant)
        settings.sms_reminders = data.get("sms_reminders", settings.sms_reminders)
        settings.maintenance_mode = data.get("maintenance_mode", settings.maintenance_mode)
        
        db.session.commit()
        return jsonify({"message": "Settings updated successfully"})
        
    return jsonify({
        "clinic_name": settings.clinic_name,
        "support_email": settings.support_email,
        "admin_phone": settings.admin_phone,
        "enable_public_registration": settings.enable_public_registration,
        "ai_diagnostic_assistant": settings.ai_diagnostic_assistant,
        "sms_reminders": settings.sms_reminders,
        "maintenance_mode": settings.maintenance_mode
    })

@app.route("/admin/system_alerts", methods=["GET"])
def get_system_alerts():
    # Admin sees all pending issue reports as 'System Alerts'
    alerts = IssueReport.query.order_by(IssueReport.created_at.desc()).all()
    result = []
    for alert in alerts:
        result.append({
            "id": alert.id,
            "patient_id": alert.patient_id,
            "type": alert.issue_type,
            "message": alert.description,
            "status": alert.status,
            "time": alert.created_at.strftime("%Y-%m-%d %H:%M:%S")
        })
    return jsonify(result)

@app.route("/admin/system_alerts/resolve/<int:alert_id>", methods=["POST"])
def resolve_system_alert(alert_id):
    alert = IssueReport.query.get(alert_id)
    if not alert:
        return jsonify({"error": "Alert not found"}), 404
    
    alert.status = "Resolved"
    
    # Also mark corresponding notifications as read for admins
    # We search for notifications for any admin that mention this patient
    try:
        patient = Patient.query.get(alert.patient_id)
        search_term = f"%Patient {patient.name if patient else alert.patient_id}%"
        
        related_notifs = Notification.query.filter(
            Notification.role == "admin",
            Notification.type == "report_issue",
            Notification.message.like(search_term),
            Notification.is_read == False
        ).all()
        
        for n in related_notifs:
            n.is_read = True
            
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error resolving alert {alert_id}: {e}")
        return jsonify({"error": "Failed to resolve alert"}), 500
        
    return jsonify({"message": "Alert marked as resolved and notifications cleared"})

@app.route("/clinician/dashboard/<clinician_id>", methods=["GET"])
def get_clinician_dashboard(clinician_id):
    clinician_id_clean = clinician_id.strip()
    settings = AppSettings.query.first()
    
    # Accept optional date from client to handle timezone differences
    date_str = request.args.get("date")
    if date_str:
        try:
            today = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            today = datetime.now().date()
    else:
        today = datetime.now().date()
    
    logging.info(f"Dashboard request for clinician: {clinician_id_clean} on date: {today}")
    
    # User requested clinician dashboard to show system-wide stats for Total and Priority
    patients_count = Patient.query.count()
    
    # Robust clinician_id comparison
    appointments_today_count = Appointment.query.filter(
        func.lower(func.trim(Appointment.clinician_id)) == clinician_id_clean.lower(),
        Appointment.appointment_date == today,
        func.lower(func.trim(Appointment.status)) != 'cancelled',
        func.lower(func.trim(Appointment.status)) != 'completed'
    ).count()
    
    # Priority Patients Logic (Unscheduled critical/attention patients)
    # BUG FIX: Include "rescheduled" status as an active appointment
    active_statuses = ["scheduled", "rescheduled"]
    upcoming_appt_pids = [aid[0] for aid in db.session.query(Appointment.patient_id).filter(
        Appointment.appointment_date >= today,
        Appointment.status.in_(active_statuses)
    ).all()]

    priority_query = Patient.query.filter(
        and_(
            func.lower(Patient.status).in_(["critical", "attention"]),
            ~Patient.patient_id.in_(upcoming_appt_pids)
        )
    )
    
    all_priority = priority_query.all()
    # Sort: critical first, then attention, then by updated_at
    all_priority.sort(key=lambda p: (0 if p.status.lower() == 'critical' else 1, -(p.updated_at.timestamp() if p.updated_at else 0)))
    
    priority_count = Patient.query.filter(func.lower(Patient.status).in_(["critical", "attention"])).count()
    recent_patients_list = all_priority[:8]
    
    # Robust clinician_id comparison
    schedule = Appointment.query.filter(
        func.lower(func.trim(Appointment.clinician_id)) == clinician_id_clean.lower(),
        Appointment.appointment_date == today,
        func.lower(func.trim(Appointment.status)) != 'cancelled',
        func.lower(func.trim(Appointment.status)) != 'completed'
    ).order_by(Appointment.appointment_time.asc()).all()
    
    logging.info(f"Dashboard: Found {len(schedule)} appointments for today")

    # Find next appointment (if any upcoming after today)
    # Robust clinician_id comparison
    next_apt = Appointment.query.filter(
        func.lower(func.trim(Appointment.clinician_id)) == clinician_id_clean.lower(),
        Appointment.appointment_date > today,
        func.lower(func.trim(Appointment.status)) != 'cancelled',
        func.lower(func.trim(Appointment.status)) != 'completed'
    ).order_by(Appointment.appointment_date.asc(), Appointment.appointment_time.asc()).first()
    
    next_apt_data = None
    if next_apt:
        # Robust patient_id comparison
        p_next = Patient.query.filter(func.lower(func.trim(Patient.patient_id)) == next_apt.patient_id.lower().strip()).first()
        next_apt_data = {
            "id": next_apt.id,
            "patient_id": next_apt.patient_id,
            "patient_name": p_next.name if p_next else "Unknown",
            "patient_status": p_next.status if p_next else "on track",
            "patient_stage": p_next.treatment_stage if p_next else "Initial Consultation",
            "appointment_date": str(next_apt.appointment_date),
            "appointment_time": next_apt.appointment_time,
            "appointment_type": next_apt.appointment_type,
            "status": next_apt.status
        }

    return jsonify({
        "clinic_name": settings.clinic_name if settings else "OrthoGuide Clinic",
        "total_patients": patients_count,
        "appointments_today": appointments_today_count,
        "need_attention": priority_count,
        "recent_patients": [{
            "patient_id": p.patient_id,
            "name": p.name,
            "status": p.status,
            "treatment_stage": p.treatment_stage,
            "updated_at": p.updated_at.strftime("%b %d") if p.updated_at else "N/A"
        } for p in recent_patients_list],
        "today_schedule": [{
            "id": apt.id,
            "patient_id": apt.patient_id,
            "patient_name": (p := Patient.query.filter(func.lower(func.trim(Patient.patient_id)) == apt.patient_id.lower().strip()).first()) and p.name or "Unknown",
            "patient_status": p.status if p else "on track",
            "patient_stage": p.treatment_stage if p else "Initial Consultation",
            "appointment_date": str(apt.appointment_date),
            "appointment_time": apt.appointment_time,
            "appointment_type": apt.appointment_type,
            "status": apt.status
        } for apt in schedule],
        "next_appointment": next_apt_data
    })


@app.route("/clinician/add_patient", methods=["POST"])
def clinician_add_patient():
    data = request.get_json()
    clinician_id = data.get("clinician_id")
    patient_id = data.get("patient_id")
    
    if Patient.query.filter_by(patient_id=patient_id).first():
        return jsonify({"error": "Patient ID already exists"}), 400
        
    if data.get("email") and Patient.query.filter_by(email=data.get("email")).first():
        return jsonify({"error": "Patient email already exists"}), 400
        
    phone = data.get("phone_number", "")
    temp_pw = f"ortho@{phone[-4:]}" if len(phone) >= 4 else (phone if phone else "123456")
    hashed_pw = bcrypt.generate_password_hash(temp_pw).decode("utf-8")
    
    new_patient = Patient(
        patient_id=patient_id,
        name=data.get("name"),
        email=data.get("email"),
        phone_number=data.get("phone_number"),
        password=hashed_pw,
        created_by_clinician=clinician_id,
        treatment_stage=data.get("treatment_stage", "Initial Consultation"),
        status="on track",
        is_active=True
    )
    db.session.add(new_patient)
    db.session.commit()
    
    # Send welcome email with credentials
    creator_name = data.get("creator_name", "Your Clinician")
    if creator_name and not creator_name.lower().startswith("dr."):
        creator_name = f"Dr. {creator_name}"

    send_welcome_email(
        to_email=data.get("email"),
        name=data.get("name"),
        user_id=patient_id,
        password=temp_pw,
        role="patient",
        creator_name=creator_name
    )
    
    return jsonify({"message": "Patient added successfully", "patient": {"name": new_patient.name, "id": new_patient.patient_id}})

@app.route("/clinician/schedule/add", methods=["POST"])
def clinician_add_schedule():
    data = request.get_json()
    
    # Check if patient exists
    if not Patient.query.filter_by(patient_id=data.get("patient_id")).first():
        return jsonify({"error": "Patient not found"}), 404
        
    date_str = data.get("appointment_date")
    time_str = data.get("appointment_time")
    try:
        # Check if time_str is in 'HH:MM AM/PM' format or 'HH:MM'
        try:
            full_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %I:%M %p")
        except ValueError:
            full_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        
        # Use Asia/Kolkata for consistency with scheduler
        tz = pytz.timezone('Asia/Kolkata')
        local_now = datetime.now(tz)
        localized_dt = tz.localize(full_dt)
        
        # Allow 'now' by subtracting a 1-minute grace period
        if localized_dt < local_now - timedelta(minutes=1):
            return jsonify({"error": "Cannot plan sessions in the past"}), 400
            
        appt_date = full_dt.date()
            
    except ValueError:
        return jsonify({"error": "Invalid date or time format"}), 400
        
    # Check if an active appointment already exists for this patient and date
    # BUG FIX: Use robust patient_id comparison to prevent duplicates due to formatting
    existing_app = Appointment.query.filter(
        func.lower(func.trim(Appointment.patient_id)) == data.get("patient_id", "").lower().strip(),
        Appointment.appointment_date == appt_date,
        func.lower(func.trim(Appointment.status)) != 'cancelled'
    ).first()
    
    if existing_app:
        existing_app.clinician_id = data.get("clinician_id")
        existing_app.appointment_time = time_str
        existing_app.appointment_type = data.get("appointment_type", "Checkup")
        existing_app.notes = data.get("notes", existing_app.notes)
        existing_app.status = "scheduled"
        
        # Create notification for update
        send_appointment_notification(data.get("patient_id"), existing_app.id, "rescheduled")
        
        db.session.commit()
        return jsonify({
            "message": "Existing treatment session updated successfully",
            "appointment_id": existing_app.id
        })
        
    new_app = Appointment(
        patient_id=data.get("patient_id"),
        clinician_id=data.get("clinician_id"),
        appointment_date=appt_date,
        appointment_time=time_str,
        appointment_type=data.get("appointment_type", "Checkup"),
        notes=data.get("notes", ""),
        status="scheduled"
    )
    db.session.add(new_app)
    
    # Create notification for new appointment
    send_appointment_notification(data.get("patient_id"), new_app.id, "scheduled")
    
    db.session.commit()
    return jsonify({
        "message": "Treatment session planned successfully",
        "appointment_id": new_app.id
    })


# ---------------------------
# RUN SERVER
# ---------------------------




@app.route("/patient/chatbot", methods=["POST"])
def patient_chatbot():
    data = request.get_json()
    user_message = data.get("message", "").strip()
    patient_id = data.get("patient_id", "")
    
    if not user_message:
        return jsonify({"answer": "Please say something!"}), 400
    
    # Use FAQ Chatbot Engine instead of LLM
    results = find_faq_answer(user_message)
    answer = results[0]["answer"] if results else "I'm sorry, I don't have an answer for that. Please try again or contact your clinician."
    source = "FAQ"
    
    return jsonify({
        "answer": answer,
        "source": source
    })

@app.route("/patient/chat_history/<patient_id>", methods=["GET"])
def get_chat_history(patient_id):
    try:
        messages = ChatMessage.query.filter_by(patient_id=patient_id).order_by(ChatMessage.created_at.asc()).all()
        history = []
        for msg in messages:
            history.append({
                "message": msg.message,
                "sender": msg.sender if isinstance(msg.sender, str) else msg.sender.value if hasattr(msg.sender, 'value') else str(msg.sender),
                "created_at": msg.created_at.isoformat() if hasattr(msg.created_at, 'isoformat') else str(msg.created_at)
            })
        return jsonify(history)
    except Exception as e:
        print(f"Error fetching chat history: {e}")
        return jsonify({"error": "Failed to fetch chat history"}), 500

# ---------------------------
# REACTIVATION REQUESTS
# ---------------------------

@app.route("/patient/reactivation/request", methods=["POST"])
def submit_reactivation_request():
    data = request.get_json()
    patient_id = data.get("patient_id")
    patient_name = data.get("patient_name")
    user_role = data.get("user_role", "patient")
    contact_info = data.get("contact_info") # email/phone
    reason = data.get("reason")

    if not all([patient_id, patient_name, contact_info, reason]):
        return jsonify({"error": "Missing required fields"}), 400

    # 1. Validate Account and Contact Info
    if user_role == "clinician":
        user = Clinician.query.filter_by(clinician_id=patient_id).first()
        role_label = "Clinician"
    else:
        user = Patient.query.filter_by(patient_id=patient_id).first()
        role_label = "Patient"

    if not user:
        return jsonify({"error": f"{role_label} ID not found. Please check your ID."}), 404

    # Normalize for comparison
    def normalize_phone(p):
        return re.sub(r'\D', '', p) if p else ""

    reg_email = (user.email or "").lower().strip()
    reg_phone = normalize_phone(user.phone_number)
    
    input_info = contact_info.lower().strip()
    input_phone = normalize_phone(contact_info)

    # Match email or phone (using suffix match for phone to handle country codes)
    match_email = input_info == reg_email
    match_phone = False
    if input_phone and reg_phone:
        # Match if one is a suffix of another (min 10 digits to be safe)
        if (reg_phone.endswith(input_phone) or input_phone.endswith(reg_phone)) and len(input_phone) >= 10:
            match_phone = True

    if not (match_email or match_phone):
        return jsonify({"error": "The provided email/phone does not match our records for this account."}), 403

    # Prevent duplicate pending requests only if they are UNREAD (once read, allow re-requesting if still deactivated)
    existing = ReactivationRequest.query.filter_by(patient_id=patient_id, user_role=user_role, status="Pending", is_read=False).first()
    if existing:
        return jsonify({"error": "A pending request already exists for this account."}), 409

    new_request = ReactivationRequest(
        patient_id=patient_id,
        patient_name=patient_name,
        user_role=user_role,
        contact_info=contact_info,
        reason=reason
    )
    
    try:
        db.session.add(new_request)
        db.session.commit()
        return jsonify({"message": "Request Sent"}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route("/admin/reactivation/requests", methods=["GET"])
def get_reactivation_requests():
    requests = ReactivationRequest.query.order_by(ReactivationRequest.created_at.desc()).all()
    result = []
    for req in requests:
        result.append({
            "id": req.id,
            "patient_id": req.patient_id,
            "patient_name": req.patient_name,
            "user_role": req.user_role,
            "contact_info": req.contact_info,
            "reason": req.reason,
            "status": req.status,
            "is_read": req.is_read,
            "created_at": req.created_at.strftime("%Y-%m-%d %H:%M:%S")
        })
    return jsonify(result)

@app.route("/admin/reactivation/action", methods=["POST"])
def reactivation_action():
    data = request.get_json()
    request_id = data.get("request_id")
    action = data.get("action") # "approve" or "reject"

    req = ReactivationRequest.query.get(request_id)
    if not req:
        return jsonify({"error": "Request not found"}), 404

    if action == "approve":
        if req.user_role == "clinician":
            user = Clinician.query.filter_by(clinician_id=req.patient_id).first()
        else:
            user = Patient.query.filter_by(patient_id=req.patient_id).first()
        
        if user:
            user.is_active = True
            req.status = "Approved"
            db.session.commit()
            return jsonify({"message": f"Account for {req.patient_name} reactivated successfully"})
        return jsonify({"error": "User not found"}), 404
    
    elif action == "reject":
        req.status = "Rejected"
        db.session.commit()
        return jsonify({"message": "Request rejected"})

    return jsonify({"error": "Invalid action"}), 400

if __name__ == "__main__":
    try:
        with app.app_context():
            print("Initializing database...", flush=True)
            db.create_all()
            print("Database initialized.", flush=True)

        import os
        if not scheduler.running and os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
            print("Starting scheduler in main process...", flush=True)
            scheduler.start()
        elif not scheduler.running and not app.debug:
            print("Starting scheduler...", flush=True)
            scheduler.start()

        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except Exception:
            local_ip = "localhost"
            
        print(f"Server starting on http://{local_ip}:5001", flush=True)
        app.run(debug=True, host="0.0.0.0", port=5001)
    except Exception as e:
        print(f"CRITICAL ERROR DURING STARTUP: {e}", flush=True)
        logging.error(f"Startup error: {e}")