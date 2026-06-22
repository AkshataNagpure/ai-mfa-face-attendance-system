from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    mobile = db.Column(db.String(20))
    department = db.Column(db.String(100))
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    profile_pic = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Forgot Password Fields
    security_question = db.Column(db.String(255))
    security_answer_hash = db.Column(db.String(255))
    admin_pin_hash = db.Column(db.String(255))
    reset_token = db.Column(db.String(100))
    reset_token_expiry = db.Column(db.DateTime)
    secret_key = db.Column(db.String(100), unique=True, nullable=True)
    
    # Relationships
    attendances = db.relationship('Attendance', backref='user', lazy=True)
    face_encodings = db.relationship('FaceEncoding', backref='user', lazy=True)
    notifications = db.relationship('Notification', backref='user', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    mark_in_time = db.Column(db.DateTime)
    break_out_time = db.Column(db.DateTime)
    break_in_time = db.Column(db.DateTime)
    mark_out_time = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='present')  # present, absent, late
    work_type = db.Column(db.String(20)) # full_day, half_day
    emotion = db.Column(db.String(50))  # legacy: last-saved emotion (kept for backward compatibility)
    # Per-event emotion tracking
    mark_in_emotion = db.Column(db.String(50))   # emotion at mark-in
    break_out_emotion = db.Column(db.String(50)) # emotion at break-out
    break_in_emotion = db.Column(db.String(50))  # emotion at break-in
    mark_out_emotion = db.Column(db.String(50))  # emotion at mark-out
    location = db.Column(db.String(100))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    is_spoof = db.Column(db.Boolean, default=False)
    net_working_hours = db.Column(db.Float, default=0.0)
    overtime_hours = db.Column(db.Float, default=0.0)
    break_in_auto_generated = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('user_id', 'date', name='unique_user_date'),)

class IdempotencyLog(db.Model):
    request_id = db.Column(db.String(36), primary_key=True)
    response_payload = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class FaceEncoding(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    encoding_path = db.Column(db.String(255), nullable=False)
    image_path = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text)
    type = db.Column(db.String(50))  # email, system, attendance
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class EmailLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    email_to = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(200))
    body = db.Column(db.Text)
    status = db.Column(db.String(20))  # sent, failed
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)


def create_database_views(database):
    """Create reporting database views if they do not exist."""
    try:
        database.session.execute(database.text("""
            CREATE VIEW IF NOT EXISTS employee_attendance_report AS
            SELECT 
                u.name AS employee_name,
                u.department AS department,
                a.date AS date,
                a.mark_in_time AS mark_in_time,
                a.break_out_time AS break_out_time,
                a.break_in_time AS break_in_time,
                a.mark_out_time AS mark_out_time,
                a.net_working_hours AS net_working_hours,
                a.overtime_hours AS overtime_hours,
                a.status AS status,
                a.work_type AS work_type
            FROM attendance a
            JOIN user u ON a.user_id = u.id;
        """))
        database.session.execute(database.text("""
            CREATE VIEW IF NOT EXISTS employee_notification_report AS
            SELECT 
                u.name AS employee_name,
                n.title AS notification_title,
                n.message AS notification_message,
                n.type AS type,
                n.is_read AS read_status,
                n.created_at AS created_date
            FROM notification n
            JOIN user u ON n.user_id = u.id;
        """))
        database.session.execute(database.text("""
            CREATE VIEW IF NOT EXISTS email_activity_report AS
            SELECT 
                u.name AS employee_name,
                el.email_to AS email_address,
                el.subject AS subject,
                el.status AS status,
                el.sent_at AS sent_time
            FROM email_log el
            JOIN user u ON el.user_id = u.id;
        """))
        database.session.commit()
        print("✓ Database views verified/created")
    except Exception as e:
        database.session.rollback()
        print(f"Error creating views: {e}")


