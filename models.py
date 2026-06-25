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
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    username = db.Column(db.String(80))
    date = db.Column(db.Date, nullable=False)
    mark_in_time = db.Column(db.DateTime)
    break_out_time = db.Column(db.DateTime)
    break_in_time = db.Column(db.DateTime)
    mark_out_time = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='present')  # present, absent, late
    work_type = db.Column(db.String(20)) # full_day, half_day
    # Per-event emotion tracking
    mark_in_emotion = db.Column(db.String(50))   # emotion at mark-in
    break_out_emotion = db.Column(db.String(50)) # emotion at break-out
    break_in_emotion = db.Column(db.String(50))  # emotion at break-in
    mark_out_emotion = db.Column(db.String(50))  # emotion at mark-out
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    is_spoof = db.Column(db.Boolean, default=False)
    working_hours = db.Column(db.Float, default=0.0)
    overtime_hours = db.Column(db.Float, default=0.0)
    mark_in_status = db.Column(db.String(50))
    break_out_status = db.Column(db.String(50))
    break_in_status = db.Column(db.String(50))
    mark_out_status = db.Column(db.String(50))
    overtime_recorded = db.Column(db.Integer, default=0)
    approval_status = db.Column(db.String(20), nullable=True, default=None)
    break_in_auto_generated = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('user_id', 'date', name='unique_user_date'),)

class IdempotencyLog(db.Model):
    request_id = db.Column(db.String(36), primary_key=True)
    response_payload = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class FaceEncoding(db.Model):
    __tablename__ = 'face_encodings'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    encoding_path = db.Column(db.String(255), nullable=False)
    image_path = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

def create_database_views(database):
    """Create reporting database views if they do not exist."""
    try:
        # Drop all views first
        database.session.execute(database.text("DROP VIEW IF EXISTS employee_attendance_report"))
        database.session.execute(database.text("DROP VIEW IF EXISTS employee_notification_report"))
        database.session.execute(database.text("DROP VIEW IF EXISTS email_activity_report"))
        database.session.execute(database.text("DROP VIEW IF EXISTS email_report"))
        
        # Create allowed VIEW only: email_report
        database.session.execute(database.text("""
            CREATE VIEW email_report AS
            SELECT 
                u.name AS employee_name,
                u.email AS email_address,
                'Marked In Successfully - ' || datetime(a.mark_in_time) AS subject,
                'sent' AS status,
                a.mark_in_time AS sent_time
            FROM attendance a
            JOIN user u ON a.user_id = u.id
            WHERE a.mark_in_time IS NOT NULL

            UNION ALL

            SELECT 
                u.name AS employee_name,
                u.email AS email_address,
                'Break Out Successfully - ' || datetime(a.break_out_time) AS subject,
                'sent' AS status,
                a.break_out_time AS sent_time
            FROM attendance a
            JOIN user u ON a.user_id = u.id
            WHERE a.break_out_time IS NOT NULL

            UNION ALL

            SELECT 
                u.name AS employee_name,
                u.email AS email_address,
                'Break In Successfully - ' || datetime(a.break_in_time) AS subject,
                'sent' AS status,
                a.break_in_time AS sent_time
            FROM attendance a
            JOIN user u ON a.user_id = u.id
            WHERE a.break_in_time IS NOT NULL

            UNION ALL

            SELECT 
                u.name AS employee_name,
                u.email AS email_address,
                'Marked Out Successfully - ' || datetime(a.mark_out_time) AS subject,
                'sent' AS status,
                a.mark_out_time AS sent_time
            FROM attendance a
            JOIN user u ON a.user_id = u.id
            WHERE a.mark_out_time IS NOT NULL;
        """))
        database.session.commit()
        print("Database views verified/created successfully.")
    except Exception as e:
        database.session.rollback()
        print(f"Error creating views: {e}")
