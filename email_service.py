from flask_mail import Message
from flask import current_app
from extensions import mail
from models import EmailLog, db
from datetime import datetime

def send_email(to, subject, body, user_id=None):
    """Send email notification"""
    try:
        msg = Message(
            subject=subject,
            recipients=[to],
            body=body,
            html=body  # Support HTML emails
        )
        
        mail.send(msg)
        
        # Log email
        if user_id:
            email_log = EmailLog(
                user_id=user_id,
                email_to=to,
                subject=subject,
                body=body,
                status='sent'
            )
            db.session.add(email_log)
            db.session.commit()
        
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        
        # Log failed email
        if user_id:
            email_log = EmailLog(
                user_id=user_id,
                email_to=to,
                subject=subject,
                body=body,
                status='failed'
            )
            db.session.add(email_log)
            db.session.commit()
        
        return False

def send_mark_in_notification(user, attendance_time):
    """Send mark in notification email"""
    subject = f"Marked In Successfully - {attendance_time.strftime('%Y-%m-%d %H:%M:%S')}"
    body = f"""
    <html>
    <body>
        <h2>Attendance Marked In</h2>
        <p>Hello {user.name},</p>
        <p>You have successfully marked in at {attendance_time.strftime('%Y-%m-%d %H:%M:%S')}.</p>
        <p>Have a great day!</p>
        <br>
        <p>Best regards,<br>AI Attendance System</p>
    </body>
    </html>
    """
    return send_email(user.email, subject, body, user.id)

def send_mark_out_notification(user, attendance_time):
    """Send mark out notification email"""
    subject = f"Marked Out Successfully - {attendance_time.strftime('%Y-%m-%d %H:%M:%S')}"
    body = f"""
    <html>
    <body>
        <h2>Attendance Marked Out</h2>
        <p>Hello {user.name},</p>
        <p>You have successfully marked out at {attendance_time.strftime('%Y-%m-%d %H:%M:%S')}.</p>
        <p>Thank you for your work today!</p>
        <br>
        <p>Best regards,<br>AI Attendance System</p>
    </body>
    </html>
    """
    return send_email(user.email, subject, body, user.id)

def send_break_out_notification(user, attendance_time):
    """Send break out notification email"""
    subject = f"Break Out Successfully - {attendance_time.strftime('%Y-%m-%d %H:%M:%S')}"
    body = f"""
    <html>
    <body>
        <h2>Break Started</h2>
        <p>Hello {user.name},</p>
        <p>You have successfully started your break at {attendance_time.strftime('%Y-%m-%d %H:%M:%S')}.</p>
        <br>
        <p>Best regards,<br>AI Attendance System</p>
    </body>
    </html>
    """
    return send_email(user.email, subject, body, user.id)

def send_break_in_notification(user, attendance_time):
    """Send break in notification email"""
    subject = f"Break In Successfully - {attendance_time.strftime('%Y-%m-%d %H:%M:%S')}"
    body = f"""
    <html>
    <body>
        <h2>Break Ended</h2>
        <p>Hello {user.name},</p>
        <p>You have successfully returned from your break at {attendance_time.strftime('%Y-%m-%d %H:%M:%S')}.</p>
        <br>
        <p>Best regards,<br>AI Attendance System</p>
    </body>
    </html>
    """
    return send_email(user.email, subject, body, user.id)

def send_password_reset_email(user, reset_url):
    """Send password reset email with token link"""
    subject = "Password Reset Request"
    body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <p>Hello {user.name} ,</p>
        <p>You recently requested to reset your password for the AI Attendance System.</p>
        <p>Click the link below to reset it. This link will expire after 10mins</p>
        <p>
            <a href="{reset_url}" style="display:inline-block; padding:11px 22px; background-color:#2980b9; color:white; text-decoration:none; border-radius:6px; font-weight:600;">Reset Password</a>
        </p>
        <p>If you did not request a password reset, please ignore this email or reply to let us know.</p>
        <br>
        <p>Best regards,<br>AI Attendance System</p>
    </body>
    </html>
    """
    return send_email(user.email, subject, body, user.id)
