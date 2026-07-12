
import os
import json
import urllib.parse
import smtplib
from email.message import EmailMessage
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from pathlib import Path
from datetime import datetime, date, timedelta
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash, abort, jsonify, send_from_directory
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-secret-key")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL",
    "sqlite:///" + os.path.join(BASE_DIR, "mawadda.db")
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = os.path.join(BASE_DIR, "uploads")
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
app.config["UPLOAD_FOLDER"] = os.path.join(BASE_DIR, "uploads")
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "سجّل الدخول أولًا."


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    phone = db.Column(db.String(30))
    whatsapp = db.Column(db.String(30))
    photo = db.Column(db.String(255))
    role = db.Column(db.String(20), nullable=False, default="parent")  # admin, manager, accountant, teacher, parent
    password_hash = db.Column(db.String(255), nullable=False)
    is_active_user = db.Column(db.Boolean, default=True)

    teacher_profile = db.relationship("Teacher", backref="user", uselist=False)
    parent_profile = db.relationship("Parent", backref="user", uselist=False)

    @property
    def is_active(self):
        return self.is_active_user

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Teacher(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True, nullable=False)
    employee_code = db.Column(db.String(30), unique=True)
    specialization = db.Column(db.String(120))
    bio = db.Column(db.Text)
    join_date = db.Column(db.Date, default=date.today)


class Parent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    parent_code = db.Column(db.String(30), unique=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True, nullable=False)
    address = db.Column(db.String(255))
    country = db.Column(db.String(80), default="مصر")


class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_code = db.Column(db.String(30), unique=True)
    full_name = db.Column(db.String(120), nullable=False)
    birth_date = db.Column(db.Date)
    gender = db.Column(db.String(10))
    country = db.Column(db.String(80), default="مصر")
    level = db.Column(db.String(120))
    notes = db.Column(db.Text)
    photo = db.Column(db.String(255))
    parent_id = db.Column(db.Integer, db.ForeignKey("parent.id"), nullable=False)
    active = db.Column(db.Boolean, default=True)
    parent = db.relationship("Parent", backref=db.backref("students", lazy=True))



class SystemSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ManagerEvaluation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    evaluator_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    target_type = db.Column(db.String(20), nullable=False)  # student / teacher
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"))
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher.id"))
    score = db.Column(db.Float, nullable=False)
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    evaluator = db.relationship("User")
    student = db.relationship("Student")
    teacher = db.relationship("Teacher")

class Circle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher.id"), nullable=False)
    study_type = db.Column(db.String(30), default="أونلاين")
    default_minutes = db.Column(db.Integer, default=30)
    schedule_text = db.Column(db.String(255))
    active = db.Column(db.Boolean, default=True)
    teacher = db.relationship("Teacher", backref=db.backref("circles", lazy=True))


class Enrollment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    circle_id = db.Column(db.Integer, db.ForeignKey("circle.id"), nullable=False)
    start_date = db.Column(db.Date, default=date.today)
    active = db.Column(db.Boolean, default=True)
    student = db.relationship("Student", backref=db.backref("enrollments", lazy=True))
    circle = db.relationship("Circle", backref=db.backref("enrollments", lazy=True))


class LessonSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    circle_id = db.Column(db.Integer, db.ForeignKey("circle.id"), nullable=False)
    session_date = db.Column(db.Date, default=date.today)
    start_time = db.Column(db.String(10))
    duration_minutes = db.Column(db.Integer, default=30)
    actual_minutes = db.Column(db.Integer)
    session_type = db.Column(db.String(30), default="عادية")
    cancellation_reason = db.Column(db.String(255))
    rescheduled_from_id = db.Column(db.Integer)
    topic = db.Column(db.String(255))
    status = db.Column(db.String(30), default="مجدولة")
    notes = db.Column(db.Text)
    circle = db.relationship("Circle", backref=db.backref("sessions", lazy=True))


class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("lesson_session.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="حاضر")
    notes = db.Column(db.String(255))
    session = db.relationship("LessonSession", backref=db.backref("attendance_records", lazy=True))
    student = db.relationship("Student", backref=db.backref("attendance_records", lazy=True))


class StudentEvaluation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("lesson_session.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher.id"), nullable=False)
    memorization = db.Column(db.Integer, default=0)
    revision = db.Column(db.Integer, default=0)
    tajweed = db.Column(db.Integer, default=0)
    pronunciation = db.Column(db.Integer, default=0)
    focus = db.Column(db.Integer, default=0)
    homework_done = db.Column(db.Boolean, default=False)
    lesson_covered = db.Column(db.String(255))
    homework = db.Column(db.String(255))
    parent_note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    session = db.relationship("LessonSession", backref=db.backref("evaluations", lazy=True))
    student = db.relationship("Student", backref=db.backref("evaluations", lazy=True))
    teacher = db.relationship("Teacher", backref=db.backref("student_evaluations", lazy=True))

    @property
    def average(self):
        values = [self.memorization, self.revision, self.tajweed, self.pronunciation, self.focus]
        return round(sum(values) / len(values), 1)


class TeacherEvaluation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    parent_id = db.Column(db.Integer, db.ForeignKey("parent.id"), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    punctuality = db.Column(db.Integer, default=0)
    communication = db.Column(db.Integer, default=0)
    explanation = db.Column(db.Integer, default=0)
    motivation = db.Column(db.Integer, default=0)
    progress = db.Column(db.Integer, default=0)
    comment = db.Column(db.Text)
    private_to_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    parent = db.relationship("Parent", backref=db.backref("teacher_evaluations", lazy=True))
    teacher = db.relationship("Teacher", backref=db.backref("parent_evaluations", lazy=True))
    student = db.relationship("Student", backref=db.backref("teacher_evaluations", lazy=True))

    @property
    def average(self):
        values = [self.punctuality, self.communication, self.explanation, self.motivation, self.progress]
        return round(sum(values) / len(values), 1)



class SubscriptionContract(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    contract_no = db.Column(db.String(40), unique=True, nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher.id"))
    service_name = db.Column(db.String(150), nullable=False)
    start_date = db.Column(db.Date, nullable=False, default=date.today)
    end_date = db.Column(db.Date)
    total_sessions = db.Column(db.Integer, default=0)
    weekly_sessions = db.Column(db.Integer, default=1)
    session_minutes = db.Column(db.Integer, default=30)
    contract_price = db.Column(db.Float, default=0)
    discount_amount = db.Column(db.Float, default=0)
    currency = db.Column(db.String(10), default="EGP")
    teacher_rate_per_session = db.Column(db.Float, default=0)
    teacher_rate_currency = db.Column(db.String(10), default="EGP")
    exchange_rate_to_egp = db.Column(db.Float, default=1)
    teacher_rate_mode = db.Column(db.String(30), default="fixed_egp")
    status = db.Column(db.String(20), default="نشط")
    frozen_from = db.Column(db.Date)
    frozen_to = db.Column(db.Date)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    student = db.relationship("Student", backref=db.backref("contracts", lazy=True))
    teacher = db.relationship("Teacher", backref=db.backref("contracts", lazy=True))

    @property
    def net_amount(self):
        return max((self.contract_price or 0) - (self.discount_amount or 0), 0)

    @property
    def paid_amount(self):
        return round(sum((p.amount or 0) for p in self.payments), 2)

    @property
    def balance(self):
        return round(self.net_amount - self.paid_amount, 2)


class ContractSchedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    contract_id = db.Column(db.Integer, db.ForeignKey("subscription_contract.id"), nullable=False)
    weekday = db.Column(db.Integer, nullable=False)  # 0=Monday
    start_time = db.Column(db.String(5), nullable=False)
    duration_minutes = db.Column(db.Integer, default=30)
    active = db.Column(db.Boolean, default=True)
    contract = db.relationship("SubscriptionContract", backref=db.backref("schedule_slots", lazy=True, cascade="all, delete-orphan"))

    @property
    def weekday_name(self):
        return ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"][self.weekday]


class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    receipt_no = db.Column(db.String(40), unique=True, nullable=False)
    contract_id = db.Column(db.Integer, db.ForeignKey("subscription_contract.id"), nullable=False)
    payment_date = db.Column(db.Date, nullable=False, default=date.today)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default="EGP")
    payment_method = db.Column(db.String(30), default="كاش")
    reference_no = db.Column(db.String(100))
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    contract = db.relationship("SubscriptionContract", backref=db.backref("payments", lazy=True, cascade="all, delete-orphan"))
    creator = db.relationship("User", foreign_keys=[created_by])


def next_number(prefix, model, field_name):
    year = date.today().year
    base = f"{prefix}-{year}-"
    field = getattr(model, field_name)
    latest = model.query.filter(field.like(base + "%")).order_by(model.id.desc()).first()
    if latest:
        try:
            seq = int(getattr(latest, field_name).split("-")[-1]) + 1
        except Exception:
            seq = latest.id + 1
    else:
        seq = 1
    return f"{base}{seq:05d}"


class Cashbox(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    currency = db.Column(db.String(10), default="EGP")
    opening_balance = db.Column(db.Float, default=0)
    active = db.Column(db.Boolean, default=True)
    notes = db.Column(db.Text)

    @property
    def current_balance(self):
        incoming = sum((t.amount or 0) for t in self.transactions if t.direction == "in")
        outgoing = sum((t.amount or 0) for t in self.transactions if t.direction == "out")
        return round((self.opening_balance or 0) + incoming - outgoing, 2)


class FinanceCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    kind = db.Column(db.String(20), nullable=False)  # income / expense
    active = db.Column(db.Boolean, default=True)


class FinanceTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tx_no = db.Column(db.String(40), unique=True, nullable=False)
    tx_date = db.Column(db.Date, default=date.today, nullable=False)
    cashbox_id = db.Column(db.Integer, db.ForeignKey("cashbox.id"), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("finance_category.id"))
    direction = db.Column(db.String(10), nullable=False)  # in / out
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default="EGP")
    source_type = db.Column(db.String(30), default="manual")  # payment, expense, teacher_salary, manual
    source_id = db.Column(db.Integer)
    description = db.Column(db.String(255))
    reference_no = db.Column(db.String(100))
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    cashbox = db.relationship("Cashbox", backref=db.backref("transactions", lazy=True))
    category = db.relationship("FinanceCategory", backref=db.backref("transactions", lazy=True))
    creator = db.relationship("User", foreign_keys=[created_by])


class TeacherSessionEarning(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher.id"), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey("lesson_session.id"))
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"))
    contract_id = db.Column(db.Integer, db.ForeignKey("subscription_contract.id"))
    earning_date = db.Column(db.Date, default=date.today, nullable=False)
    amount = db.Column(db.Float, nullable=False, default=0)
    currency = db.Column(db.String(10), default="EGP")
    status = db.Column(db.String(20), default="مستحق")  # مستحق / مرحل / مدفوع
    notes = db.Column(db.String(255))

    teacher = db.relationship("Teacher", backref=db.backref("earnings", lazy=True))
    session = db.relationship("LessonSession", backref=db.backref("teacher_earnings", lazy=True))
    student = db.relationship("Student", backref=db.backref("teacher_earnings", lazy=True))
    contract = db.relationship("SubscriptionContract", backref=db.backref("teacher_earnings", lazy=True))


class TeacherPayroll(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    payroll_no = db.Column(db.String(40), unique=True, nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher.id"), nullable=False)
    period_from = db.Column(db.Date, nullable=False)
    period_to = db.Column(db.Date, nullable=False)
    gross_amount = db.Column(db.Float, default=0)
    bonuses = db.Column(db.Float, default=0)
    deductions = db.Column(db.Float, default=0)
    net_amount = db.Column(db.Float, default=0)
    currency = db.Column(db.String(10), default="EGP")
    status = db.Column(db.String(20), default="مسودة")  # مسودة / معتمد / مدفوع
    paid_date = db.Column(db.Date)
    cashbox_id = db.Column(db.Integer, db.ForeignKey("cashbox.id"))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    teacher = db.relationship("Teacher", backref=db.backref("payrolls", lazy=True))
    cashbox = db.relationship("Cashbox", backref=db.backref("teacher_payrolls", lazy=True))


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    body = db.Column(db.Text, nullable=False)
    channel = db.Column(db.String(20), default="in_app")  # in_app / email / whatsapp
    status = db.Column(db.String(20), default="جديد")
    action_url = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    read_at = db.Column(db.DateTime)

    user = db.relationship("User", backref=db.backref("notifications", lazy=True))


class NotificationTemplate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(80), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    channel = db.Column(db.String(20), default="whatsapp")
    body = db.Column(db.Text, nullable=False)
    active = db.Column(db.Boolean, default=True)


class ContactMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(40), nullable=False)
    email = db.Column(db.String(150))
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default="جديد")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class TeacherPayment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    payment_no = db.Column(db.String(40), unique=True, nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher.id"), nullable=False)
    payment_date = db.Column(db.Date, default=date.today, nullable=False)
    period_from = db.Column(db.Date)
    period_to = db.Column(db.Date)
    amount = db.Column(db.Float, nullable=False, default=0)
    currency = db.Column(db.String(10), default="EGP")
    payment_method = db.Column(db.String(30), default="كاش")
    reference_no = db.Column(db.String(100))
    cashbox_id = db.Column(db.Integer, db.ForeignKey("cashbox.id"))
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    teacher = db.relationship("Teacher", backref=db.backref("payments_received", lazy=True))
    cashbox = db.relationship("Cashbox", backref=db.backref("teacher_payments", lazy=True))
    creator = db.relationship("User", foreign_keys=[created_by])


class QuranProgress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey("lesson_session.id"))
    progress_date = db.Column(db.Date, default=date.today, nullable=False)
    surah_name = db.Column(db.String(100), nullable=False)
    from_ayah = db.Column(db.Integer)
    to_ayah = db.Column(db.Integer)
    progress_type = db.Column(db.String(30), default="حفظ جديد")
    memorization_errors = db.Column(db.Integer, default=0)
    tajweed_errors = db.Column(db.Integer, default=0)
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"))

    student = db.relationship("Student", backref=db.backref("quran_progress", lazy=True))
    session = db.relationship("LessonSession", backref=db.backref("quran_progress", lazy=True))
    creator = db.relationship("User", foreign_keys=[created_by])


class CodeSequence(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    entity = db.Column(db.String(30), unique=True, nullable=False)
    prefix = db.Column(db.String(20), nullable=False)
    next_number = db.Column(db.Integer, nullable=False)
    padding = db.Column(db.Integer, default=4)


class ExchangeRate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    currency = db.Column(db.String(10), unique=True, nullable=False)
    rate_to_egp = db.Column(db.Float, nullable=False, default=1)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_by = db.Column(db.Integer, db.ForeignKey("user.id"))


class Complaint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    complaint_no = db.Column(db.String(40), unique=True, nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("parent.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher.id"), nullable=False)
    subject = db.Column(db.String(160), nullable=False)
    details = db.Column(db.Text, nullable=False)
    priority = db.Column(db.String(20), default="عادية")
    status = db.Column(db.String(30), default="جديدة")
    admin_response = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    closed_at = db.Column(db.DateTime)

    parent = db.relationship("Parent", backref=db.backref("complaints", lazy=True))
    student = db.relationship("Student", backref=db.backref("complaints", lazy=True))
    teacher = db.relationship("Teacher", backref=db.backref("complaints", lazy=True))


class TeacherChangeRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    request_no = db.Column(db.String(40), unique=True, nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("parent.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    current_teacher_id = db.Column(db.Integer, db.ForeignKey("teacher.id"), nullable=False)
    requested_teacher_id = db.Column(db.Integer, db.ForeignKey("teacher.id"))
    reason = db.Column(db.Text, nullable=False)
    preferred_times = db.Column(db.String(255))
    status = db.Column(db.String(30), default="جديد")
    admin_note = db.Column(db.Text)
    approved_teacher_id = db.Column(db.Integer, db.ForeignKey("teacher.id"))
    effective_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime)

    parent = db.relationship("Parent", backref=db.backref("teacher_change_requests", lazy=True))
    student = db.relationship("Student", backref=db.backref("teacher_change_requests", lazy=True))
    current_teacher = db.relationship("Teacher", foreign_keys=[current_teacher_id])
    requested_teacher = db.relationship("Teacher", foreign_keys=[requested_teacher_id])
    approved_teacher = db.relationship("Teacher", foreign_keys=[approved_teacher_id])



class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    action = db.Column(db.String(40), nullable=False)
    entity = db.Column(db.String(80))
    entity_id = db.Column(db.Integer)
    description = db.Column(db.String(255))
    endpoint = db.Column(db.String(120))
    ip_address = db.Column(db.String(64))
    user_agent = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    user = db.relationship("User", foreign_keys=[user_id])


class Permission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(80), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)


class RolePermission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(30), nullable=False, index=True)
    permission_id = db.Column(db.Integer, db.ForeignKey("permission.id"), nullable=False)
    permission = db.relationship("Permission")
    __table_args__ = (db.UniqueConstraint("role", "permission_id", name="uq_role_permission"),)

class UserPermission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    permission_id = db.Column(db.Integer, db.ForeignKey("permission.id"), nullable=False)
    allowed = db.Column(db.Boolean, nullable=False, default=True)
    user = db.relationship("User", backref=db.backref("permission_overrides", lazy=True, cascade="all, delete-orphan"))
    permission = db.relationship("Permission")
    __table_args__ = (db.UniqueConstraint("user_id", "permission_id", name="uq_user_permission"),)


class EvaluationQuestion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    evaluation_type = db.Column(db.String(20), nullable=False)  # student / teacher
    code = db.Column(db.String(60), nullable=False)
    label = db.Column(db.String(150), nullable=False)
    max_score = db.Column(db.Integer, default=5)
    sort_order = db.Column(db.Integer, default=0)
    active = db.Column(db.Boolean, default=True)
    required = db.Column(db.Boolean, default=True)
    __table_args__ = (db.UniqueConstraint("evaluation_type", "code", name="uq_eval_question"),)


class EvaluationAnswer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    evaluation_type = db.Column(db.String(20), nullable=False)
    evaluation_id = db.Column(db.Integer, nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey("evaluation_question.id"), nullable=False)
    score = db.Column(db.Float, default=0)
    question = db.relationship("EvaluationQuestion")
    __table_args__ = (db.UniqueConstraint("evaluation_type", "evaluation_id", "question_id", name="uq_eval_answer"),)


class ApprovalRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    request_no = db.Column(db.String(40), unique=True, nullable=False)
    request_type = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    details = db.Column(db.Text)
    status = db.Column(db.String(20), default="قيد المراجعة")
    requested_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    reviewed_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    review_note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime)
    requester = db.relationship("User", foreign_keys=[requested_by])
    reviewer = db.relationship("User", foreign_keys=[reviewed_by])


class Account(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    account_type = db.Column(db.String(30), nullable=False)
    active = db.Column(db.Boolean, default=True)


class JournalEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    entry_no = db.Column(db.String(40), unique=True, nullable=False)
    entry_date = db.Column(db.Date, default=date.today, nullable=False)
    description = db.Column(db.String(255), nullable=False)
    source_type = db.Column(db.String(50))
    source_id = db.Column(db.Integer)
    status = db.Column(db.String(20), default="مرحل")
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    creator = db.relationship("User", foreign_keys=[created_by])


class JournalLine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    entry_id = db.Column(db.Integer, db.ForeignKey("journal_entry.id"), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey("account.id"), nullable=False)
    debit = db.Column(db.Float, default=0)
    credit = db.Column(db.Float, default=0)
    currency = db.Column(db.String(10), default="EGP")
    memo = db.Column(db.String(255))
    entry = db.relationship("JournalEntry", backref=db.backref("lines", lazy=True, cascade="all, delete-orphan"))
    account = db.relationship("Account")


class ActivityTimeline(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False, index=True)
    activity_type = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    details = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    student = db.relationship("Student", backref=db.backref("timeline", lazy=True, cascade="all, delete-orphan"))
    creator = db.relationship("User", foreign_keys=[created_by])


class StudentDocument(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    document_type = db.Column(db.String(50), nullable=False)
    original_name = db.Column(db.String(255), nullable=False)
    stored_name = db.Column(db.String(255), nullable=False)
    notes = db.Column(db.Text)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    student = db.relationship("Student", backref=db.backref("documents", lazy=True, cascade="all, delete-orphan"))
    uploader = db.relationship("User", foreign_keys=[uploaded_by])


class BackgroundJob(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_type = db.Column(db.String(50), nullable=False)
    payload = db.Column(db.Text)
    status = db.Column(db.String(20), default="pending")
    attempts = db.Column(db.Integer, default=0)
    scheduled_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime)
    finished_at = db.Column(db.DateTime)
    error = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def roles_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if current_user.role not in {"admin", "developer"} and current_user.role not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator



def ensure_default_sequences():
    defaults = {
        "student": ("STU", 100, 4),
        "teacher": ("TCH", 200, 4),
        "parent": ("PAR", 300, 4),
    }
    for entity, (prefix, start, padding) in defaults.items():
        if not CodeSequence.query.filter_by(entity=entity).first():
            db.session.add(CodeSequence(entity=entity, prefix=prefix, next_number=start, padding=padding))
    db.session.commit()


def next_entity_code(entity):
    seq = CodeSequence.query.filter_by(entity=entity).first()
    if not seq:
        ensure_default_sequences()
        seq = CodeSequence.query.filter_by(entity=entity).first()
    code = f"{seq.prefix}-{seq.next_number:0{seq.padding}d}"
    seq.next_number += 1
    db.session.flush()
    return code


def next_student_code():
    return next_entity_code("student")


def next_teacher_code():
    return next_entity_code("teacher")


def next_parent_code():
    return next_entity_code("parent")

def parse_date(value):
    return datetime.strptime(value, "%Y-%m-%d").date() if value else None



def has_permission(code):
    if not current_user.is_authenticated:
        return False
    if current_user.role in {"admin", "developer"}:
        return True
    perm = Permission.query.filter_by(code=code).first()
    if not perm:
        return False
    override = UserPermission.query.filter_by(user_id=current_user.id, permission_id=perm.id).first()
    if override is not None:
        return bool(override.allowed)
    return RolePermission.query.filter_by(role=current_user.role, permission_id=perm.id).first() is not None

def permission_required(code):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not has_permission(code):
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


def can_access_student(student):
    if current_user.role in {"admin", "developer", "manager"}: return True
    if current_user.role == "parent": return bool(current_user.parent_profile and student.parent_id == current_user.parent_profile.id)
    if current_user.role == "teacher":
        return db.session.query(Enrollment.id).join(Circle).filter(Enrollment.student_id==student.id, Enrollment.active==True, Circle.teacher_id==current_user.teacher_profile.id).first() is not None
    return False

def can_access_session(session):
    if current_user.role in {"admin", "developer", "manager"}: return True
    if current_user.role == "teacher": return session.circle.teacher_id == current_user.teacher_profile.id
    if current_user.role == "parent":
        ids=[x.id for x in current_user.parent_profile.students]
        return db.session.query(Enrollment.id).filter(Enrollment.circle_id==session.circle_id, Enrollment.student_id.in_(ids), Enrollment.active==True).first() is not None
    return False

def audit(action, entity=None, entity_id=None, description=None):
    db.session.add(AuditLog(
        user_id=current_user.id if current_user.is_authenticated else None,
        action=action, entity=entity, entity_id=entity_id,
        description=description, endpoint=request.endpoint,
        ip_address=request.headers.get("X-Forwarded-For", request.remote_addr),
        user_agent=(request.user_agent.string or "")[:255],
    ))


def add_timeline(student_id, activity_type, title, details=None):
    db.session.add(ActivityTimeline(student_id=student_id, activity_type=activity_type,
                                    title=title, details=details,
                                    created_by=current_user.id if current_user.is_authenticated else None))


def get_account(code):
    return Account.query.filter_by(code=code).first()


def post_journal(description, source_type, source_id, lines, entry_date=None):
    if JournalEntry.query.filter_by(source_type=source_type, source_id=source_id).first():
        return None
    total_debit = round(sum(float(x.get("debit", 0)) for x in lines), 2)
    total_credit = round(sum(float(x.get("credit", 0)) for x in lines), 2)
    if total_debit != total_credit:
        raise ValueError("القيد المحاسبي غير متوازن")
    entry = JournalEntry(entry_no=next_number("JRN", JournalEntry, "entry_no"),
                         entry_date=entry_date or date.today(), description=description,
                         source_type=source_type, source_id=source_id,
                         created_by=current_user.id if current_user.is_authenticated else None)
    db.session.add(entry); db.session.flush()
    for line in lines:
        account = get_account(line["account"])
        if not account:
            raise ValueError("الحساب غير موجود: " + line["account"])
        db.session.add(JournalLine(entry_id=entry.id, account_id=account.id,
                                  debit=float(line.get("debit", 0)), credit=float(line.get("credit", 0)),
                                  currency=line.get("currency", "EGP"), memo=line.get("memo")))
    return entry


def queue_job(job_type, payload=None, scheduled_at=None):
    job = BackgroundJob(job_type=job_type, payload=json.dumps(payload or {}, ensure_ascii=False),
                        scheduled_at=scheduled_at or datetime.utcnow())
    db.session.add(job)
    return job


@app.after_request
def automatic_audit(response):
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and current_user.is_authenticated and response.status_code < 400:
        try:
            audit(request.method, description=f"عملية على {request.path}")
            db.session.commit()
        except Exception:
            db.session.rollback()
    return response


@app.context_processor
def inject_notification_count():
    if current_user.is_authenticated:
        unread_notifications = Notification.query.filter_by(user_id=current_user.id, read_at=None).count()
    else:
        unread_notifications = 0
    return {"unread_notifications": unread_notifications, "can": has_permission}


def create_notification(user_id, title, body, action_url=None, channel="in_app"):
    n = Notification(
        user_id=user_id,
        title=title,
        body=body,
        action_url=action_url,
        channel=channel,
    )
    db.session.add(n)
    return n


def whatsapp_link(phone, message):
    cleaned = "".join(ch for ch in (phone or "") if ch.isdigit())
    return f"https://wa.me/{cleaned}?text={urllib.parse.quote(message)}"


def render_template_text(code, context):
    tpl = NotificationTemplate.query.filter_by(code=code, active=True).first()
    if not tpl:
        return ""
    text = tpl.body
    for key, value in context.items():
        text = text.replace("{{" + key + "}}", str(value))
    return text

def get_setting(key, default=None):
    row = SystemSetting.query.filter_by(key=key).first()
    return row.value if row and row.value not in (None, "") else default

def set_setting(key, value):
    row = SystemSetting.query.filter_by(key=key).first()
    if not row:
        row = SystemSetting(key=key); db.session.add(row)
    row.value = value

def management_role():
    return current_user.is_authenticated and current_user.role in {"admin", "developer", "manager"}

def _password_serializer():
    return URLSafeTimedSerializer(app.config["SECRET_KEY"], salt="password-reset")

def send_reset_email(user, reset_url):
    host = get_setting("SMTP_HOST", os.environ.get("SMTP_HOST"))
    if not host:
        app.logger.warning("Password reset URL for %s: %s", user.email, reset_url)
        return False
    msg = EmailMessage()
    msg["Subject"] = "إعادة تعيين كلمة المرور - أكاديمية المودة"
    msg["From"] = get_setting("SMTP_FROM", get_setting("SMTP_USER", os.environ.get("SMTP_FROM", os.environ.get("SMTP_USER", "no-reply@mawadda.local"))))
    msg["To"] = user.email
    msg.set_content(f"مرحبًا {user.full_name}،\n\nاستخدم الرابط التالي لتعيين كلمة مرور جديدة. الرابط صالح لمدة 30 دقيقة:\n{reset_url}\n\nإذا لم تطلب ذلك فتجاهل الرسالة.")
    port = int(get_setting("SMTP_PORT", os.environ.get("SMTP_PORT", "587")))
    with smtplib.SMTP(host, port, timeout=15) as server:
        if get_setting("SMTP_TLS", os.environ.get("SMTP_TLS", "1")) == "1": server.starttls()
        username = get_setting("SMTP_USER", os.environ.get("SMTP_USER"))
        if username: server.login(username, get_setting("SMTP_PASSWORD", os.environ.get("SMTP_PASSWORD", "")))
        server.send_message(msg)
    return True

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = User.query.filter_by(email=email, is_active_user=True).first()
        if user:
            token = _password_serializer().dumps({"uid": user.id, "pwd": user.password_hash[-16:]})
            reset_url = url_for("reset_password", token=token, _external=True)
            try:
                delivered = send_reset_email(user, reset_url)
                if not delivered and app.debug:
                    flash("وضع التطوير: رابط إعادة التعيين: " + reset_url, "warning")
            except Exception:
                app.logger.exception("Unable to send password reset email")
        flash("إذا كان البريد مسجلًا فستصلك رسالة إعادة التعيين خلال دقائق.", "success")
        return redirect(url_for("login"))
    return render_template("forgot_password.html")

@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    try:
        data = _password_serializer().loads(token, max_age=1800)
        user = db.session.get(User, int(data["uid"]))
        if not user or data.get("pwd") != user.password_hash[-16:]: raise BadSignature("used")
    except SignatureExpired:
        flash("رابط إعادة التعيين انتهت صلاحيته. اطلب رابطًا جديدًا.", "danger")
        return redirect(url_for("forgot_password"))
    except Exception:
        flash("رابط إعادة التعيين غير صالح أو تم استخدامه سابقًا.", "danger")
        return redirect(url_for("forgot_password"))
    if request.method == "POST":
        password = request.form.get("password", "")
        if len(password) < 8 or not any(c.isdigit() for c in password) or not any(c.isalpha() for c in password):
            flash("كلمة المرور يجب ألا تقل عن 8 أحرف وتحتوي حروفًا وأرقامًا.", "danger")
        elif password != request.form.get("confirm_password"):
            flash("تأكيد كلمة المرور غير مطابق.", "danger")
        else:
            user.set_password(password); db.session.commit()
            flash("تم تغيير كلمة المرور. يمكنك تسجيل الدخول الآن.", "success")
            return redirect(url_for("login"))
    return render_template("reset_password.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password) and user.is_active:
            login_user(user)
            return redirect(url_for("dashboard"))
        flash("بيانات الدخول غير صحيحة.", "danger")
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def dashboard():
    today = date.today()
    if current_user.role == "parent":
        parent = current_user.parent_profile
        student_ids = [x.id for x in parent.students]
        upcoming = LessonSession.query.join(Circle).join(Enrollment, Enrollment.circle_id == Circle.id).filter(
            Enrollment.student_id.in_(student_ids), LessonSession.session_date >= today
        ).order_by(LessonSession.session_date, LessonSession.start_time).limit(8).all() if student_ids else []
        return render_template("dashboard_parent.html", students=parent.students, upcoming=upcoming)
    if current_user.role == "accountant":
        return redirect(url_for("finance_dashboard"))
    if current_user.role == "teacher":
        teacher = current_user.teacher_profile
        recent_sessions = LessonSession.query.join(Circle).filter(Circle.teacher_id == teacher.id).order_by(
            LessonSession.session_date.desc(), LessonSession.id.desc()).limit(8).all()
        due = sum(e.amount for e in TeacherSessionEarning.query.filter_by(teacher_id=teacher.id).filter(TeacherSessionEarning.status != "مدفوع"))
        return render_template("dashboard_teacher.html", teacher=teacher, recent_sessions=recent_sessions, due=round(due,2))
    stats = {
        "students": Student.query.filter_by(active=True).count(), "teachers": Teacher.query.count(),
        "parents": Parent.query.count(), "circles": Circle.query.filter_by(active=True).count(),
        "sessions_today": LessonSession.query.filter_by(session_date=today).count(),
        "open_complaints": Complaint.query.filter(Complaint.status != "مغلقة").count(),
        "receivables": round(sum(max(c.balance, 0) for c in SubscriptionContract.query.all()), 2),
        "teacher_due": round(sum(e.amount for e in TeacherSessionEarning.query.filter(TeacherSessionEarning.status != "مدفوع").all()), 2),
    }
    recent_sessions = LessonSession.query.order_by(LessonSession.session_date.desc(), LessonSession.id.desc()).limit(8).all()
    months=[]; income=[]; expenses=[]
    for offset in range(5,-1,-1):
        y=today.year; m=today.month-offset
        while m<=0: y-=1; m+=12
        start=date(y,m,1); end=date(y+1,1,1)-timedelta(days=1) if m==12 else date(y,m+1,1)-timedelta(days=1)
        txs=FinanceTransaction.query.filter(FinanceTransaction.tx_date>=start, FinanceTransaction.tx_date<=end).all()
        months.append(start.strftime("%Y-%m")); income.append(round(sum(t.amount for t in txs if t.direction=="in"),2)); expenses.append(round(sum(t.amount for t in txs if t.direction=="out"),2))
    student_scores=[]
    for st in Student.query.filter_by(active=True).all():
        vals=[e.average for e in st.evaluations if e.average is not None]
        if vals: student_scores.append((st, round(sum(vals)/len(vals),2)))
    teacher_scores=[]
    for t in Teacher.query.all():
        vals=[e.average for e in t.parent_evaluations if e.average is not None]
        mgr=[e.score for e in ManagerEvaluation.query.filter_by(target_type="teacher", teacher_id=t.id).all()]
        allv=vals+mgr
        if allv: teacher_scores.append((t, round(sum(allv)/len(allv),2)))
    best_student=max(student_scores,key=lambda x:x[1]) if student_scores else None
    best_teacher=max(teacher_scores,key=lambda x:x[1]) if teacher_scores else None
    return render_template("dashboard.html", stats=stats, recent_sessions=recent_sessions, chart_months=months, chart_income=income, chart_expenses=expenses, best_student=best_student, best_teacher=best_teacher)


@app.route("/students")
@login_required
@permission_required("students.view")
def students():
    if current_user.role == "parent":
        items = current_user.parent_profile.students
    elif current_user.role == "teacher":
        tid = current_user.teacher_profile.id
        items = Student.query.join(Enrollment).join(Circle).filter(Circle.teacher_id == tid, Enrollment.active == True).distinct().all()
    else:
        items = Student.query.order_by(Student.full_name).all()
    return render_template("students.html", students=items)


@app.route("/students/new", methods=["GET", "POST"])
@login_required
@roles_required("admin", "developer", "manager")
def student_new():
    parents = Parent.query.join(User).order_by(User.full_name).all()
    if request.method == "POST":
        code = next_student_code()
        if Student.query.filter_by(student_code=code).first():
            flash("كود الطالب مستخدم بالفعل.", "danger")
        else:
            student = Student(
                student_code=code,
                full_name=request.form["full_name"].strip(),
                birth_date=parse_date(request.form.get("birth_date")),
                gender=request.form.get("gender"),
                country=request.form.get("country"),
                level=request.form.get("level"),
                notes=request.form.get("notes"),
                parent_id=int(request.form["parent_id"]),
            )
            db.session.add(student)
            db.session.flush()
            try:
                student.photo = _save_profile_photo(request.files.get("photo"), f"student_{student.id}")
            except ValueError as exc:
                db.session.rollback(); flash(str(exc), "danger")
                return render_template("student_form.html", parents=parents)
            add_timeline(student.id, "registration", "تسجيل الطالب", f"تم إنشاء الطالب بالكود {student.student_code}")
            db.session.commit()
            flash("تم إضافة الطالب.", "success")
            return redirect(url_for("students"))
    return render_template("student_form.html", parents=parents)


@app.route("/students/<int:student_id>")
@login_required
def student_profile(student_id):
    student = db.get_or_404(Student, student_id)
    if not can_access_student(student): abort(403)
    if current_user.role == "teacher":
        allowed = Enrollment.query.join(Circle).filter(
            Enrollment.student_id == student.id,
            Circle.teacher_id == current_user.teacher_profile.id,
            Enrollment.active == True
        ).first()
        if not allowed:
            abort(403)
    evaluations = StudentEvaluation.query.filter_by(student_id=student.id).order_by(StudentEvaluation.created_at.desc()).all()
    attendance = Attendance.query.filter_by(student_id=student.id).order_by(Attendance.id.desc()).limit(30).all()
    return render_template("student_profile.html", student=student, evaluations=evaluations, attendance=attendance)


@app.route("/students/<int:student_id>/edit", methods=["GET", "POST"])
@login_required
def student_edit(student_id):
    student = db.get_or_404(Student, student_id)
    if current_user.role not in {"admin", "developer", "manager"}:
        if current_user.role != "parent" or not current_user.parent_profile or student.parent_id != current_user.parent_profile.id:
            abort(403)
    parents = Parent.query.join(User).order_by(User.full_name).all()
    if request.method == "POST":
        student.full_name = request.form.get("full_name", student.full_name).strip()
        student.birth_date = parse_date(request.form.get("birth_date"))
        student.gender = request.form.get("gender")
        student.country = request.form.get("country")
        student.level = request.form.get("level")
        student.notes = request.form.get("notes")
        if current_user.role in {"admin", "developer", "manager"} and request.form.get("parent_id"):
            student.parent_id = int(request.form.get("parent_id"))
        try:
            stored = _save_profile_photo(request.files.get("photo"), f"student_{student.id}")
            if stored: student.photo = stored
        except ValueError as exc:
            flash(str(exc), "danger"); return redirect(request.url)
        if request.form.get("remove_photo"): student.photo = None
        db.session.commit(); flash("تم تحديث بروفايل الطالب.", "success")
        return redirect(url_for("student_profile", student_id=student.id))
    return render_template("student_edit.html", student=student, parents=parents)

@app.route("/parents")
@login_required
@roles_required("admin", "developer", "manager")
def parents():
    return render_template("parents.html", parents=Parent.query.join(User).order_by(User.full_name).all())


@app.route("/parents/new", methods=["GET", "POST"])
@login_required
@roles_required("admin", "developer", "manager")
def parent_new():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        if User.query.filter_by(email=email).first():
            flash("البريد مستخدم بالفعل.", "danger")
        else:
            user = User(
                full_name=request.form["full_name"].strip(),
                email=email,
                phone=request.form.get("phone"),
                whatsapp=request.form.get("whatsapp"),
                role="parent",
            )
            user.set_password(request.form["password"])
            db.session.add(user)
            db.session.flush()
            user.photo = _save_profile_photo(request.files.get("photo"), f"user_{user.id}")
            db.session.add(Parent(user_id=user.id, parent_code=next_parent_code(), address=request.form.get("address"), country=request.form.get("country")))
            db.session.commit()
            flash("تم إضافة ولي الأمر.", "success")
            return redirect(url_for("parents"))
    return render_template("parent_form.html")


@app.route("/teachers")
@login_required
@permission_required("teachers.view")
def teachers():
    query = Teacher.query.join(User)
    if current_user.role == "parent":
        allowed_ids = {e.circle.teacher_id for st in current_user.parent_profile.students for e in st.enrollments if e.active}
        query = query.filter(Teacher.id.in_(allowed_ids)) if allowed_ids else query.filter(db.false())
    elif current_user.role == "teacher":
        query = query.filter(Teacher.id == current_user.teacher_profile.id)
    return render_template("teachers.html", teachers=query.order_by(User.full_name).all())


@app.route("/teachers/new", methods=["GET", "POST"])
@login_required
@roles_required("admin", "developer", "manager")
def teacher_new():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        if User.query.filter_by(email=email).first():
            flash("البريد مستخدم بالفعل.", "danger")
        else:
            user = User(
                full_name=request.form["full_name"].strip(),
                email=email,
                phone=request.form.get("phone"),
                whatsapp=request.form.get("whatsapp"),
                role="teacher",
            )
            user.set_password(request.form["password"])
            db.session.add(user)
            db.session.flush()
            user.photo = _save_profile_photo(request.files.get("photo"), f"user_{user.id}")
            teacher = Teacher(
                user_id=user.id,
                employee_code=next_teacher_code(),
                specialization=request.form.get("specialization"),
                bio=request.form.get("bio"),
                join_date=parse_date(request.form.get("join_date")) or date.today(),
            )
            db.session.add(teacher)
            db.session.commit()
            flash("تم إضافة المعلم.", "success")
            return redirect(url_for("teachers"))
    return render_template("teacher_form.html")


@app.route("/circles")
@login_required
@permission_required("sessions.view")
def circles():
    if current_user.role == "teacher":
        items = Circle.query.filter_by(teacher_id=current_user.teacher_profile.id).all()
    else:
        items = Circle.query.order_by(Circle.name).all()
    return render_template("circles.html", circles=items)


@app.route("/circles/new", methods=["GET", "POST"])
@login_required
@roles_required("admin", "developer", "manager")
def circle_new():
    teachers = Teacher.query.join(User).order_by(User.full_name).all()
    if request.method == "POST":
        circle = Circle(
            name=request.form["name"].strip(),
            teacher_id=int(request.form["teacher_id"]),
            study_type=request.form.get("study_type"),
            default_minutes=int(request.form.get("default_minutes", 30)),
            schedule_text=request.form.get("schedule_text"),
        )
        db.session.add(circle)
        db.session.commit()
        flash("تم إنشاء الحلقة.", "success")
        return redirect(url_for("circles"))
    return render_template("circle_form.html", teachers=teachers)


@app.route("/enrollments/new", methods=["GET", "POST"])
@login_required
@roles_required("admin", "developer", "manager")
def enrollment_new():
    students = Student.query.filter_by(active=True).order_by(Student.full_name).all()
    circles = Circle.query.filter_by(active=True).order_by(Circle.name).all()
    if request.method == "POST":
        enrollment = Enrollment(
            student_id=int(request.form["student_id"]),
            circle_id=int(request.form["circle_id"]),
            start_date=parse_date(request.form.get("start_date")) or date.today(),
        )
        db.session.add(enrollment)
        db.session.commit()
        flash("تم ربط الطالب بالحلقة.", "success")
        return redirect(url_for("circles"))
    return render_template("enrollment_form.html", students=students, circles=circles)


@app.route("/sessions")
@login_required
@permission_required("sessions.view")
def sessions():
    query = LessonSession.query.join(Circle)
    if current_user.role == "teacher":
        query = query.filter(Circle.teacher_id == current_user.teacher_profile.id)
    elif current_user.role == "parent":
        student_ids = [s.id for s in current_user.parent_profile.students]
        circle_ids = [e.circle_id for e in Enrollment.query.filter(Enrollment.student_id.in_(student_ids), Enrollment.active == True).all()]
        query = query.filter(Circle.id.in_(circle_ids)) if circle_ids else query.filter(False)
    items = query.order_by(LessonSession.session_date.desc(), LessonSession.id.desc()).all()
    return render_template("sessions.html", sessions=items)


@app.route("/sessions/new", methods=["GET", "POST"])
@login_required
@roles_required("admin", "developer", "manager", "teacher")
def session_new():
    if current_user.role == "teacher":
        circles = Circle.query.filter_by(teacher_id=current_user.teacher_profile.id, active=True).all()
    else:
        circles = Circle.query.filter_by(active=True).all()
    if request.method == "POST":
        circle = db.get_or_404(Circle, int(request.form["circle_id"]))
        if current_user.role == "teacher" and circle.teacher_id != current_user.teacher_profile.id:
            abort(403)
        session = LessonSession(
            circle_id=circle.id,
            session_date=parse_date(request.form.get("session_date")) or date.today(),
            start_time=request.form.get("start_time"),
            duration_minutes=int(request.form.get("duration_minutes") or circle.default_minutes),
            topic=request.form.get("topic"),
            status=request.form.get("status", "مجدولة"),
            notes=request.form.get("notes"),
        )
        db.session.add(session)
        db.session.commit()
        flash("تم إنشاء الحصة.", "success")
        return redirect(url_for("session_detail", session_id=session.id))
    return render_template("session_form.html", circles=circles)


@app.route("/sessions/<int:session_id>", methods=["GET", "POST"])
@login_required
def session_detail(session_id):
    session = db.get_or_404(LessonSession, session_id)
    if not can_access_session(session): abort(403)
    enrolled = [e.student for e in session.circle.enrollments if e.active]
    attendance_map = {a.student_id: a for a in session.attendance_records}
    evaluation_map = {e.student_id: e for e in session.evaluations}

    if request.method == "POST":
        if current_user.role not in ("admin", "developer", "manager", "teacher"):
            abort(403)
        for student in enrolled:
            status = request.form.get(f"attendance_{student.id}", "حاضر")
            note = request.form.get(f"attendance_note_{student.id}", "")
            record = Attendance.query.filter_by(session_id=session.id, student_id=student.id).first()
            if not record:
                record = Attendance(session_id=session.id, student_id=student.id)
                db.session.add(record)
            record.status = status
            record.notes = note
        session.status = "تمت"
        db.session.commit()
        flash("تم حفظ الحضور.", "success")
        return redirect(url_for("session_detail", session_id=session.id))

    return render_template(
        "session_detail.html",
        session=session,
        enrolled=enrolled,
        attendance_map=attendance_map,
        evaluation_map=evaluation_map,
    )


@app.route("/evaluations/student/<int:session_id>/<int:student_id>", methods=["GET", "POST"])
@login_required
@permission_required("sessions.manage")
def student_evaluation_form(session_id, student_id):
    session=db.get_or_404(LessonSession,session_id); student=db.get_or_404(Student,student_id)
    if current_user.role=="teacher" and session.circle.teacher_id!=current_user.teacher_profile.id: abort(403)
    evaluation=StudentEvaluation.query.filter_by(session_id=session.id,student_id=student.id).first()
    questions=EvaluationQuestion.query.filter_by(evaluation_type="student",active=True).order_by(EvaluationQuestion.sort_order).all()
    answers={}
    if evaluation:
        answers={a.question_id:a.score for a in EvaluationAnswer.query.filter_by(evaluation_type="student",evaluation_id=evaluation.id).all()}
    if request.method=="POST":
        if not evaluation:
            evaluation=StudentEvaluation(session_id=session.id,student_id=student.id,teacher_id=session.circle.teacher_id); db.session.add(evaluation); db.session.flush()
        legacy={"memorization","revision","tajweed","pronunciation","focus"}
        for q in questions:
            score=max(0,min(q.max_score,float(request.form.get(f"q_{q.id}",0) or 0)))
            if q.code in legacy: setattr(evaluation,q.code,int(score))
            ans=EvaluationAnswer.query.filter_by(evaluation_type="student",evaluation_id=evaluation.id,question_id=q.id).first()
            if not ans: ans=EvaluationAnswer(evaluation_type="student",evaluation_id=evaluation.id,question_id=q.id); db.session.add(ans)
            ans.score=score
        evaluation.homework_done=bool(request.form.get("homework_done")); evaluation.lesson_covered=request.form.get("lesson_covered"); evaluation.homework=request.form.get("homework"); evaluation.parent_note=request.form.get("parent_note")
        create_notification(student.parent.user.id,"تقرير حصة جديد",f"تم إضافة تقييم جديد للطالب {student.full_name} عن حصة {session.session_date}.",url_for("student_profile",student_id=student.id))
        db.session.commit(); flash("تم حفظ تقييم الطالب وإشعار ولي الأمر.","success"); return redirect(url_for("session_detail",session_id=session.id))
    return render_template("student_evaluation_form.html",session=session,student=student,evaluation=evaluation,questions=questions,answers=answers)


@app.route("/evaluations/teacher/new", methods=["GET", "POST"])
@login_required
@roles_required("parent")
def teacher_evaluation_new():
    parent=current_user.parent_profile; students=parent.students
    teacher_ids={e.circle.teacher_id for st in students for e in st.enrollments if e.active}
    teachers=Teacher.query.filter(Teacher.id.in_(teacher_ids)).all() if teacher_ids else []
    questions=EvaluationQuestion.query.filter_by(evaluation_type="teacher",active=True).order_by(EvaluationQuestion.sort_order).all()
    if request.method=="POST":
        student=db.get_or_404(Student,int(request.form["student_id"])); teacher_id=int(request.form["teacher_id"])
        if student.parent_id!=parent.id or teacher_id not in teacher_ids: abort(403)
        evaluation=TeacherEvaluation(parent_id=parent.id,teacher_id=teacher_id,student_id=student.id,comment=request.form.get("comment"),private_to_admin=bool(request.form.get("private_to_admin")))
        db.session.add(evaluation); db.session.flush(); legacy={"punctuality","communication","explanation","motivation","progress"}
        for q in questions:
            score=max(0,min(q.max_score,float(request.form.get(f"q_{q.id}",0) or 0)))
            if q.code in legacy: setattr(evaluation,q.code,int(score))
            db.session.add(EvaluationAnswer(evaluation_type="teacher",evaluation_id=evaluation.id,question_id=q.id,score=score))
        db.session.commit(); flash("شكرًا، تم إرسال تقييم المعلم.","success"); return redirect(url_for("dashboard"))
    return render_template("teacher_evaluation_form.html",students=students,teachers=teachers,questions=questions)


@app.route("/contracts")
@login_required
@permission_required("contracts.view")
def contracts():
    query = SubscriptionContract.query
    if current_user.role == "parent":
        student_ids = [s.id for s in current_user.parent_profile.students]
        query = query.filter(SubscriptionContract.student_id.in_(student_ids)) if student_ids else query.filter(False)
    elif current_user.role == "teacher":
        query = query.filter_by(teacher_id=current_user.teacher_profile.id)
    items = query.order_by(SubscriptionContract.created_at.desc()).all()
    return render_template("contracts.html", contracts=items)


@app.route("/contracts/new", methods=["GET", "POST"])
@login_required
@roles_required("admin", "developer", "manager")
def contract_new():
    students = Student.query.filter_by(active=True).order_by(Student.full_name).all()
    teachers = Teacher.query.join(User).filter(User.is_active_user == True).order_by(User.full_name).all()
    if request.method == "POST":
        contract = SubscriptionContract(
            contract_no=next_number("CNT", SubscriptionContract, "contract_no"),
            student_id=int(request.form["student_id"]),
            teacher_id=int(request.form["teacher_id"]) if request.form.get("teacher_id") else None,
            service_name=request.form["service_name"].strip(),
            start_date=parse_date(request.form.get("start_date")) or date.today(),
            end_date=parse_date(request.form.get("end_date")),
            total_sessions=int(request.form.get("total_sessions") or 0),
            weekly_sessions=int(request.form.get("weekly_sessions") or 1),
            session_minutes=int(request.form.get("session_minutes") or 30),
            contract_price=float(request.form.get("contract_price") or 0),
            discount_amount=float(request.form.get("discount_amount") or 0),
            currency=request.form.get("currency") or "EGP",
            teacher_rate_per_session=float(request.form.get("teacher_rate_per_session") or 0),
            teacher_rate_currency=request.form.get("teacher_rate_currency") or "EGP",
            exchange_rate_to_egp=float(request.form.get("exchange_rate_to_egp") or 1),
            teacher_rate_mode=request.form.get("teacher_rate_mode") or "fixed_egp",
            status=request.form.get("status") or "نشط",
            notes=request.form.get("notes"),
        )
        weekdays = request.form.getlist("schedule_weekday")
        times = request.form.getlist("schedule_time")
        requested_weekly = contract.weekly_sessions or 1
        slots = [(int(d), t) for d, t in zip(weekdays, times) if d != "" and t]
        if len(slots) != requested_weekly:
            flash(f"يجب إدخال {requested_weekly} موعد أسبوعي بالضبط.", "danger")
            return render_template("contract_form.html", students=students, teachers=teachers)
        if len(set(slots)) != len(slots):
            flash("لا يمكن تكرار نفس اليوم والوقت داخل الاتفاق.", "danger")
            return render_template("contract_form.html", students=students, teachers=teachers)
        for weekday, start_time in slots:
            if contract.teacher_id:
                conflict = ContractSchedule.query.join(SubscriptionContract).filter(
                    SubscriptionContract.teacher_id == contract.teacher_id,
                    SubscriptionContract.status == "نشط",
                    ContractSchedule.weekday == weekday,
                    ContractSchedule.start_time == start_time,
                    ContractSchedule.active == True
                ).first()
                if conflict:
                    flash(f"المعلم مرتبط بالفعل بموعد {conflict.weekday_name} الساعة {start_time}.", "danger")
                    return render_template("contract_form.html", students=students, teachers=teachers)
        db.session.add(contract)
        db.session.flush()
        for weekday, start_time in slots:
            db.session.add(ContractSchedule(contract_id=contract.id, weekday=weekday, start_time=start_time, duration_minutes=contract.session_minutes))
        db.session.commit()
        flash("تم إنشاء عقد الاشتراك وجدوله الأسبوعي.", "success")
        return redirect(url_for("contract_detail", contract_id=contract.id))
    return render_template("contract_form.html", students=students, teachers=teachers)


@app.route("/contracts/<int:contract_id>/schedule", methods=["GET", "POST"])
@login_required
@roles_required("admin", "developer", "manager")
def contract_schedule_edit(contract_id):
    contract = db.get_or_404(SubscriptionContract, contract_id)
    if request.method == "POST":
        total_sessions = max(1, int(request.form.get("total_sessions") or contract.total_sessions or 1))
        weekly_sessions = max(1, min(7, int(request.form.get("weekly_sessions") or 1)))
        weekdays = request.form.getlist("schedule_weekday")
        times = request.form.getlist("schedule_time")
        slots = [(int(d), t) for d, t in zip(weekdays, times) if d != "" and t]
        if len(slots) != weekly_sessions:
            flash(f"يجب إدخال {weekly_sessions} موعد أسبوعي بالضبط.", "danger")
        elif len(set(slots)) != len(slots):
            flash("لا يمكن تكرار نفس اليوم والوقت.", "danger")
        else:
            conflict_found = None
            for weekday, start_time in slots:
                if contract.teacher_id:
                    conflict_found = ContractSchedule.query.join(SubscriptionContract).filter(
                        SubscriptionContract.teacher_id == contract.teacher_id,
                        SubscriptionContract.id != contract.id,
                        SubscriptionContract.status == "نشط",
                        ContractSchedule.weekday == weekday,
                        ContractSchedule.start_time == start_time,
                        ContractSchedule.active == True
                    ).first()
                    if conflict_found: break
            if conflict_found:
                flash(f"المعلم مرتبط بالفعل بموعد {conflict_found.weekday_name} الساعة {conflict_found.start_time}.", "danger")
            else:
                contract.total_sessions = total_sessions
                contract.weekly_sessions = weekly_sessions
                ContractSchedule.query.filter_by(contract_id=contract.id).delete()
                for weekday, start_time in slots:
                    db.session.add(ContractSchedule(contract_id=contract.id, weekday=weekday, start_time=start_time, duration_minutes=contract.session_minutes))
                db.session.commit()
                flash("تم تحديث عدد الحصص والجدول الأسبوعي.", "success")
                return redirect(url_for("contract_detail", contract_id=contract.id))
    return render_template("contract_schedule_form.html", contract=contract)

@app.route("/contracts/<int:contract_id>")
@login_required
@permission_required("contracts.view")
def contract_detail(contract_id):
    contract = db.get_or_404(SubscriptionContract, contract_id)
    if current_user.role == "parent" and contract.student.parent_id != current_user.parent_profile.id:
        abort(403)
    if current_user.role == "teacher" and contract.teacher_id != current_user.teacher_profile.id:
        abort(403)
    return render_template("contract_detail.html", contract=contract)


@app.route("/contracts/<int:contract_id>/payment", methods=["GET", "POST"])
@login_required
@roles_required("admin", "developer", "manager")
def payment_new(contract_id):
    contract = db.get_or_404(SubscriptionContract, contract_id)
    if request.method == "POST":
        amount = float(request.form.get("amount") or 0)
        if amount <= 0:
            flash("قيمة الدفعة يجب أن تكون أكبر من صفر.", "danger")
        else:
            payment = Payment(
                receipt_no=next_number("REC", Payment, "receipt_no"),
                contract_id=contract.id,
                payment_date=parse_date(request.form.get("payment_date")) or date.today(),
                amount=amount,
                currency=request.form.get("currency") or contract.currency,
                payment_method=request.form.get("payment_method") or "كاش",
                reference_no=request.form.get("reference_no"),
                notes=request.form.get("notes"),
                created_by=current_user.id,
            )
            db.session.add(payment)
            db.session.flush()
            cashbox_id = request.form.get("cashbox_id")
            if cashbox_id:
                income_cat = FinanceCategory.query.filter_by(kind="income").first()
                tx = FinanceTransaction(
                    tx_no=next_number("TX", FinanceTransaction, "tx_no"),
                    tx_date=payment.payment_date,
                    cashbox_id=int(cashbox_id),
                    category_id=income_cat.id if income_cat else None,
                    direction="in",
                    amount=payment.amount,
                    currency=payment.currency,
                    source_type="payment",
                    source_id=payment.id,
                    description=f"دفعة اشتراك {contract.contract_no} - {contract.student.full_name}",
                    reference_no=payment.reference_no,
                    created_by=current_user.id,
                )
                db.session.add(tx)
            amount_egp = round(payment.amount * (ExchangeRate.query.filter_by(currency=payment.currency).first().rate_to_egp if ExchangeRate.query.filter_by(currency=payment.currency).first() else 1), 2)
            post_journal(f"تحصيل اشتراك {contract.contract_no}", "payment", payment.id, [
                {"account": "1000", "debit": amount_egp, "currency": "EGP"},
                {"account": "4000", "credit": amount_egp, "currency": "EGP"},
            ], payment.payment_date)
            add_timeline(contract.student_id, "payment", "تسجيل دفعة", f"{payment.amount} {payment.currency} - {payment.receipt_no}")
            db.session.commit()
            flash("تم تسجيل الدفعة وترحيل القيد المحاسبي.", "success")
            return redirect(url_for("contract_detail", contract_id=contract.id))
    cashboxes = Cashbox.query.filter_by(active=True, currency=contract.currency).all()
    return render_template("payment_form.html", contract=contract, cashboxes=cashboxes)


@app.post("/users/<int:user_id>/toggle-active")
@login_required
@roles_required("admin", "developer", "manager")
def toggle_user_active(user_id):
    user = db.get_or_404(User, user_id)
    if user.id == current_user.id:
        flash("لا يمكنك تعطيل حسابك الحالي.", "danger")
        return redirect(request.referrer or url_for("dashboard"))
    if user.role not in ("teacher", "parent"):
        abort(403)
    user.is_active_user = not user.is_active_user
    db.session.commit()
    flash("تم تفعيل الحساب." if user.is_active_user else "تم تعطيل الحساب ومنع تسجيل الدخول.", "success")
    return redirect(request.referrer or url_for("dashboard"))


@app.route("/finance")
@login_required
@roles_required("admin", "developer", "manager", "accountant")
def finance_dashboard():
    cashboxes = Cashbox.query.filter_by(active=True).all()
    today = date.today()
    month_start = today.replace(day=1)
    month_tx = FinanceTransaction.query.filter(FinanceTransaction.tx_date >= month_start, FinanceTransaction.tx_date <= today).all()
    income = round(sum(t.amount for t in month_tx if t.direction == "in"), 2)
    expense = round(sum(t.amount for t in month_tx if t.direction == "out"), 2)
    pending_teacher = round(sum(e.amount for e in TeacherSessionEarning.query.filter(TeacherSessionEarning.status != "مدفوع").all()), 2)
    return render_template("finance_dashboard.html", cashboxes=cashboxes, income=income, expense=expense, net=round(income-expense,2), pending_teacher=pending_teacher)


@app.route("/cashboxes")
@login_required
@roles_required("admin", "developer", "manager", "accountant")
def cashboxes():
    return render_template("cashboxes.html", cashboxes=Cashbox.query.order_by(Cashbox.name).all())


@app.route("/cashboxes/new", methods=["GET", "POST"])
@login_required
@roles_required("admin", "developer", "manager", "accountant")
def cashbox_new():
    if request.method == "POST":
        box = Cashbox(
            name=request.form["name"].strip(),
            currency=request.form.get("currency") or "EGP",
            opening_balance=float(request.form.get("opening_balance") or 0),
            notes=request.form.get("notes"),
        )
        db.session.add(box)
        db.session.commit()
        flash("تم إنشاء الخزنة.", "success")
        return redirect(url_for("cashboxes"))
    return render_template("cashbox_form.html")


@app.route("/finance/transactions")
@login_required
@roles_required("admin", "developer", "manager", "accountant")
def finance_transactions():
    items = FinanceTransaction.query.order_by(FinanceTransaction.tx_date.desc(), FinanceTransaction.id.desc()).all()
    return render_template("finance_transactions.html", transactions=items)


@app.route("/finance/transactions/new", methods=["GET", "POST"])
@login_required
@roles_required("admin", "developer", "manager", "accountant")
def finance_transaction_new():
    cashboxes = Cashbox.query.filter_by(active=True).all()
    categories = FinanceCategory.query.filter_by(active=True).order_by(FinanceCategory.kind, FinanceCategory.name).all()
    if request.method == "POST":
        direction = request.form["direction"]
        tx = FinanceTransaction(
            tx_no=next_number("TX", FinanceTransaction, "tx_no"),
            tx_date=parse_date(request.form.get("tx_date")) or date.today(),
            cashbox_id=int(request.form["cashbox_id"]),
            category_id=int(request.form["category_id"]) if request.form.get("category_id") else None,
            direction=direction,
            amount=float(request.form.get("amount") or 0),
            currency=request.form.get("currency") or "EGP",
            source_type="manual",
            description=request.form.get("description"),
            reference_no=request.form.get("reference_no"),
            created_by=current_user.id,
        )
        db.session.add(tx)
        db.session.commit()
        flash("تم تسجيل الحركة المالية.", "success")
        return redirect(url_for("finance_transactions"))
    return render_template("finance_transaction_form.html", cashboxes=cashboxes, categories=categories)


@app.route("/teacher-earnings")
@login_required
@roles_required("admin", "developer", "manager", "teacher")
def teacher_earnings():
    query = TeacherSessionEarning.query
    if current_user.role == "teacher":
        query = query.filter_by(teacher_id=current_user.teacher_profile.id)
    items = query.order_by(TeacherSessionEarning.earning_date.desc(), TeacherSessionEarning.id.desc()).all()
    return render_template("teacher_earnings.html", earnings=items)


@app.route("/teacher-earnings/generate/<int:session_id>", methods=["POST"])
@login_required
@roles_required("admin", "developer", "manager", "teacher")
def generate_teacher_earnings(session_id):
    session = db.get_or_404(LessonSession, session_id)
    if current_user.role == "teacher" and session.circle.teacher_id != current_user.teacher_profile.id:
        abort(403)
    created = 0
    for attendance in session.attendance_records:
        if attendance.status not in ("حاضر", "متأخر"):
            continue
        contract = SubscriptionContract.query.filter_by(
            student_id=attendance.student_id,
            teacher_id=session.circle.teacher_id,
            status="نشط"
        ).order_by(SubscriptionContract.id.desc()).first()
        if not contract:
            continue
        existing = TeacherSessionEarning.query.filter_by(session_id=session.id, student_id=attendance.student_id).first()
        if existing:
            continue
        db.session.add(TeacherSessionEarning(
            teacher_id=session.circle.teacher_id,
            session_id=session.id,
            student_id=attendance.student_id,
            contract_id=contract.id,
            earning_date=session.session_date,
            amount=round(
                contract.teacher_rate_per_session
                if contract.teacher_rate_mode == "fixed_egp"
                else contract.teacher_rate_per_session * (contract.exchange_rate_to_egp or 1),
                2
            ),
            currency="EGP",
            status="مستحق",
            notes=f"{session.circle.name} - {attendance.student.full_name}",
        ))
        created += 1
    db.session.commit()
    flash(f"تم إنشاء {created} استحقاق للمعلم.", "success")
    return redirect(url_for("session_detail", session_id=session.id))


@app.route("/teacher-payrolls")
@login_required
@roles_required("admin", "developer", "manager", "teacher")
def teacher_payrolls():
    query = TeacherPayroll.query
    if current_user.role == "teacher":
        query = query.filter_by(teacher_id=current_user.teacher_profile.id)
    items = query.order_by(TeacherPayroll.period_to.desc(), TeacherPayroll.id.desc()).all()
    return render_template("teacher_payrolls.html", payrolls=items)


@app.route("/teacher-payrolls/new", methods=["GET", "POST"])
@login_required
@roles_required("admin", "developer", "manager")
def teacher_payroll_new():
    teachers = Teacher.query.join(User).filter(User.is_active_user == True).order_by(User.full_name).all()
    cashboxes = Cashbox.query.filter_by(active=True).all()
    if request.method == "POST":
        teacher_id = int(request.form["teacher_id"])
        period_from = parse_date(request.form["period_from"])
        period_to = parse_date(request.form["period_to"])
        earnings = TeacherSessionEarning.query.filter(
            TeacherSessionEarning.teacher_id == teacher_id,
            TeacherSessionEarning.earning_date >= period_from,
            TeacherSessionEarning.earning_date <= period_to,
            TeacherSessionEarning.status != "مدفوع"
        ).all()
        gross = round(sum(e.amount for e in earnings), 2)
        bonuses = float(request.form.get("bonuses") or 0)
        deductions = float(request.form.get("deductions") or 0)
        payroll = TeacherPayroll(
            payroll_no=next_number("PAY", TeacherPayroll, "payroll_no"),
            teacher_id=teacher_id,
            period_from=period_from,
            period_to=period_to,
            gross_amount=gross,
            bonuses=bonuses,
            deductions=deductions,
            net_amount=round(gross + bonuses - deductions, 2),
            currency=request.form.get("currency") or "EGP",
            status="معتمد",
            cashbox_id=int(request.form["cashbox_id"]) if request.form.get("cashbox_id") else None,
            notes=request.form.get("notes"),
        )
        db.session.add(payroll)
        for e in earnings:
            e.status = "مرحل"
        db.session.commit()
        flash("تم إنشاء كشف مستحقات المعلم.", "success")
        return redirect(url_for("teacher_payrolls"))
    return render_template("teacher_payroll_form.html", teachers=teachers, cashboxes=cashboxes)


@app.post("/teacher-payrolls/<int:payroll_id>/pay")
@login_required
@roles_required("admin", "developer", "manager")
def teacher_payroll_pay(payroll_id):
    payroll = db.get_or_404(TeacherPayroll, payroll_id)
    if payroll.status == "مدفوع":
        flash("الكشف مدفوع بالفعل.", "danger")
        return redirect(url_for("teacher_payrolls"))
    if not payroll.cashbox_id:
        flash("يجب تحديد خزنة للكشف قبل الدفع.", "danger")
        return redirect(url_for("teacher_payrolls"))
    tx = FinanceTransaction(
        tx_no=next_number("TX", FinanceTransaction, "tx_no"),
        tx_date=date.today(),
        cashbox_id=payroll.cashbox_id,
        direction="out",
        amount=payroll.net_amount,
        currency=payroll.currency,
        source_type="teacher_salary",
        source_id=payroll.id,
        description=f"مستحقات المعلم {payroll.teacher.user.full_name} - {payroll.payroll_no}",
        created_by=current_user.id,
    )
    db.session.add(tx)
    payroll.status = "مدفوع"
    payroll.paid_date = date.today()
    post_journal(f"دفع مستحقات المعلم {payroll.teacher.user.full_name}", "teacher_payroll", payroll.id, [
        {"account": "5000", "debit": payroll.net_amount, "currency": "EGP"},
        {"account": "1000", "credit": payroll.net_amount, "currency": "EGP"},
    ], date.today())
    TeacherSessionEarning.query.filter(
        TeacherSessionEarning.teacher_id == payroll.teacher_id,
        TeacherSessionEarning.earning_date >= payroll.period_from,
        TeacherSessionEarning.earning_date <= payroll.period_to,
        TeacherSessionEarning.status == "مرحل"
    ).update({"status": "مدفوع"}, synchronize_session=False)
    db.session.commit()
    flash("تم دفع مستحقات المعلم وتسجيل حركة الخزنة.", "success")
    return redirect(url_for("teacher_payrolls"))


@app.route("/reports")
@login_required
@roles_required("admin", "developer", "manager", "accountant")
def reports():
    today = date.today()
    start = parse_date(request.args.get("start")) or today.replace(day=1)
    end = parse_date(request.args.get("end")) or today
    txs = FinanceTransaction.query.filter(FinanceTransaction.tx_date >= start, FinanceTransaction.tx_date <= end).all()
    income = round(sum(t.amount for t in txs if t.direction == "in"), 2)
    expense = round(sum(t.amount for t in txs if t.direction == "out"), 2)
    contracts = SubscriptionContract.query.filter(SubscriptionContract.start_date <= end).all()
    receivables = round(sum(max(c.balance, 0) for c in contracts), 2)
    teacher_due = round(sum(e.amount for e in TeacherSessionEarning.query.filter(
        TeacherSessionEarning.earning_date >= start,
        TeacherSessionEarning.earning_date <= end,
        TeacherSessionEarning.status != "مدفوع"
    ).all()), 2)
    return render_template("reports.html", start=start, end=end, income=income, expense=expense, net=round(income-expense,2), receivables=receivables, teacher_due=teacher_due, transactions=txs)


@app.cli.command("seed-test-data")
def seed_test_data():
    """Rebuild a clean, realistic academy demo database for the new workflow."""
    db.drop_all(); db.create_all()
    initialize_runtime_defaults()
    for etype, rows in {
        "student":[("memorization","الحفظ الجديد"),("revision","المراجعة"),("tajweed","التجويد"),("pronunciation","مخارج الحروف"),("focus","التركيز")],
        "teacher":[("punctuality","الالتزام بالمواعيد"),("communication","التواصل"),("explanation","وضوح الشرح"),("motivation","التحفيز"),("progress","تطور الطالب")]
    }.items():
        for order,(code,label) in enumerate(rows,1): db.session.add(EvaluationQuestion(evaluation_type=etype,code=code,label=label,max_score=5,sort_order=order))
    db.session.flush()

    admin = User(full_name="إدارة أكاديمية المودة", email="admin@mawadda.local", phone="01000000001", role="admin")
    admin.set_password("Admin@123"); db.session.add(admin); db.session.flush()

    categories = [
        FinanceCategory(name="اشتراكات الطلاب", kind="income"),
        FinanceCategory(name="إيرادات أخرى", kind="income"),
        FinanceCategory(name="رواتب المعلمين", kind="expense"),
        FinanceCategory(name="تشغيل ومنصات", kind="expense"),
    ]
    db.session.add_all(categories)
    boxes = [Cashbox(name="الخزنة الرئيسية", currency="EGP", opening_balance=10000),
             Cashbox(name="InstaPay", currency="EGP", opening_balance=3500),
             Cashbox(name="تحويلات دولية", currency="USD", opening_balance=100)]
    db.session.add_all(boxes); db.session.flush()

    teacher_data = [
        ("أحمد عبد الرحمن", "ahmed.teacher@mawadda.test", "تحفيظ وتجويد"),
        ("مريم مصطفى", "mariam.teacher@mawadda.test", "نور البيان وتصحيح التلاوة"),
        ("عبد الله محمود", "abdullah.teacher@mawadda.test", "إجازات وقراءات"),
        ("فاطمة علي", "fatma.teacher@mawadda.test", "تحفيظ الأطفال"),
    ]
    teachers=[]
    for i,(name,email,spec) in enumerate(teacher_data):
        u=User(full_name=name,email=email,phone=f"0102000000{i}",whatsapp=f"20102000000{i}",role="teacher")
        u.set_password("Teacher@123"); db.session.add(u); db.session.flush()
        t=Teacher(user_id=u.id,employee_code=next_teacher_code(),specialization=spec,join_date=date.today()-timedelta(days=180-i*20))
        db.session.add(t); db.session.flush(); teachers.append(t)

    parent_data = [
        ("محمد حسن", "mohamed.parent@mawadda.test", "مصر"),
        ("سارة خالد", "sara.parent@mawadda.test", "مصر"),
        ("عمر يوسف", "omar.parent@mawadda.test", "السعودية"),
        ("نور أحمد", "nour.parent@mawadda.test", "الإمارات"),
        ("خالد إبراهيم", "khaled.parent@mawadda.test", "الكويت"),
        ("هبة محمود", "heba.parent@mawadda.test", "قطر"),
    ]
    parents=[]
    for i,(name,email,country) in enumerate(parent_data):
        u=User(full_name=name,email=email,phone=f"0113000000{i}",whatsapp=f"20113000000{i}",role="parent")
        u.set_password("Parent@123"); db.session.add(u); db.session.flush()
        par=Parent(parent_code=next_parent_code(),user_id=u.id,address="عنوان تجريبي",country=country)
        db.session.add(par); db.session.flush(); parents.append(par)

    student_names=["يوسف محمد","آدم محمد","ليان سارة","جنى سارة","حمزة عمر","ريم نور","عبد الرحمن خالد","مريم خالد","ياسين هبة","سلمى هبة"]
    students=[]
    for i,name in enumerate(student_names):
        par=parents[min(i//2,len(parents)-1)]
        st=Student(student_code=next_student_code(),full_name=name,birth_date=date.today()-timedelta(days=365*(7+i%7)),
                   gender="ذكر" if i%2==0 else "أنثى",country=par.country,level=["تمهيدي","مبتدئ","متوسط","متقدم"][i%4],parent_id=par.id)
        db.session.add(st); db.session.flush(); students.append(st)
        db.session.add(ActivityTimeline(student_id=st.id,activity_type="registration",title="تسجيل الطالب",details="بيانات اختبار الإصدار المؤسسي",created_by=admin.id))

    circle_data=[("التحفيظ الفردي",teachers[0],30,"الأحد والثلاثاء 19:00"),("نور البيان",teachers[1],45,"السبت والأربعاء 18:00"),("التجويد المتقدم",teachers[2],60,"الجمعة 16:00"),("براعم القرآن",teachers[3],30,"الاثنين والخميس 17:00")]
    circles=[]
    for name,t,mins,schedule in circle_data:
        c=Circle(name=name,teacher_id=t.id,study_type="أونلاين",default_minutes=mins,schedule_text=schedule)
        db.session.add(c); db.session.flush(); circles.append(c)
    for i,st in enumerate(students): db.session.add(Enrollment(student_id=st.id,circle_id=circles[i%4].id,start_date=date.today()-timedelta(days=45)))
    db.session.flush()

    currencies=["EGP","EGP","SAR","AED","KWD","QAR","USD","EGP","SAR","AED"]
    prices={"EGP":1200,"SAR":220,"AED":215,"KWD":18,"QAR":210,"USD":65}
    rates={x.currency:x.rate_to_egp for x in ExchangeRate.query.all()}
    for i,st in enumerate(students):
        cur=currencies[i]; teacher=circles[i%4].teacher
        contract=SubscriptionContract(contract_no=f"CNT-{date.today().year}-{i+1:05d}",student_id=st.id,teacher_id=teacher.id,
             service_name="باقة شهرية - 8 حصص",start_date=date.today()-timedelta(days=20-i),end_date=date.today()+timedelta(days=10+i),
             total_sessions=8,session_minutes=circles[i%4].default_minutes,contract_price=prices[cur],discount_amount=0,currency=cur,
             teacher_rate_per_session=120 if cur=="EGP" else 120,teacher_rate_currency="EGP",exchange_rate_to_egp=rates.get(cur,1),teacher_rate_mode="fixed_egp",status="نشط")
        db.session.add(contract); db.session.flush()
        paid=round(contract.contract_price*(1 if i%3 else .5),2)
        payment=Payment(receipt_no=f"REC-{date.today().year}-{i+1:05d}",contract_id=contract.id,payment_date=date.today()-timedelta(days=10),amount=paid,currency=cur,
                        payment_method=["InstaPay","كاش","تحويل بنكي"][i%3],created_by=admin.id)
        db.session.add(payment); db.session.flush()
        egp=round(paid*rates.get(cur,1),2)
        tx=FinanceTransaction(tx_no=f"TX-{date.today().year}-{i+1:05d}",tx_date=payment.payment_date,cashbox_id=boxes[0].id,category_id=categories[0].id,
                              direction="in",amount=egp,currency="EGP",source_type="payment",source_id=payment.id,description=f"تحصيل {contract.contract_no}",created_by=admin.id)
        db.session.add(tx)
        db.session.add(ActivityTimeline(student_id=st.id,activity_type="payment",title="دفعة اشتراك",details=f"{paid} {cur}",created_by=admin.id))

    for day_offset in range(0,21,3):
        for c in circles:
            ses=LessonSession(circle_id=c.id,session_date=date.today()-timedelta(days=day_offset),start_time="19:00",duration_minutes=c.default_minutes,actual_minutes=c.default_minutes,status="تمت",topic="حفظ جديد ومراجعة")
            db.session.add(ses); db.session.flush()
            for enr in c.enrollments:
                status="غائب" if (enr.student_id+day_offset)%9==0 else "حاضر"
                db.session.add(Attendance(session_id=ses.id,student_id=enr.student_id,status=status))
                if status=="حاضر":
                    db.session.add(StudentEvaluation(session_id=ses.id,student_id=enr.student_id,teacher_id=c.teacher_id,memorization=4,revision=4,tajweed=4,pronunciation=5,focus=4,homework_done=True,lesson_covered="ورد الحصة",homework="مراجعة الورد"))
                    contract=SubscriptionContract.query.filter_by(student_id=enr.student_id).first()
                    db.session.add(TeacherSessionEarning(teacher_id=c.teacher_id,session_id=ses.id,student_id=enr.student_id,contract_id=contract.id,earning_date=ses.session_date,amount=120,currency="EGP",status="مستحق"))

    complaint=Complaint(complaint_no=f"CMP-{date.today().year}-00001",parent_id=parents[0].id,student_id=students[0].id,teacher_id=teachers[0].id,subject="طلب مراجعة موعد الحصة",details="الموعد الحالي يتعارض مع المدرسة.",priority="عادية",status="جديدة")
    db.session.add(complaint)
    approval=ApprovalRequest(request_no=f"APR-{date.today().year}-00001",request_type="خصم",title="طلب خصم استثنائي",details="خصم للأخوين في نفس الأسرة",requested_by=admin.id)
    db.session.add(approval)
    db.session.add(BackgroundJob(job_type="contract-reminders",payload="{}",scheduled_at=datetime.utcnow()))
    db.session.commit()
    print("New enterprise test data created.")
    print("Admin: admin@mawadda.local / Admin@123")
    print("Teacher: ahmed.teacher@mawadda.test / Teacher@123")
    print("Parent: mohamed.parent@mawadda.test / Parent@123")


@app.route("/home", methods=["GET", "POST"])
def public_home():
    if request.method == "POST":
        msg = ContactMessage(
            full_name=request.form["full_name"].strip(),
            phone=request.form["phone"].strip(),
            email=request.form.get("email"),
            message=request.form["message"].strip(),
        )
        db.session.add(msg)
        db.session.commit()
        flash("تم إرسال رسالتك، وسنتواصل معك قريبًا.", "success")
        return redirect(url_for("public_home"))
    teachers = Teacher.query.join(User).filter(User.is_active_user == True).limit(6).all()
    return render_template("public_home.html", teachers=teachers)


@app.route("/manifest.json")
def manifest():
    data = {
        "name": "أكاديمية المودة",
        "short_name": "المودة",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#fff8f6",
        "theme_color": "#102f5c",
        "lang": "ar",
        "dir": "rtl",
        "icons": [
            {"src": url_for("static", filename="img/logo.png"), "sizes": "192x192", "type": "image/png"},
            {"src": url_for("static", filename="img/logo.png"), "sizes": "512x512", "type": "image/png"}
        ]
    }
    return app.response_class(json.dumps(data, ensure_ascii=False), mimetype="application/manifest+json")


@app.route("/service-worker.js")
def service_worker():
    js = """
const CACHE='mawadda-v1';
const ASSETS=['/','/home','/static/css/style.css','/static/img/logo.png'];
self.addEventListener('install',e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(ASSETS))));
self.addEventListener('fetch',e=>e.respondWith(caches.match(e.request).then(r=>r||fetch(e.request))));
"""
    return app.response_class(js, mimetype="application/javascript")


@app.route("/notifications")
@login_required
def notifications():
    items = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
    return render_template("notifications.html", notifications=items)


@app.post("/notifications/<int:notification_id>/read")
@login_required
def notification_read(notification_id):
    n = db.get_or_404(Notification, notification_id)
    if n.user_id != current_user.id:
        abort(403)
    n.read_at = datetime.utcnow()
    n.status = "مقروء"
    db.session.commit()
    return redirect(n.action_url or url_for("notifications"))


@app.route("/admin/messages")
@login_required
@roles_required("admin", "developer", "manager")
def contact_messages():
    items = ContactMessage.query.order_by(ContactMessage.created_at.desc()).all()
    return render_template("contact_messages.html", messages=items)


@app.route("/admin/notification-templates")
@login_required
@roles_required("admin", "developer", "manager")
def notification_templates():
    items = NotificationTemplate.query.order_by(NotificationTemplate.name).all()
    return render_template("notification_templates.html", templates=items)


@app.route("/whatsapp/contract/<int:contract_id>")
@login_required
@roles_required("admin", "developer", "manager")
def whatsapp_contract(contract_id):
    contract = db.get_or_404(SubscriptionContract, contract_id)
    parent_user = contract.student.parent.user
    text = render_template_text("contract_reminder", {
        "parent_name": parent_user.full_name,
        "student_name": contract.student.full_name,
        "contract_no": contract.contract_no,
        "balance": contract.balance,
        "currency": contract.currency,
        "end_date": contract.end_date or "-",
    }) or f"السلام عليكم، نذكركم باشتراك الطالب {contract.student.full_name}. المتبقي {contract.balance} {contract.currency}."
    return redirect(whatsapp_link(parent_user.whatsapp or parent_user.phone, text))


@app.route("/whatsapp/session/<int:session_id>/<int:student_id>")
@login_required
@roles_required("admin", "developer", "manager", "teacher")
def whatsapp_session_report(session_id, student_id):
    session = db.get_or_404(LessonSession, session_id)
    student = db.get_or_404(Student, student_id)
    evaluation = StudentEvaluation.query.filter_by(session_id=session.id, student_id=student.id).first()
    parent_user = student.parent.user
    text = render_template_text("session_report", {
        "parent_name": parent_user.full_name,
        "student_name": student.full_name,
        "session_date": session.session_date,
        "lesson": evaluation.lesson_covered if evaluation else session.topic or "-",
        "homework": evaluation.homework if evaluation else "-",
        "score": evaluation.average if evaluation else "-",
    }) or f"تقرير حصة {student.full_name} بتاريخ {session.session_date}."
    return redirect(whatsapp_link(parent_user.whatsapp or parent_user.phone, text))


@app.cli.command("generate-notifications")
def generate_notifications():
    today = date.today()
    created = 0
    for contract in SubscriptionContract.query.filter_by(status="نشط").all():
        if contract.end_date and 0 <= (contract.end_date - today).days <= 5:
            user = contract.student.parent.user
            exists = Notification.query.filter(
                Notification.user_id == user.id,
                Notification.title == "قرب انتهاء الاشتراك",
                Notification.created_at >= datetime.combine(today, datetime.min.time())
            ).first()
            if not exists:
                create_notification(
                    user.id,
                    "قرب انتهاء الاشتراك",
                    f"اشتراك {contract.student.full_name} سينتهي بتاريخ {contract.end_date}.",
                    url_for("contract_detail", contract_id=contract.id),
                )
                created += 1
        if contract.balance > 0:
            user = contract.student.parent.user
            exists = Notification.query.filter(
                Notification.user_id == user.id,
                Notification.title == "مبلغ مستحق",
                Notification.created_at >= datetime.combine(today, datetime.min.time())
            ).first()
            if not exists:
                create_notification(
                    user.id,
                    "مبلغ مستحق",
                    f"المتبقي على عقد {contract.student.full_name}: {contract.balance} {contract.currency}.",
                    url_for("contract_detail", contract_id=contract.id),
                )
                created += 1

    for session in LessonSession.query.filter_by(session_date=today).all():
        teacher_user = session.circle.teacher.user
        exists = Notification.query.filter(
            Notification.user_id == teacher_user.id,
            Notification.title == "حصة اليوم",
            Notification.body.contains(session.circle.name),
            Notification.created_at >= datetime.combine(today, datetime.min.time())
        ).first()
        if not exists:
            create_notification(
                teacher_user.id,
                "حصة اليوم",
                f"لديك حصة {session.circle.name} الساعة {session.start_time or '-'} لمدة {session.duration_minutes} دقيقة.",
                url_for("session_detail", session_id=session.id),
            )
            created += 1
    db.session.commit()
    print(f"Created {created} notifications.")


@app.cli.command("seed-phase4")
def seed_phase4():
    db.create_all()
    defaults = [
        ("contract_reminder","تذكير اشتراك","whatsapp","السلام عليكم أ/ {{parent_name}}، نذكركم باشتراك الطالب {{student_name}} رقم {{contract_no}}. المتبقي {{balance}} {{currency}}، وتاريخ الانتهاء {{end_date}}."),
        ("session_report","تقرير حصة","whatsapp","السلام عليكم أ/ {{parent_name}}، تقرير حصة الطالب {{student_name}} بتاريخ {{session_date}}: تم {{lesson}}، التقييم {{score}}/5، والواجب {{homework}}."),
        ("welcome_parent","ترحيب ولي أمر","whatsapp","مرحبًا بكم في أكاديمية المودة، تم إنشاء حسابكم بنجاح."),
    ]
    for code,name,channel,body in defaults:
        if not NotificationTemplate.query.filter_by(code=code).first():
            db.session.add(NotificationTemplate(code=code,name=name,channel=channel,body=body))
    db.session.commit()
    print("Phase 4 templates created.")


@app.route("/teachers/<int:teacher_id>/account")
@login_required
@permission_required("teacher_finance.view")
def teacher_account(teacher_id):
    teacher = db.get_or_404(Teacher, teacher_id)
    if current_user.role == "teacher" and current_user.teacher_profile.id != teacher.id: abort(403)
    if current_user.role == "teacher" and current_user.teacher_profile.id != teacher.id:
        abort(403)
    if current_user.role not in ("admin", "developer", "manager", "teacher"):
        abort(403)

    earned_by_currency = {}
    for e in teacher.earnings:
        earned_by_currency[e.currency] = earned_by_currency.get(e.currency, 0) + e.amount

    paid_by_currency = {}
    for p in teacher.payments_received:
        paid_by_currency[p.currency] = paid_by_currency.get(p.currency, 0) + p.amount

    balances = {}
    currencies = set(earned_by_currency) | set(paid_by_currency)
    for cur in currencies:
        balances[cur] = round(earned_by_currency.get(cur, 0) - paid_by_currency.get(cur, 0), 2)

    return render_template(
        "teacher_account.html",
        teacher=teacher,
        earned_by_currency=earned_by_currency,
        paid_by_currency=paid_by_currency,
        balances=balances,
    )


@app.route("/teachers/<int:teacher_id>/payments/new", methods=["GET", "POST"])
@login_required
@roles_required("admin", "developer", "manager", "accountant")
def teacher_payment_new(teacher_id):
    teacher = db.get_or_404(Teacher, teacher_id)
    cashboxes = Cashbox.query.filter_by(active=True, currency="EGP").all()
    if request.method == "POST":
        amount = float(request.form.get("amount") or 0)
        if amount <= 0:
            flash("المبلغ يجب أن يكون أكبر من صفر.", "danger")
        else:
            payment = TeacherPayment(
                payment_no=next_number("TPY", TeacherPayment, "payment_no"),
                teacher_id=teacher.id,
                payment_date=parse_date(request.form.get("payment_date")) or date.today(),
                period_from=parse_date(request.form.get("period_from")),
                period_to=parse_date(request.form.get("period_to")),
                amount=amount,
                currency="EGP",
                payment_method=request.form.get("payment_method") or "كاش",
                reference_no=request.form.get("reference_no"),
                cashbox_id=int(request.form["cashbox_id"]) if request.form.get("cashbox_id") else None,
                notes=request.form.get("notes"),
                created_by=current_user.id,
            )
            db.session.add(payment)
            db.session.flush()
            if payment.cashbox_id:
                db.session.add(FinanceTransaction(
                    tx_no=next_number("TX", FinanceTransaction, "tx_no"),
                    tx_date=payment.payment_date,
                    cashbox_id=payment.cashbox_id,
                    direction="out",
                    amount=payment.amount,
                    currency="EGP",
                    source_type="teacher_payment",
                    source_id=payment.id,
                    description=f"دفعة للمعلم {teacher.user.full_name} حتى {payment.period_to or payment.payment_date}",
                    reference_no=payment.reference_no,
                    created_by=current_user.id,
                ))
            db.session.commit()
            flash("تم تسجيل دفعة المعلم.", "success")
            return redirect(url_for("teacher_account", teacher_id=teacher.id))
    return render_template("teacher_payment_form.html", teacher=teacher, cashboxes=cashboxes)


@app.route("/contracts/<int:contract_id>/freeze", methods=["GET", "POST"])
@login_required
@roles_required("admin", "developer", "manager")
def contract_freeze(contract_id):
    contract = db.get_or_404(SubscriptionContract, contract_id)
    if request.method == "POST":
        contract.frozen_from = parse_date(request.form.get("frozen_from"))
        contract.frozen_to = parse_date(request.form.get("frozen_to"))
        contract.status = "مجمد"
        if contract.end_date and contract.frozen_from and contract.frozen_to:
            days = (contract.frozen_to - contract.frozen_from).days + 1
            if days > 0:
                contract.end_date = contract.end_date + timedelta(days=days)
        db.session.commit()
        flash("تم تجميد الاشتراك وتمديد تاريخ الانتهاء.", "success")
        return redirect(url_for("contract_detail", contract_id=contract.id))
    return render_template("contract_freeze_form.html", contract=contract)


@app.route("/sessions/<int:session_id>/reschedule", methods=["GET", "POST"])
@login_required
@roles_required("admin", "developer", "manager", "teacher")
def session_reschedule(session_id):
    old = db.get_or_404(LessonSession, session_id)
    if current_user.role == "teacher" and old.circle.teacher_id != current_user.teacher_profile.id:
        abort(403)
    if request.method == "POST":
        new_session = LessonSession(
            circle_id=old.circle_id,
            session_date=parse_date(request.form.get("session_date")) or date.today(),
            start_time=request.form.get("start_time"),
            duration_minutes=int(request.form.get("duration_minutes") or old.duration_minutes),
            actual_minutes=None,
            session_type="تعويض" if request.form.get("makeup") else "إعادة جدولة",
            rescheduled_from_id=old.id,
            topic=old.topic,
            status="مجدولة",
            notes=request.form.get("notes"),
        )
        old.status = "مؤجلة"
        db.session.add(new_session)
        db.session.commit()
        flash("تم إنشاء موعد جديد للحصة.", "success")
        return redirect(url_for("session_detail", session_id=new_session.id))
    return render_template("session_reschedule_form.html", session=old)


@app.route("/students/<int:student_id>/quran-progress/new", methods=["GET", "POST"])
@login_required
@roles_required("admin", "developer", "manager", "teacher")
def quran_progress_new(student_id):
    student = db.get_or_404(Student, student_id)
    sessions = LessonSession.query.join(Circle)
    if current_user.role == "teacher":
        sessions = sessions.filter(Circle.teacher_id == current_user.teacher_profile.id)
    sessions = sessions.order_by(LessonSession.session_date.desc()).limit(50).all()
    if request.method == "POST":
        progress = QuranProgress(
            student_id=student.id,
            session_id=int(request.form["session_id"]) if request.form.get("session_id") else None,
            progress_date=parse_date(request.form.get("progress_date")) or date.today(),
            surah_name=request.form["surah_name"].strip(),
            from_ayah=int(request.form.get("from_ayah") or 0) or None,
            to_ayah=int(request.form.get("to_ayah") or 0) or None,
            progress_type=request.form.get("progress_type") or "حفظ جديد",
            memorization_errors=int(request.form.get("memorization_errors") or 0),
            tajweed_errors=int(request.form.get("tajweed_errors") or 0),
            notes=request.form.get("notes"),
            created_by=current_user.id,
        )
        db.session.add(progress)
        db.session.commit()
        flash("تم حفظ تقدم الطالب في القرآن.", "success")
        return redirect(url_for("student_profile", student_id=student.id))
    return render_template("quran_progress_form.html", student=student, sessions=sessions)


def parent_allowed_teacher_ids(parent):
    teacher_ids = set()
    for student in parent.students:
        for enrollment in student.enrollments:
            if enrollment.active and enrollment.circle and enrollment.circle.teacher_id:
                teacher_ids.add(enrollment.circle.teacher_id)
    return teacher_ids


@app.route("/settings/codes", methods=["GET", "POST"])
@login_required
@roles_required("admin", "developer", "manager")
def code_settings():
    ensure_default_sequences()
    if request.method == "POST":
        for entity in ["student", "teacher", "parent"]:
            seq = CodeSequence.query.filter_by(entity=entity).first()
            seq.prefix = request.form.get(f"{entity}_prefix", seq.prefix).strip().upper()
            seq.next_number = int(request.form.get(f"{entity}_next_number") or seq.next_number)
            seq.padding = int(request.form.get(f"{entity}_padding") or seq.padding)
        db.session.commit()
        flash("تم تحديث إعدادات الأكواد بدون تعديل الكود البرمجي.", "success")
        return redirect(url_for("code_settings"))
    sequences = {s.entity: s for s in CodeSequence.query.all()}
    return render_template("code_settings.html", sequences=sequences)


@app.route("/settings/exchange-rates", methods=["GET", "POST"])
@login_required
@roles_required("admin", "developer", "manager")
def exchange_rates():
    if request.method == "POST":
        currency = request.form["currency"].strip().upper()
        rate = float(request.form.get("rate_to_egp") or 1)
        item = ExchangeRate.query.filter_by(currency=currency).first()
        if not item:
            item = ExchangeRate(currency=currency)
            db.session.add(item)
        item.rate_to_egp = rate
        item.updated_at = datetime.utcnow()
        item.updated_by = current_user.id
        db.session.commit()
        flash("تم حفظ سعر التحويل إلى الجنيه المصري.", "success")
        return redirect(url_for("exchange_rates"))
    items = ExchangeRate.query.order_by(ExchangeRate.currency).all()
    return render_template("exchange_rates.html", rates=items)


@app.route("/complaints")
@login_required
def complaints():
    if current_user.role == "parent":
        items = Complaint.query.filter_by(parent_id=current_user.parent_profile.id).order_by(Complaint.created_at.desc()).all()
    elif current_user.role in {"admin", "developer", "manager"}:
        items = Complaint.query.order_by(Complaint.created_at.desc()).all()
    else:
        abort(403)
    return render_template("complaints.html", complaints=items)


@app.route("/complaints/new", methods=["GET", "POST"])
@login_required
@roles_required("parent")
def complaint_new():
    parent = current_user.parent_profile
    students = parent.students
    allowed_teacher_ids = parent_allowed_teacher_ids(parent)
    teachers = Teacher.query.filter(Teacher.id.in_(allowed_teacher_ids)).all() if allowed_teacher_ids else []
    if request.method == "POST":
        student = db.get_or_404(Student, int(request.form["student_id"]))
        teacher = db.get_or_404(Teacher, int(request.form["teacher_id"]))
        if student.parent_id != parent.id or teacher.id not in allowed_teacher_ids:
            abort(403)
        complaint = Complaint(
            complaint_no=next_number("CMP", Complaint, "complaint_no"),
            parent_id=parent.id,
            student_id=student.id,
            teacher_id=teacher.id,
            subject=request.form["subject"].strip(),
            details=request.form["details"].strip(),
            priority=request.form.get("priority") or "عادية",
        )
        db.session.add(complaint)
        admin = User.query.filter(User.role.in_(["admin", "developer", "manager"]), User.is_active_user == True).order_by(db.case((User.role.in_(["admin", "developer"]), 0), else_=1)).first()
        if admin:
            create_notification(admin.id, "شكوى جديدة", f"شكوى جديدة بخصوص الطالب {student.full_name}.", url_for("complaints"))
        db.session.commit()
        flash("تم إرسال الشكوى للإدارة.", "success")
        return redirect(url_for("complaints"))
    return render_template("complaint_form.html", students=students, teachers=teachers)


@app.route("/complaints/<int:complaint_id>/manage", methods=["GET", "POST"])
@login_required
@roles_required("admin", "developer", "manager")
def complaint_manage(complaint_id):
    complaint = db.get_or_404(Complaint, complaint_id)
    if request.method == "POST":
        complaint.status = request.form.get("status") or complaint.status
        complaint.admin_response = request.form.get("admin_response")
        if complaint.status == "مغلقة":
            complaint.closed_at = datetime.utcnow()
        create_notification(
            complaint.parent.user.id,
            "تحديث الشكوى",
            f"تم تحديث الشكوى {complaint.complaint_no} إلى الحالة: {complaint.status}.",
            url_for("complaints"),
        )
        db.session.commit()
        flash("تم تحديث الشكوى.", "success")
        return redirect(url_for("complaints"))
    return render_template("complaint_manage.html", complaint=complaint)


@app.route("/teacher-change-requests")
@login_required
def teacher_change_requests():
    if current_user.role == "parent":
        items = TeacherChangeRequest.query.filter_by(parent_id=current_user.parent_profile.id).order_by(TeacherChangeRequest.created_at.desc()).all()
    elif current_user.role in {"admin", "developer", "manager"}:
        items = TeacherChangeRequest.query.order_by(TeacherChangeRequest.created_at.desc()).all()
    else:
        abort(403)
    return render_template("teacher_change_requests.html", requests=items)


@app.route("/teacher-change-requests/new", methods=["GET", "POST"])
@login_required
@roles_required("parent")
def teacher_change_request_new():
    parent = current_user.parent_profile
    students = parent.students
    allowed_teacher_ids = parent_allowed_teacher_ids(parent)
    current_teachers = Teacher.query.filter(Teacher.id.in_(allowed_teacher_ids)).all() if allowed_teacher_ids else []
    if request.method == "POST":
        student = db.get_or_404(Student, int(request.form["student_id"]))
        current_teacher = db.get_or_404(Teacher, int(request.form["current_teacher_id"]))
        if student.parent_id != parent.id or current_teacher.id not in allowed_teacher_ids:
            abort(403)
        item = TeacherChangeRequest(
            request_no=next_number("TCR", TeacherChangeRequest, "request_no"),
            parent_id=parent.id,
            student_id=student.id,
            current_teacher_id=current_teacher.id,
            reason=request.form["reason"].strip(),
            preferred_times=request.form.get("preferred_times"),
        )
        db.session.add(item)
        admin = User.query.filter(User.role.in_(["admin", "developer", "manager"]), User.is_active_user == True).order_by(db.case((User.role.in_(["admin", "developer"]), 0), else_=1)).first()
        if admin:
            create_notification(admin.id, "طلب تغيير معلم", f"طلب تغيير معلم للطالب {student.full_name}.", url_for("teacher_change_requests"))
        db.session.commit()
        flash("تم إرسال طلب تغيير المعلم.", "success")
        return redirect(url_for("teacher_change_requests"))
    return render_template("teacher_change_request_form.html", students=students, teachers=current_teachers)


@app.route("/teacher-change-requests/<int:request_id>/manage", methods=["GET", "POST"])
@login_required
@roles_required("admin", "developer", "manager")
def teacher_change_request_manage(request_id):
    item = db.get_or_404(TeacherChangeRequest, request_id)
    teachers = Teacher.query.join(User).filter(User.is_active_user == True).order_by(User.full_name).all()
    if request.method == "POST":
        item.status = request.form.get("status") or item.status
        item.admin_note = request.form.get("admin_note")
        item.approved_teacher_id = int(request.form["approved_teacher_id"]) if request.form.get("approved_teacher_id") else None
        item.effective_date = parse_date(request.form.get("effective_date"))
        if item.status in ("مقبول", "مرفوض"):
            item.resolved_at = datetime.utcnow()

        # On approval, deactivate old enrollment and create a new one in an active circle of the approved teacher.
        if item.status == "مقبول" and item.approved_teacher_id:
            old_enrollments = Enrollment.query.join(Circle).filter(
                Enrollment.student_id == item.student_id,
                Enrollment.active == True,
                Circle.teacher_id == item.current_teacher_id
            ).all()
            for enrollment in old_enrollments:
                enrollment.active = False

            target_circle = Circle.query.filter_by(teacher_id=item.approved_teacher_id, active=True).first()
            if target_circle:
                db.session.add(Enrollment(
                    student_id=item.student_id,
                    circle_id=target_circle.id,
                    start_date=item.effective_date or date.today(),
                    active=True,
                ))

            # Update active contracts to the new teacher.
            active_contracts = SubscriptionContract.query.filter_by(student_id=item.student_id, status="نشط").all()
            for contract in active_contracts:
                contract.teacher_id = item.approved_teacher_id

        create_notification(
            item.parent.user.id,
            "تحديث طلب تغيير المعلم",
            f"تم تحديث الطلب {item.request_no} إلى الحالة: {item.status}.",
            url_for("teacher_change_requests"),
        )
        db.session.commit()
        flash("تم تحديث طلب تغيير المعلم.", "success")
        return redirect(url_for("teacher_change_requests"))
    return render_template("teacher_change_request_manage.html", item=item, teachers=teachers)


# ===== Enterprise Services & Screens =====

@app.route("/audit-logs")
@login_required
@roles_required("admin", "developer", "manager")
def audit_logs():
    items = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(500).all()
    return render_template("audit_logs.html", items=items)


@app.route("/approvals", methods=["GET", "POST"])
@login_required
@permission_required("approvals.view")
def approvals():
    if request.method == "POST":
        item = ApprovalRequest(request_no=next_number("APR", ApprovalRequest, "request_no"),
                               request_type=request.form.get("request_type") or "عام",
                               title=request.form["title"].strip(), details=request.form.get("details"),
                               requested_by=current_user.id)
        db.session.add(item); db.session.commit()
        flash("تم إرسال الطلب للموافقة.", "success")
        return redirect(url_for("approvals"))
    q = ApprovalRequest.query
    if current_user.role not in {"admin", "developer", "manager"}: q = q.filter_by(requested_by=current_user.id)
    return render_template("approvals.html", items=q.order_by(ApprovalRequest.created_at.desc()).all())


@app.post("/approvals/<int:item_id>/review")
@login_required
@roles_required("admin", "developer", "manager")
def approval_review(item_id):
    item=db.get_or_404(ApprovalRequest,item_id)
    item.status=request.form.get("status") or "مرفوض"
    item.review_note=request.form.get("review_note")
    item.reviewed_by=current_user.id; item.reviewed_at=datetime.utcnow()
    create_notification(item.requested_by,"تحديث طلب الموافقة",f"الطلب {item.request_no}: {item.status}",url_for("approvals"))
    db.session.commit(); flash("تم تحديث الطلب.","success")
    return redirect(url_for("approvals"))


@app.route("/accounting/journal")
@login_required
@roles_required("admin", "developer", "manager", "accountant")
def journal_entries():
    items=JournalEntry.query.order_by(JournalEntry.entry_date.desc(),JournalEntry.id.desc()).all()
    return render_template("journal_entries.html",items=items)


@app.route("/permissions", methods=["GET", "POST"])
@login_required
@roles_required("admin", "developer")
def permissions():
    scope=request.values.get("scope","role")
    role=request.values.get("role","teacher")
    user_id=request.values.get("user_id",type=int)
    if request.method=="POST":
        selected={int(x) for x in request.form.getlist("permission_ids")}
        if scope=="user" and user_id:
            UserPermission.query.filter_by(user_id=user_id).delete()
            for p in Permission.query.all():
                role_has=RolePermission.query.filter_by(role=db.session.get(User,user_id).role,permission_id=p.id).first() is not None
                wanted=p.id in selected
                if wanted != role_has: db.session.add(UserPermission(user_id=user_id,permission_id=p.id,allowed=wanted))
        else:
            RolePermission.query.filter_by(role=role).delete()
            for pid in selected: db.session.add(RolePermission(role=role,permission_id=pid))
        db.session.commit(); flash("تم حفظ الصلاحيات وتطبيقها فورًا.","success")
        return redirect(url_for("permissions",scope=scope,role=role,user_id=user_id))
    items=Permission.query.order_by(Permission.name).all(); users=User.query.filter(~User.role.in_(["admin", "developer"])).order_by(User.full_name).all()
    if scope=="user" and user_id:
        user=db.session.get(User,user_id); selected=set()
        for p in items:
            ov=UserPermission.query.filter_by(user_id=user_id,permission_id=p.id).first()
            role_has=RolePermission.query.filter_by(role=user.role,permission_id=p.id).first() is not None
            if (ov.allowed if ov is not None else role_has): selected.add(p.id)
    else:
        selected={x.permission_id for x in RolePermission.query.filter_by(role=role).all()}
    return render_template("permissions.html",items=items,selected=selected,role=role,scope=scope,users=users,user_id=user_id)


@app.route("/settings/email", methods=["GET", "POST"])
@login_required
@roles_required("admin", "developer")
def email_settings():
    keys=["SMTP_HOST","SMTP_PORT","SMTP_USER","SMTP_PASSWORD","SMTP_FROM","SMTP_TLS"]
    if request.method=="POST":
        for k in keys:
            if k=="SMTP_PASSWORD" and not request.form.get(k):
                continue
            set_setting(k, request.form.get(k, ""))
        db.session.commit(); flash("تم حفظ إعدادات Gmail.","success")
        return redirect(url_for("email_settings"))
    values={k:get_setting(k, "") for k in keys}; values["SMTP_PASSWORD"]=""
    return render_template("email_settings.html", values=values)

ADMIN_ROLES = {"admin", "developer", "manager", "accountant"}
ALL_USER_ROLES = {"admin", "developer", "manager", "accountant", "teacher", "parent"}

def _save_profile_photo(file, prefix):
    if not file or not file.filename:
        return None
    ext = Path(secure_filename(file.filename)).suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise ValueError("الصورة يجب أن تكون JPG أو PNG أو WEBP.")
    stored = f"{prefix}_{int(datetime.utcnow().timestamp())}{ext}"
    file.save(os.path.join(app.config["UPLOAD_FOLDER"], stored))
    return stored

@app.route("/users", methods=["GET"])
@login_required
@roles_required("admin", "developer", "manager", "accountant")
def users_admin():
    role_filter = request.args.get("role", "all")
    query = User.query
    if current_user.role == "accountant":
        query = query.filter(User.id == current_user.id)
    elif current_user.role == "manager":
        query = query.filter(User.role != "admin", User.role != "developer")
    if role_filter in ALL_USER_ROLES:
        query = query.filter(User.role == role_filter)
    students = []
    if current_user.role in {"admin", "developer", "manager"} and role_filter in {"all", "student"}:
        students = Student.query.order_by(Student.full_name).all()
    return render_template("users_admin.html", users=query.order_by(User.full_name).all(), students=students, role_filter=role_filter)

@app.route("/users/new", methods=["GET", "POST"])
@login_required
@roles_required("admin", "developer", "manager")
def user_new():
    roles = [("manager", "مدير"), ("accountant", "مدير حسابات"), ("teacher", "معلم"), ("parent", "ولي أمر")]
    if current_user.role in {"admin", "developer"}:
        roles.insert(0, ("admin", "Admin"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        role = request.form.get("role")
        if role not in {x[0] for x in roles}: abort(403)
        if User.query.filter_by(email=email).first():
            flash("البريد مستخدم بالفعل.", "danger")
        else:
            password = request.form.get("password", "")
            if len(password) < 8:
                flash("كلمة المرور لا تقل عن 8 أحرف.", "danger")
                return render_template("admin_user_form.html", roles=roles)
            user = User(full_name=request.form.get("full_name", "").strip(), email=email,
                        phone=request.form.get("phone"), whatsapp=request.form.get("whatsapp"),
                        role=role, is_active_user=True)
            user.set_password(password); db.session.add(user); db.session.flush()
            user.photo = _save_profile_photo(request.files.get("photo"), f"user_{user.id}")
            if role == "teacher":
                db.session.add(Teacher(user_id=user.id, employee_code=next_teacher_code(),
                    specialization=request.form.get("specialization"), bio=request.form.get("bio"), join_date=date.today()))
            elif role == "parent":
                db.session.add(Parent(user_id=user.id, parent_code=next_parent_code(),
                    address=request.form.get("address"), country=request.form.get("country") or "مصر"))
            db.session.commit(); flash("تم إنشاء المستخدم بنجاح.", "success")
            return redirect(url_for("users_admin"))
    return render_template("admin_user_form.html", roles=roles)

@app.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@roles_required("admin", "developer", "manager", "accountant")
def user_edit(user_id):
    user=db.get_or_404(User,user_id)
    if current_user.role == "accountant" and user.id != current_user.id: abort(403)
    if current_user.role == "manager" and user.role in {"admin", "developer"}: abort(403)
    roles=[("accountant","مدير حسابات"),("manager","مدير"),("teacher","معلم"),("parent","ولي أمر")]
    if current_user.role in {"admin", "developer"}: roles.insert(0,("admin","Admin"))
    if request.method=="POST":
        email=request.form.get("email",user.email).strip().lower()
        duplicate=User.query.filter(User.email==email, User.id!=user.id).first()
        if duplicate:
            flash("البريد مستخدم بواسطة حساب آخر.","danger"); return redirect(request.url)
        user.full_name=request.form.get("full_name",user.full_name).strip(); user.email=email
        user.phone=request.form.get("phone"); user.whatsapp=request.form.get("whatsapp")
        if current_user.role in {"admin", "developer"} and request.form.get("role") in ALL_USER_ROLES:
            user.role=request.form.get("role")
        stored=_save_profile_photo(request.files.get("photo"), f"user_{user.id}")
        if stored: user.photo=stored
        if request.form.get("remove_photo"): user.photo=None
        pwd=request.form.get("new_password","").strip()
        if pwd:
            if len(pwd)<8: flash("كلمة المرور لا تقل عن 8 أحرف.","danger"); return redirect(request.url)
            user.set_password(pwd)
        if current_user.role != "accountant": user.is_active_user=bool(request.form.get("is_active_user"))
        if user.teacher_profile:
            user.teacher_profile.specialization=request.form.get("specialization")
            user.teacher_profile.bio=request.form.get("bio")
        if user.parent_profile:
            user.parent_profile.address=request.form.get("address")
            user.parent_profile.country=request.form.get("country") or user.parent_profile.country
        db.session.commit(); flash("تم تحديث المستخدم والبروفايل بنجاح.","success")
        return redirect(url_for("users_admin"))
    return render_template("user_edit.html", user=user, roles=roles)

@app.route("/my-profile", methods=["GET", "POST"])
@login_required
def my_profile():
    user = current_user
    if request.method == "POST":
        user.full_name = request.form.get("full_name", user.full_name).strip()
        user.phone = request.form.get("phone"); user.whatsapp = request.form.get("whatsapp")
        stored = _save_profile_photo(request.files.get("photo"), f"user_{user.id}")
        if stored: user.photo = stored
        if request.form.get("remove_photo"): user.photo = None
        pwd = request.form.get("new_password", "").strip()
        if pwd:
            if len(pwd) < 8: flash("كلمة المرور لا تقل عن 8 أحرف.", "danger"); return redirect(request.url)
            user.set_password(pwd)
        if user.role == "teacher" and user.teacher_profile:
            user.teacher_profile.specialization = request.form.get("specialization"); user.teacher_profile.bio = request.form.get("bio")
        elif user.role == "parent" and user.parent_profile:
            user.parent_profile.address = request.form.get("address"); user.parent_profile.country = request.form.get("country") or user.parent_profile.country
        db.session.commit(); flash("تم تحديث بروفايلك.", "success"); return redirect(url_for("my_profile"))
    return render_template("my_profile.html", user=user)

@app.route("/settings/clear-test-data", methods=["POST"])
@login_required
@roles_required("admin", "developer")
def clear_test_data():
    test_domains=("@mawadda.test",)
    test_users=User.query.filter(User.email.like("%@mawadda.test")).all()
    test_ids=[u.id for u in test_users]
    # Demo database can be safely rebuilt; preserve developer/system settings only.
    for model in [ManagerEvaluation, EvaluationAnswer, StudentEvaluation, TeacherEvaluation,
                  Attendance, QuranProgress, LessonSession, Enrollment, ContractSchedule,
                  Payment, TeacherSessionEarning, TeacherPayment, TeacherPayroll,
                  SubscriptionContract, Complaint, TeacherChangeRequest, ApprovalRequest,
                  ActivityTimeline, StudentDocument, Enrollment, Circle, Student, Teacher, Parent]:
        try: model.query.delete(synchronize_session=False)
        except Exception: pass
    for u in test_users:
        db.session.delete(u)
    db.session.commit()
    flash("تم مسح بيانات الاختبار مع الاحتفاظ بحسابات الإدارة والإعدادات.","success")
    return redirect(url_for("users_admin"))

@app.route("/management/evaluation", methods=["GET", "POST"])
@login_required
@roles_required("admin", "developer", "manager")
def management_evaluation():
    if request.method=="POST":
        typ=request.form.get("target_type"); score=max(1,min(10,float(request.form.get("score",0))))
        item=ManagerEvaluation(evaluator_user_id=current_user.id,target_type=typ,score=score,comment=request.form.get("comment"))
        if typ=="student": item.student_id=int(request.form["student_id"])
        else: item.teacher_id=int(request.form["teacher_id"])
        db.session.add(item); db.session.commit(); flash("تم حفظ تقييم الإدارة.","success"); return redirect(url_for("management_evaluation"))
    return render_template("management_evaluation.html",students=Student.query.filter_by(active=True).order_by(Student.full_name).all(),teachers=Teacher.query.join(User).order_by(User.full_name).all(),items=ManagerEvaluation.query.order_by(ManagerEvaluation.created_at.desc()).limit(50).all())

@app.route("/settings/evaluation-questions", methods=["GET", "POST"])
@login_required
@roles_required("admin", "developer", "manager")
def evaluation_questions():
    etype=request.values.get("type","student")
    if request.method=="POST":
        action=request.form.get("action","save")
        if action=="add":
            label=request.form.get("label","").strip(); code=request.form.get("code","").strip() or f"q_{int(datetime.utcnow().timestamp())}"
            if label: db.session.add(EvaluationQuestion(evaluation_type=etype,code=code,label=label,max_score=max(2,min(10,int(request.form.get("max_score",5)))),sort_order=EvaluationQuestion.query.filter_by(evaluation_type=etype).count()+1))
        elif action=="delete":
            q=db.get_or_404(EvaluationQuestion,int(request.form["question_id"])); q.active=False
        elif action=="restore":
            q=db.get_or_404(EvaluationQuestion,int(request.form["question_id"])); q.active=True
        else:
            for q in EvaluationQuestion.query.filter_by(evaluation_type=etype).all():
                q.label=request.form.get(f"label_{q.id}",q.label).strip(); q.max_score=max(2,min(10,int(request.form.get(f"max_{q.id}",q.max_score)))); q.sort_order=int(request.form.get(f"order_{q.id}",q.sort_order)); q.required=bool(request.form.get(f"required_{q.id}"))
        db.session.commit(); flash("تم تحديث أسئلة التقييم.","success"); return redirect(url_for("evaluation_questions",type=etype))
    items=EvaluationQuestion.query.filter_by(evaluation_type=etype).order_by(EvaluationQuestion.sort_order,EvaluationQuestion.id).all()
    return render_template("evaluation_questions.html",items=items,etype=etype)


@app.route("/students/<int:student_id>/documents", methods=["GET", "POST"])
@login_required
def student_documents(student_id):
    student=db.get_or_404(Student,student_id)
    if not can_access_student(student): abort(403)
    if request.method=="POST":
        if not has_permission("documents.manage"): abort(403)
        f=request.files.get("file")
        if not f or not f.filename: flash("اختر ملفًا.","danger")
        else:
            ext=Path(f.filename).suffix.lower()
            if ext not in {".pdf",".jpg",".jpeg",".png",".doc",".docx"}: abort(400)
            stored=f"student_{student.id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}{ext}"
            f.save(os.path.join(app.config["UPLOAD_FOLDER"],stored))
            db.session.add(StudentDocument(student_id=student.id,document_type=request.form.get("document_type") or "أخرى",
                                           original_name=secure_filename(f.filename),stored_name=stored,
                                           notes=request.form.get("notes"),uploaded_by=current_user.id))
            add_timeline(student.id,"document","رفع مستند",request.form.get("document_type"))
            db.session.commit(); flash("تم رفع المستند.","success")
            return redirect(url_for("student_documents",student_id=student.id))
    return render_template("student_documents.html",student=student)


@app.route("/uploads/<path:filename>")
@login_required
def uploaded_file(filename):
    doc=StudentDocument.query.filter_by(stored_name=filename).first_or_404()
    if not can_access_student(doc.student) or not has_permission("documents.view"): abort(403)
    return send_from_directory(app.config["UPLOAD_FOLDER"],filename,as_attachment=True,download_name=doc.original_name)


@app.route("/search")
@login_required
@permission_required("search.global")
def global_search():
    q=request.args.get("q","").strip(); results=[]
    if q:
        like=f"%{q}%"
        students_q=Student.query
        if current_user.role=="teacher":
            students_q=students_q.join(Enrollment).join(Circle).filter(Circle.teacher_id==current_user.teacher_profile.id)
        for x in students_q.filter(db.or_(Student.full_name.ilike(like),Student.student_code.ilike(like))).limit(15):
            results.append(("طالب",x.student_code,x.full_name,url_for("student_profile",student_id=x.id)))
        if current_user.role in {"admin", "developer", "manager"}:
            for x in Teacher.query.join(User).filter(db.or_(User.full_name.ilike(like),Teacher.employee_code.ilike(like))).limit(15): results.append(("معلم",x.employee_code,x.user.full_name,url_for("teacher_account",teacher_id=x.id)))
            for x in SubscriptionContract.query.filter(SubscriptionContract.contract_no.ilike(like)).limit(15): results.append(("عقد",x.contract_no,x.student.full_name,url_for("contract_detail",contract_id=x.id)))
            for x in Complaint.query.filter(db.or_(Complaint.complaint_no.ilike(like),Complaint.subject.ilike(like))).limit(15): results.append(("شكوى",x.complaint_no,x.subject,url_for("complaints")))
    return render_template("global_search.html",q=q,results=results)


@app.route("/api/v1/dashboard")
@login_required
def api_dashboard():
    if current_user.role=="parent": return jsonify({"children":len(current_user.parent_profile.students),"date":date.today().isoformat()})
    if current_user.role=="teacher": return jsonify({"circles":Circle.query.filter_by(teacher_id=current_user.teacher_profile.id,active=True).count(),"date":date.today().isoformat()})
    return jsonify({"students":Student.query.filter_by(active=True).count(),"teachers":Teacher.query.count(),"open_complaints":Complaint.query.filter(Complaint.status!="مغلقة").count(),"date":date.today().isoformat()})


@app.route("/api/v1/students")
@login_required
@permission_required("students.view")
def api_students():
    query=Student.query
    if current_user.role == "parent":
        if not current_user.parent_profile:
            abort(403)
        query=query.filter_by(parent_id=current_user.parent_profile.id)
    elif current_user.role == "teacher":
        if not current_user.teacher_profile:
            abort(403)
        query=query.join(Enrollment).join(Circle).filter(
            Enrollment.active == True, Circle.teacher_id == current_user.teacher_profile.id
        ).distinct()
    elif current_user.role not in {"admin", "developer", "manager"}:
        abort(403)
    data=[{"id":s.id,"code":s.student_code,"name":s.full_name,"level":s.level,"active":s.active} for s in query.order_by(Student.full_name).all()]
    return jsonify(data)


@app.route("/background-jobs")
@login_required
@roles_required("admin", "developer", "manager")
def background_jobs():
    return render_template("background_jobs.html",items=BackgroundJob.query.order_by(BackgroundJob.created_at.desc()).limit(200).all())


@app.cli.command("run-jobs")
def run_jobs():
    jobs=BackgroundJob.query.filter(BackgroundJob.status=="pending",BackgroundJob.scheduled_at<=datetime.utcnow()).all()
    for job in jobs:
        try:
            job.status="running"; job.started_at=datetime.utcnow(); job.attempts+=1; db.session.commit()
            payload=json.loads(job.payload or "{}")
            if job.job_type=="notification":
                create_notification(payload["user_id"],payload["title"],payload["body"],payload.get("action_url"),payload.get("channel","in_app"))
            elif job.job_type=="contract-reminders":
                due=date.today()+timedelta(days=3)
                for c in SubscriptionContract.query.filter(SubscriptionContract.end_date<=due,SubscriptionContract.status=="نشط").all():
                    create_notification(c.student.parent.user.id,"قرب انتهاء الاشتراك",f"العقد {c.contract_no} ينتهي في {c.end_date}.",url_for("contract_detail",contract_id=c.id))
            job.status="done"; job.finished_at=datetime.utcnow(); db.session.commit()
        except Exception as exc:
            db.session.rollback(); job.status="failed"; job.error=str(exc); job.finished_at=datetime.utcnow(); db.session.commit()
    print(f"Processed {len(jobs)} jobs")


@app.errorhandler(403)
def forbidden(_):
    return render_template("403.html"), 403


@app.cli.command("init-db")
def init_db():
    db.create_all()
    default_staff = [
        (os.environ.get("ADMIN_NAME", "Admin"), os.environ.get("ADMIN_EMAIL", "admin@mawadda.local"), "admin", os.environ.get("ADMIN_PASSWORD")),
        (os.environ.get("MANAGER_NAME", "مدير الأكاديمية"), os.environ.get("MANAGER_EMAIL", "manager@mawadda.local"), "manager", os.environ.get("MANAGER_PASSWORD")),
        (os.environ.get("ACCOUNTANT_NAME", "مدير الحسابات"), os.environ.get("ACCOUNTANT_EMAIL", "accounts@mawadda.local"), "accountant", os.environ.get("ACCOUNTANT_PASSWORD")),
    ]
    changed=False
    for name,email,role,password in default_staff:
        user=User.query.filter_by(email=email).first()
        if not user:
            if not password:
                print(f"Skipped {role}: set its password in environment variables first.")
                continue
            user=User(full_name=name,email=email,role=role,is_active_user=True)
            user.set_password(password); db.session.add(user); changed=True
        else:
            if user.role!=role: user.role=role; changed=True
            if not user.is_active_user: user.is_active_user=True; changed=True
    if changed:
        db.session.commit()
        print("Created or repaired management accounts.")
    else:
        print("Database already initialized.")



def ensure_sqlite_schema():
    """Small idempotent migration layer so upgrades do not require deleting mawadda.db."""
    if not app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite"):
        return
    migrations = {
        "parent": [
            ("parent_code", "VARCHAR(30)"),
        ],
        "student": [
            ("photo", "VARCHAR(255)"),
        ],
        "subscription_contract": [
            ("teacher_rate_currency", "VARCHAR(10) DEFAULT 'EGP'"),
            ("exchange_rate_to_egp", "FLOAT DEFAULT 1"),
            ("teacher_rate_mode", "VARCHAR(30) DEFAULT 'fixed_egp'"),
            ("weekly_sessions", "INTEGER DEFAULT 1"),
            ("frozen_from", "DATE"),
            ("frozen_to", "DATE"),
        ],
        "lesson_session": [
            ("actual_minutes", "INTEGER"),
            ("session_type", "VARCHAR(30) DEFAULT 'عادية'"),
            ("cancellation_reason", "VARCHAR(255)"),
            ("rescheduled_from_id", "INTEGER"),
        ],
    }
    with db.engine.begin() as conn:
        for table, columns in migrations.items():
            existing = {row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()}
            for col_name, col_type in columns:
                if col_name not in existing:
                    conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")


def initialize_runtime_defaults():
    db.create_all()
    legacy_developers=User.query.filter_by(role="admin").all()
    for u in legacy_developers: u.role="admin"
    if legacy_developers: db.session.commit()
    permission_defaults = {
        "students.view":"عرض الطلاب", "students.edit":"إدارة الطلاب", "sessions.manage":"إدارة الحصص",
        "finance.view":"عرض المالية", "complaints.manage":"إدارة الشكاوى", "reports.view":"عرض التقارير"
    }
    for code, name in permission_defaults.items():
        if not Permission.query.filter_by(code=code).first(): db.session.add(Permission(code=code, name=name))
    db.session.flush()
    ensure_sqlite_schema()
    ensure_default_sequences()
    defaults = {
        "EGP": 1.0,
        "USD": 50.0,
        "SAR": 13.3,
        "AED": 13.6,
        "KWD": 163.0,
        "QAR": 13.7,
        "EUR": 58.0,
        "GBP": 68.0,
    }
    changed = False
    for currency, rate in defaults.items():
        if not ExchangeRate.query.filter_by(currency=currency).first():
            db.session.add(ExchangeRate(currency=currency, rate_to_egp=rate))
            changed = True
    if changed:
        db.session.commit()

    account_defaults = [
        ("1000", "النقدية والخزائن", "asset"),
        ("1100", "ذمم الطلاب", "asset"),
        ("2000", "مستحقات المعلمين", "liability"),
        ("4000", "إيرادات الاشتراكات", "revenue"),
        ("5000", "مصروف رواتب المعلمين", "expense"),
        ("5900", "مصروفات تشغيلية", "expense"),
    ]
    for code, name, account_type in account_defaults:
        if not Account.query.filter_by(code=code).first():
            db.session.add(Account(code=code, name=name, account_type=account_type))

    permission_defaults = {
        "students.view":"عرض الطلاب", "students.manage":"إدارة الطلاب", "teachers.view":"عرض المعلمين",
        "sessions.view":"عرض الحصص", "sessions.manage":"إدارة الحصص والتقييم",
        "contracts.view":"عرض الاشتراكات", "finance.view":"عرض الحسابات", "teacher_finance.view":"عرض حساب المعلم",
        "complaints.create":"إنشاء شكوى", "complaints.manage":"إدارة الشكاوى",
        "documents.view":"عرض المستندات", "documents.manage":"رفع وإدارة المستندات",
        "reports.view":"عرض التقارير", "search.global":"استخدام البحث الشامل",
        "approvals.view":"عرض طلبات الموافقة"
    }
    for code, name in permission_defaults.items():
        if not Permission.query.filter_by(code=code).first():
            db.session.add(Permission(code=code, name=name))
    db.session.commit()
    role_defaults = {
        "manager": ["students.view","students.manage","teachers.view","sessions.view","sessions.manage","contracts.view","finance.view","teacher_finance.view","complaints.manage","documents.view","documents.manage","reports.view","search.global","approvals.view"],
        "accountant": ["contracts.view","finance.view","teacher_finance.view","reports.view","approvals.view"],
        "teacher": ["students.view","teachers.view","sessions.view","sessions.manage","teacher_finance.view","documents.view","search.global"],
        "parent": ["students.view","teachers.view","sessions.view","contracts.view","documents.view","complaints.create"],
    }
    for role, codes in role_defaults.items():
        for code in codes:
            perm = Permission.query.filter_by(code=code).first()
            if perm and not RolePermission.query.filter_by(role=role, permission_id=perm.id).first():
                db.session.add(RolePermission(role=role, permission_id=perm.id))
    db.session.commit()

with app.app_context():
    initialize_runtime_defaults()
    default_staff = [
        (os.environ.get("ADMIN_NAME", "Admin"), os.environ.get("ADMIN_EMAIL", "admin@mawadda.local"), "admin", os.environ.get("ADMIN_PASSWORD")),
        (os.environ.get("MANAGER_NAME", "مدير الأكاديمية"), os.environ.get("MANAGER_EMAIL", "manager@mawadda.local"), "manager", os.environ.get("MANAGER_PASSWORD")),
        (os.environ.get("ACCOUNTANT_NAME", "مدير الحسابات"), os.environ.get("ACCOUNTANT_EMAIL", "accounts@mawadda.local"), "accountant", os.environ.get("ACCOUNTANT_PASSWORD")),
    ]
    changed=False
    for name,email,role,password in default_staff:
        user=User.query.filter_by(email=email).first()
        if not user:
            if not password:
                print(f"Skipped {role}: set its password in environment variables first.")
                continue
            user=User(full_name=name,email=email,role=role,is_active_user=True)
            user.set_password(password); db.session.add(user); changed=True
        else:
            if user.role!=role: user.role=role; changed=True
            if not user.is_active_user: user.is_active_user=True; changed=True
    if changed: db.session.commit()


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "0") == "1", host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
