
from flask import render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User, Attendance, FaceEncoding, IdempotencyLog
from datetime import datetime, date, timedelta
from face_recognition_module import FaceRecognitionSystem
from emotion_detection import EmotionDetection
from spoof_detection import SpoofDetection
from email_service import send_mark_in_notification, send_mark_out_notification, send_break_out_notification, send_break_in_notification
from analytics import PredictiveAnalytics, EmployeeInsights
import cv2
import numpy as np
import base64
import os
import pyttsx3
import json
import re
from uuid import uuid4
from werkzeug.utils import secure_filename


# ---------------- UTILS -----------------
def format_duration(hours_float):
    """Convert float hours to 'X hr Y min Z sec' format."""
    if not hours_float:
        return "0 sec"
    total_seconds = int(round(hours_float * 3600))
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    s = total_seconds % 60
    parts = []
    if h > 0: parts.append(f"{h} hr")
    if m > 0: parts.append(f"{m} min")
    if s > 0 or not parts: parts.append(f"{s} sec")
    return " ".join(parts)


def validate_password_strength(password):
    """
    Validate password strength according to the rules:
    - Minimum 8 characters length
    - At least one uppercase letter (A–Z)
    - At least one lowercase letter (a–z)
    - At least one digit (0–9)
    - At least one special character from: @ # $ % ^ & * !
    - No spaces allowed
    """
    errors = []
    if not password:
        return False, ["Password is required."]
        
    if len(password) < 8:
        errors.append("Minimum 8 characters length.")
    if not any(c.isupper() for c in password):
        errors.append("At least one uppercase letter (A–Z).")
    if not any(c.islower() for c in password):
        errors.append("At least one lowercase letter (a–z).")
    if not any(c.isdigit() for c in password):
        errors.append("At least one digit (0–9).")
    
    special_chars = "@#$%^&*!"
    if not any(c in special_chars for c in password):
        errors.append("At least one special character from: @ # $ % ^ & * !")
    if " " in password:
        errors.append("No spaces allowed.")
        
    if errors:
        return False, errors
    return True, "Password is strong and valid."


# ---------------- INITIALIZE SYSTEMS -----------------
face_recognition_system = FaceRecognitionSystem(tolerance=0.5)
emotion_detector = EmotionDetection()
spoof_detector = SpoofDetection()
predictive_analytics = PredictiveAnalytics()
employee_insights = EmployeeInsights()



# ---------------- DASHBOARD HELPER FUNCTION -----------------
def get_ai_response(prompt, user, role='employee'):
    from datetime import date, datetime, timedelta
    from models import db, User, Attendance
    
    # Normalize prompt
    def normalize_text(text):
        return text.lower().strip().replace("’", "'").replace("`", "'")
        
    p = normalize_text(prompt)
    today_dt = date.today()

    # Helper to strip markdown bold markers (**) from all chatbot responses
    def clean(text):
        return text.replace('**', '')
    
    # Helper to calculate working hours for an attendance record
    def get_working_hours(att):
        if not att or not att.mark_in_time:
            return 0.0
        
        break_secs = 0.0
        if att.break_out_time and att.break_in_time:
            break_secs = (att.break_in_time - att.break_out_time).total_seconds()
        elif att.break_out_time:
            # Still on break or missed break-in
            if att.date == date.today():
                break_secs = (datetime.now() - att.break_out_time).total_seconds()
            
        if att.mark_out_time:
            total_secs = (att.mark_out_time - att.mark_in_time).total_seconds()
        else:
            if att.date == date.today():
                total_secs = (datetime.now() - att.mark_in_time).total_seconds()
            else:
                total_secs = 0.0
                
        net_secs = max(0.0, total_secs - break_secs)
        return net_secs / 3600.0

    # Helper to format float hours
    def fmt_hours(hours):
        if not hours or hours <= 0:
            return "0 sec"
        total_seconds = int(round(hours * 3600))
        h = total_seconds // 3600
        m = (total_seconds % 3600) // 60
        s = total_seconds % 60
        parts = []
        if h > 0: parts.append(f"{h} hr")
        if m > 0: parts.append(f"{m} min")
        if s > 0 or not parts: parts.append(f"{s} sec")
        return " ".join(parts)

    # Weekdays in a month helper (excluding Sunday Holiday)
    def get_working_days_in_month(year, month, up_to_today=False):
        import calendar
        _, num_days = calendar.monthrange(year, month)
        if up_to_today and year == today_dt.year and month == today_dt.month:
            limit_day = today_dt.day
        else:
            limit_day = num_days
        
        working_days = 0
        for day in range(1, limit_day + 1):
            d = date(year, month, day)
            if d.weekday() != 6:  # Sunday is index 6
                working_days += 1
        return working_days



    # =========================================================================
    # ADMIN DASHBOARD QUESTIONS
    # =========================================================================
    if role == 'admin':
        # 1. How many employees are present today?
        if "how many employees are present today" in p:
            count = Attendance.query.filter_by(date=today_dt).filter(Attendance.mark_in_time.isnot(None), Attendance.status != 'absent').count()
            return {"success": True, "response": f"There are **{count} employees present** today."}
            
        # 2. How many employees are absent today?
        if "how many employees are absent today" in p:
            total_active = User.query.filter_by(is_admin=False, is_active=True).count()
            present = Attendance.query.filter_by(date=today_dt).filter(Attendance.mark_in_time.isnot(None), Attendance.status != 'absent').count()
            absent = max(0, total_active - present)
            return {"success": True, "response": f"There are **{absent} employees absent** today out of {total_active} active employees."}
            
        # 3. Show today’s attendance summary
        if "today's attendance summary" in p or "todays attendance summary" in p:
            total_active = User.query.filter_by(is_admin=False, is_active=True).count()
            present_records = Attendance.query.filter_by(date=today_dt).filter(Attendance.mark_in_time.isnot(None), Attendance.status != 'absent').all()
            present_count = len(present_records)
            absent_count = max(0, total_active - present_count)
            late_count = sum(1 for r in present_records if r.status == 'late' or (r.mark_in_time and r.mark_in_time.time() > datetime.strptime('09:30:00', '%H:%M:%S').time()))
            
            return {
                "success": True, 
                "response": f" **Today's Attendance Summary:**\n- **Total Active Employees**: {total_active}\n- **Present**: {present_count}\n- **Absent**: {absent_count}\n- **Late Check-ins**: {late_count}"
            }
            
        # 4. What is today’s attendance status of the company?
        if "today's attendance status of the company" in p or "todays attendance status of the company" in p:
            total_active = User.query.filter_by(is_admin=False, is_active=True).count()
            present = Attendance.query.filter_by(date=today_dt).filter(Attendance.mark_in_time.isnot(None), Attendance.status != 'absent').count()
            absent = max(0, total_active - present)
            rate = (present / total_active * 100) if total_active > 0 else 0
            
            if rate >= 90:
                status = "Excellent"
            elif rate >= 75:
                status = "Good"
            elif rate >= 50:
                status = "Average"
            else:
                status = "Needs Improvement"
                
            return {
                "success": True,
                "response": f" The overall attendance status of the company today is **{status}** ({rate:.1f}% attendance rate). **{present} present** and **{absent} absent** out of {total_active} employees."
            }
            
        # 5. Show attendance between two dates
        if "attendance between two dates" in p or "between two dates" in p:
            # Show past 7 days range as default report
            start_date = today_dt - timedelta(days=7)
            records = Attendance.query.filter(Attendance.date >= start_date, Attendance.date <= today_dt).all()
            present = sum(1 for r in records if r.mark_in_time and r.status != 'absent')
            absent = sum(1 for r in records if r.status == 'absent')
            return {
                "success": True,
                "response": f" **Attendance Report (Past 7 days: {start_date} to {today_dt}):**\n- **Present records**: {present}\n- **Absent records**: {absent}\n*(Tip: You can use the 'Attendance Report by Duration' card on the admin dashboard to specify a custom date range!)*"
            }
            
        # 6. What is this week’s attendance report?
        if "this week's attendance report" in p or "this weeks attendance report" in p:
            start_of_week = today_dt - timedelta(days=today_dt.weekday())  # Monday
            records = Attendance.query.filter(Attendance.date >= start_of_week, Attendance.date <= today_dt).all()
            present = sum(1 for r in records if r.mark_in_time and r.status != 'absent')
            absent = sum(1 for r in records if r.status == 'absent')
            return {
                "success": True,
                "response": f" **This Week's Attendance Report (Starting {start_of_week} to {today_dt}):**\n- **Present check-ins**: {present}\n- **Absent days**: {absent}"
            }
            
        # 7. Show monthly attendance summary
        if "monthly attendance summary" in p or "show monthly attendance summary" in p:
            start_of_month = date(today_dt.year, today_dt.month, 1)
            records = Attendance.query.filter(Attendance.date >= start_of_month, Attendance.date <= today_dt).all()
            present = sum(1 for r in records if r.mark_in_time and r.status != 'absent')
            absent = sum(1 for r in records if r.status == 'absent')
            return {
                "success": True,
                "response": f" **Monthly Attendance Summary ({today_dt.strftime('%B %Y')}):**\n- **Total Present check-ins**: {present}\n- **Total Absent records**: {absent}"
            }
            
        # 8. How many employees were present in last 7 days?
        if "present in last 7 days" in p or "present in the last 7 days" in p:
            start_date = today_dt - timedelta(days=7)
            records = Attendance.query.filter(Attendance.date >= start_date, Attendance.date <= today_dt).filter(Attendance.mark_in_time.isnot(None), Attendance.status != 'absent').all()
            unique_emp_ids = set(r.user_id for r in records)
            return {
                "success": True,
                "response": f" In the last 7 days, there were **{len(unique_emp_ids)} unique employees present** in the office."
            }
            
        # 9. Show details of employee [Name]
        match9 = re.search(r'details of (?:employee )?(\w+)', p)
        if not match9:
            match9 = re.search(r'(?:show )?employee (\w+) details', p)
        if not match9:
            m = re.search(r'(\w+) details', p)
            if m and m.group(1) not in ['employee', 'my', 'show']:
                match9 = m
        
        if match9:
            emp_name = match9.group(1).capitalize()
            emp = User.query.filter(User.name.ilike(f'%{emp_name}%')).first()
            if not emp:
                return {"success": True, "response": f"Employee '{emp_name}' was not found in the database. Please verify the name."}
            return {
                "success": True,
                "response": f" **Employee Details - {emp.name}:**\n- **Name**: {emp.name}\n- **Username**: {emp.username}\n- **Email**: {emp.email}\n- **Mobile**: {emp.mobile or 'N/A'}\n- **Department**: {emp.department or 'N/A'}\n- **Status**: {'Active' if emp.is_active else 'Inactive'}"
            }
            
        # 10. How many days was [Name] present this month?
        match10 = re.search(r'(\w+) present', p)
        if match10 and match10.group(1) not in ['are', 'were', 'employees', 'is', 'i']:
            emp_name = match10.group(1).capitalize()
            emp = User.query.filter(User.name.ilike(f'%{emp_name}%')).first()
            if not emp:
                return {"success": True, "response": f"Employee '{emp_name}' was not found in the database."}
            start_of_month = date(today_dt.year, today_dt.month, 1)
            count = Attendance.query.filter_by(user_id=emp.id).filter(Attendance.date >= start_of_month, Attendance.date <= today_dt).filter(Attendance.mark_in_time.isnot(None), Attendance.status != 'absent').count()
            return {"success": True, "response": f"{emp.name} was present for **{count} days** this month."}
            
        # 11. How many days was [Name] absent?
        match11 = re.search(r'(\w+) absent', p)
        if match11 and match11.group(1) not in ['are', 'were', 'employees', 'is', 'i']:
            emp_name = match11.group(1).capitalize()
            emp = User.query.filter(User.name.ilike(f'%{emp_name}%')).first()
            if not emp:
                return {"success": True, "response": f"Employee '{emp_name}' was not found in the database."}
            start_of_month = date(today_dt.year, today_dt.month, 1)
            present_count = Attendance.query.filter_by(user_id=emp.id).filter(Attendance.date >= start_of_month, Attendance.date <= today_dt).filter(Attendance.mark_in_time.isnot(None), Attendance.status != 'absent').count()
            total_working_days = get_working_days_in_month(today_dt.year, today_dt.month, up_to_today=True)
            absent_count = max(0, total_working_days - present_count)
            return {"success": True, "response": f"{emp.name} was absent for **{absent_count} working days** this month (out of {total_working_days} total working days)."}
            
        # 12. Show employee attendance history
        if "employee attendance history" in p or "employee's attendance history" in p:
            records = Attendance.query.order_by(Attendance.date.desc(), Attendance.id.desc()).limit(5).all()
            if not records:
                return {"success": True, "response": "No employee attendance history found."}
            history_lines = []
            for r in records:
                emp = User.query.get(r.user_id)
                name = emp.name if emp else "Unknown"
                status_str = f"{r.status.capitalize()} ({r.work_type.replace('_', ' ').capitalize() if r.work_type else 'Present'})" if r.status != 'absent' else "Absent"
                history_lines.append(f"- **{r.date}**: {name} - {status_str}")
            return {"success": True, "response": " **Recent Attendance History (Last 5 records):**\n" + "\n".join(history_lines)}
            
        # 13. Who has highest attendance this month?
        if "highest attendance this month" in p or "highest attendance" in p:
            start_of_month = date(today_dt.year, today_dt.month, 1)
            all_atts = Attendance.query.filter(Attendance.date >= start_of_month, Attendance.date <= today_dt).filter(Attendance.mark_in_time.isnot(None), Attendance.status != 'absent').all()
            counts = {}
            for a in all_atts:
                counts[a.user_id] = counts.get(a.user_id, 0) + 1
            if not counts:
                return {"success": True, "response": "No attendance records found this month yet."}
            best_user_id = max(counts, key=counts.get)
            best_user = User.query.get(best_user_id)
            if best_user:
                return {"success": True, "response": f" **{best_user.name}** has the highest attendance this month with **{counts[best_user_id]} present days**."}
            return {"success": True, "response": "Unable to calculate highest attendance."}
            
        # 14. Who worked more than 8 hours today?
        if "worked more than 8 hours today" in p or "more than 8 hours today" in p:
            today_atts = Attendance.query.filter_by(date=today_dt).all()
            overachievers = []
            for att in today_atts:
                wh = get_working_hours(att)
                if wh > 8.0:
                    emp = User.query.get(att.user_id)
                    if emp:
                        overachievers.append(f"- **{emp.name}** ({fmt_hours(wh)})")
            if overachievers:
                return {"success": True, "response": " **Worked more than 8 hours today:**\n" + "\n".join(overachievers)}
            return {"success": True, "response": "No employees have worked more than 8 hours today yet."}
            
        # 15. Who did overtime today?
        if "who did overtime today" in p or "overtime today" in p:
            today_atts = Attendance.query.filter_by(date=today_dt).all()
            overtime_list = []
            for att in today_atts:
                wh = get_working_hours(att)
                if wh > 8.0:
                    emp = User.query.get(att.user_id)
                    if emp:
                        ot_val = wh - 8.0
                        overtime_list.append(f"- **{emp.name}**: Overtime of {fmt_hours(ot_val)} (Total: {fmt_hours(wh)})")
            if overtime_list:
                return {"success": True, "response": " **Employees with overtime today:**\n" + "\n".join(overtime_list)}
            return {"success": True, "response": "No employees did overtime today."}
            
        # 16. Who came late today?
        if "who came late today" in p or "came late today" in p:
            today_atts = Attendance.query.filter_by(date=today_dt).all()
            late_list = []
            for att in today_atts:
                if att.status == 'late' or (att.mark_in_time and att.mark_in_time.time() > datetime.strptime('09:30:00', '%H:%M:%S').time()):
                    emp = User.query.get(att.user_id)
                    if emp:
                        check_in_time = att.mark_in_time.strftime('%I:%M:%S %p')
                        late_list.append(f"- **{emp.name}** (Checked in late at {check_in_time})")
            if late_list:
                return {"success": True, "response": " **Late arrivals today:**\n" + "\n".join(late_list)}
            return {"success": True, "response": "Everyone checked in on time today!"}
            
        # 17. Who is most punctual employee?
        if "who is most punctual employee" in p or "most punctual employee" in p or "most punctual" in p:
            start_of_month = date(today_dt.year, today_dt.month, 1)
            all_atts = Attendance.query.filter(Attendance.date >= start_of_month, Attendance.date <= today_dt).filter(Attendance.mark_in_time.isnot(None), Attendance.status != 'absent').all()
            user_punctuality = {}
            for att in all_atts:
                user_punctuality.setdefault(att.user_id, []).append(
                    att.status != 'late' and att.mark_in_time.time() <= datetime.strptime('09:30:00', '%H:%M:%S').time()
                )
            rates = {}
            for uid, list_vals in user_punctuality.items():
                rates[uid] = sum(list_vals) / len(list_vals)
            if not rates:
                return {"success": True, "response": "No data available to calculate punctuality."}
            best_user_id = max(rates, key=rates.get)
            best_user = User.query.get(best_user_id)
            if best_user:
                return {"success": True, "response": f" The most punctual employee this month is **{best_user.name}** with **{rates[best_user_id]*100:.0f}%** on-time check-ins."}
            return {"success": True, "response": "Unable to calculate punctuality statistics."}
            
        # 18. Who has incomplete session today?
        if "incomplete session today" in p:
            today_atts = Attendance.query.filter_by(date=today_dt).filter(Attendance.mark_in_time.isnot(None), Attendance.mark_out_time.is_(None)).all()
            incomplete_list = []
            for att in today_atts:
                emp = User.query.get(att.user_id)
                if emp:
                    incomplete_list.append(f"- **{emp.name}**")
            if incomplete_list:
                return {"success": True, "response": " **Employees with incomplete sessions today (Checked-in but not Checked-out):**\n" + "\n".join(incomplete_list)}
            return {"success": True, "response": "No employees have incomplete sessions today."}
            
        # 19. Who missed break-in today?
        if "who missed break-in today" in p or "missed break-in today" in p:
            today_atts = Attendance.query.filter_by(date=today_dt).filter(Attendance.break_out_time.isnot(None), Attendance.break_in_time.is_(None)).all()
            missed_list = []
            for att in today_atts:
                emp = User.query.get(att.user_id)
                if emp:
                    missed_list.append(f"- **{emp.name}** (Went out on break at {att.break_out_time.strftime('%I:%M %p')} but didn't mark break-in)")
            if missed_list:
                return {"success": True, "response": " **Employees who missed break-in today:**\n" + "\n".join(missed_list)}
            return {"success": True, "response": "No employees missed break-in today."}
            
        # 20. Show attendance statistics for this month
        if "attendance statistics for this month" in p or "statistics for this month" in p:
            start_of_month = date(today_dt.year, today_dt.month, 1)
            records = Attendance.query.filter(Attendance.date >= start_of_month, Attendance.date <= today_dt).all()
            total_days = len(records)
            present_cnt = sum(1 for r in records if r.mark_in_time and r.status != 'absent')
            absent_cnt = sum(1 for r in records if r.status == 'absent')
            late_cnt = sum(1 for r in records if r.status == 'late' or (r.mark_in_time and r.mark_in_time.time() > datetime.strptime('09:30:00', '%H:%M:%S').time()))
            
            return {
                "success": True,
                "response": f" **Monthly Attendance Statistics ({today_dt.strftime('%B %Y')}):**\n- **Total Records Logged**: {total_days}\n- **Present Marks**: {present_cnt}\n- **Absent Marks**: {absent_cnt}\n- **Late Check-ins**: {late_cnt}"
            }

        # Check greetings for Admin
        words = p.split()
        if any(k in words for k in ["hello", "hi", "hey"]):
            return {"success": True, "response": f"Hello {user.name}! I'm TrackHub, your Admin Dashboard AI Assistant. Ask me any of the standard dashboard questions, and I will give you accurate answers."}
        if any(k in words for k in ["bye", "goodbye"]):
            return {"success": True, "response": "Goodbye! Have a productive day!"}
        if any(k in words or k in p for k in ["thanks", "thank you"]):
            return {"success": True, "response": "You're very welcome!"}

        # Fallback for Admin
        return {
            "success": True, 
            "response": "I'm TrackHub, your AI assistant. You can ask me any of the following questions:\n"
                        "1. How many employees are present today?\n"
                        "2. How many employees are absent today?\n"
                        "3. Show today’s attendance summary\n"
                        "4. What is today’s attendance status of the company?\n"
                        "5. Show attendance between two dates\n"
                        "6. What is this week’s attendance report?\n"
                        "7. Show monthly attendance summary\n"
                        "8. How many employees were present in last 7 days?\n"
                        "9. Show details of employee [Name]\n"
                        "10. How many days was [Name] present this month?\n"
                        "11. How many days was [Name] absent?\n"
                        "12. Show employee attendance history\n"
                        "13. Who has highest attendance this month?\n"
                        "14. Who worked more than 8 hours today?\n"
                        "15. Who did overtime today?\n"
                        "16. Who came late today?\n"
                        "17. Who is most punctual employee?\n"
                        "18. Who has incomplete session today?\n"
                        "19. Who missed break-in today?\n"
                        "20. Show attendance statistics for this month"
        }

    # =========================================================================
    # EMPLOYEE DASHBOARD QUESTIONS
    # =========================================================================
    else:
        # 1. How many days was I present this month?
        if "how many days was i present this month" in p or "i present this month" in p:
            start_of_month = date(today_dt.year, today_dt.month, 1)
            count = Attendance.query.filter_by(user_id=user.id).filter(Attendance.date >= start_of_month, Attendance.date <= today_dt).filter(Attendance.mark_in_time.isnot(None), Attendance.status != 'absent').count()
            return {"success": True, "response": f"You were present for **{count} days** this month."}
            
        # 2. How many half days do I have?
        if "how many half days do i have" in p or "half days do i have" in p:
            start_of_month = date(today_dt.year, today_dt.month, 1)
            count = Attendance.query.filter_by(user_id=user.id, work_type='half_day').filter(Attendance.date >= start_of_month, Attendance.date <= today_dt).count()
            return {"success": True, "response": f"You have **{count} half days** recorded this month."}
            
        # 3. What is my attendance percentage?
        if "my attendance percentage" in p:
            start_of_month = date(today_dt.year, today_dt.month, 1)
            present_cnt = Attendance.query.filter_by(user_id=user.id).filter(Attendance.date >= start_of_month, Attendance.date <= today_dt).filter(Attendance.mark_in_time.isnot(None), Attendance.status != 'absent').count()
            total_working_days = get_working_days_in_month(today_dt.year, today_dt.month, up_to_today=True)
            pct = (present_cnt / total_working_days * 100) if total_working_days > 0 else 0.0
            return {"success": True, "response": f"Your attendance percentage for this month is **{pct:.1f}%** ({present_cnt} days present out of {total_working_days} working days)."}
            
        # 4. What are my present dates in May?
        if "present dates in may" in p or "my present dates in may" in p:
            all_records = Attendance.query.filter_by(user_id=user.id).all()
            may_records = [r for r in all_records if r.date.month == 5 and r.mark_in_time and r.status != 'absent']
            dates_list = [r.date.strftime('%B %d, %Y') for r in may_records]
            if dates_list:
                return {"success": True, "response": f" **Your present dates in May:**\n" + "\n".join(f"- {d}" for d in dates_list)}
            return {"success": True, "response": "You don't have any present attendance records in May."}
            
        # 5. On which days was I absent?
        if "on which days was i absent" in p or "days was i absent" in p:
            start_of_month = date(today_dt.year, today_dt.month, 1)
            records = Attendance.query.filter_by(user_id=user.id).filter(Attendance.date >= start_of_month, Attendance.date <= today_dt).all()
            present_dates = set(r.date for r in records if r.mark_in_time and r.status != 'absent')
            
            absent_dates = []
            for day in range(1, today_dt.day + 1):
                d = date(today_dt.year, today_dt.month, day)
                if d.weekday() != 6 and d not in present_dates:  # exclude Sunday Holiday
                    absent_dates.append(d.strftime('%b %d, %Y'))
            if absent_dates:
                return {"success": True, "response": f" **Your absent working days this month:**\n" + "\n".join(f"- {ad}" for ad in absent_dates)}
            return {"success": True, "response": "You haven't been absent on any working days this month! Excellent job!"}
            
        # 6. Show my attendance history
        if "show my attendance history" in p or "my attendance history" in p:
            records = Attendance.query.filter_by(user_id=user.id).order_by(Attendance.date.desc()).limit(10).all()
            if not records:
                return {"success": True, "response": "You have no attendance history yet."}
            history_lines = []
            for r in records:
                status_str = f"{r.status.capitalize()} ({r.work_type.replace('_', ' ').capitalize() if r.work_type else 'Present'})" if r.status != 'absent' else "Absent"
                history_lines.append(f"- **{r.date}**: {status_str}")
            return {"success": True, "response": " **Your Attendance History (Last 10 records):**\n" + "\n".join(history_lines)}
            
        # 7. Show weekly attendance report
        if "show weekly attendance report" in p or "weekly attendance report" in p:
            start_of_week = today_dt - timedelta(days=today_dt.weekday())  # Monday
            records = Attendance.query.filter_by(user_id=user.id).filter(Attendance.date >= start_of_week, Attendance.date <= today_dt).all()
            present = sum(1 for r in records if r.mark_in_time and r.status != 'absent')
            absent = sum(1 for r in records if r.status == 'absent')
            return {"success": True, "response": f" **Your Weekly Attendance Report (Starting {start_of_week} to {today_dt}):**\n- **Present Days**: {present}\n- **Absent Days**: {absent}"}
            
        # 8. Am I present today?
        if "am i present today" in p:
            att = Attendance.query.filter_by(user_id=user.id, date=today_dt).first()
            if att and att.mark_in_time and att.status != 'absent':
                check_in_time = att.mark_in_time.strftime('%I:%M:%S %p')
                return {"success": True, "response": f"Yes, you are **Present** today! You checked in at **{check_in_time}**."}
            return {"success": True, "response": "No, you haven't checked in today yet. Please mark your attendance via the camera modal."}
            
        # 9. What is my working time today?
        if "working time today" in p:
            att = Attendance.query.filter_by(user_id=user.id, date=today_dt).first()
            if not att or not att.mark_in_time:
                return {"success": True, "response": "You haven't checked in today yet, so there is no working time."}
            wh = get_working_hours(att)
            return {"success": True, "response": f"Your working time today is **{fmt_hours(wh)}**."}
            
        # 10. Did I complete full day today?
        if "complete full day today" in p or "did i complete full day today" in p:
            att = Attendance.query.filter_by(user_id=user.id, date=today_dt).first()
            if not att or not att.mark_in_time:
                return {"success": True, "response": "You haven't checked in today yet."}
            wh = get_working_hours(att)
            if wh >= 8.0:
                return {"success": True, "response": f"Yes, you completed a **Full Day** today! You worked {fmt_hours(wh)}."}
            return {"success": True, "response": f"No, you have worked **{fmt_hours(wh)}** today. You need to work at least 8 hours for a Full Day."}
            
        # 11. Did I take break today?
        if "did i take break today" in p or "take break today" in p:
            att = Attendance.query.filter_by(user_id=user.id, date=today_dt).first()
            if not att or not att.break_out_time:
                return {"success": True, "response": "No, you haven't marked a break today."}
            bout = att.break_out_time.strftime('%I:%M:%S %p')
            bin_str = att.break_in_time.strftime('%I:%M:%S %p') if att.break_in_time else "still out on break"
            return {"success": True, "response": f"Yes, you took a break starting at **{bout}** and returned at **{bin_str}**."}
            
        # 12. How many hours did I work today?
        if "hours did i work today" in p:
            att = Attendance.query.filter_by(user_id=user.id, date=today_dt).first()
            if not att or not att.mark_in_time:
                return {"success": True, "response": "You haven't checked in today."}
            wh = get_working_hours(att)
            return {"success": True, "response": f"You worked **{fmt_hours(wh)}** today."}
            
        # 13. Did I do overtime today?
        if "overtime today" in p:
            att = Attendance.query.filter_by(user_id=user.id, date=today_dt).first()
            if not att or not att.mark_in_time:
                return {"success": True, "response": "You haven't checked in today."}
            wh = get_working_hours(att)
            if wh > 8.0:
                ot = wh - 8.0
                return {"success": True, "response": f"Yes, you did **{fmt_hours(ot)}** of overtime today! (Total hours: {fmt_hours(wh)})"}
            return {"success": True, "response": f"No overtime today. You worked {fmt_hours(wh)} so far."}
            
        # 14. What is my monthly overtime?
        if "monthly overtime" in p or "my monthly overtime" in p:
            start_of_month = date(today_dt.year, today_dt.month, 1)
            records = Attendance.query.filter_by(user_id=user.id).filter(Attendance.date >= start_of_month, Attendance.date <= today_dt).all()
            total_ot = 0.0
            for r in records:
                wh = get_working_hours(r)
                if wh > 8.0:
                    total_ot += (wh - 8.0)
            return {"success": True, "response": f"Your total monthly overtime is **{fmt_hours(total_ot)}**."}
            
        # 15. Did I come late today?
        if "did i come late today" in p or "come late today" in p:
            att = Attendance.query.filter_by(user_id=user.id, date=today_dt).first()
            if not att or not att.mark_in_time:
                return {"success": True, "response": "You haven't checked in today yet."}
            if att.status == 'late' or att.mark_in_time.time() > datetime.strptime('09:30:00', '%H:%M:%S').time():
                return {"success": True, "response": f"Yes, you checked in late today at **{att.mark_in_time.strftime('%I:%M:%S %p')}** (Punctual threshold: 09:30 AM)."}
            return {"success": True, "response": f"No, you checked in on time at **{att.mark_in_time.strftime('%I:%M:%S %p')}**! Great job!"}
            
        # 16. Do I have incomplete session?
        if "do i have incomplete session" in p or "incomplete session" in p:
            incomplete_att = Attendance.query.filter_by(user_id=user.id).filter(Attendance.mark_in_time.isnot(None), Attendance.mark_out_time.is_(None)).order_by(Attendance.date.desc()).first()
            if incomplete_att:
                return {"success": True, "response": f"Yes, you have an incomplete session on **{incomplete_att.date}** (checked in at {incomplete_att.mark_in_time.strftime('%I:%M %p')} but didn't mark out)."}
            return {"success": True, "response": "No, you don't have any incomplete sessions."}
            
        # 17. Did I miss break-in today?
        if "did i miss break-in today" in p or "missed break-in today" in p:
            att = Attendance.query.filter_by(user_id=user.id, date=today_dt).first()
            if att and att.break_out_time and not att.break_in_time:
                return {"success": True, "response": "Yes, you marked break-out but missed marking break-in!"}
            return {"success": True, "response": "No, you haven't missed any break-in today."}
            
        # 18. What is my emotion today?
        if "my emotion today" in p or "emotion today" in p:
            att = Attendance.query.filter_by(user_id=user.id, date=today_dt).first()
            if att and att.mark_in_emotion:
                return {"success": True, "response": f"Your detected emotion today during check-in was **{att.mark_in_emotion.capitalize()}**."}
            return {"success": True, "response": "No emotion data recorded for you today."}
            
        # 19. Show my weekly mood trend
        if "show my mood trend" in p or "weekly mood trend" in p:
            start_date = today_dt - timedelta(days=7)
            records = Attendance.query.filter_by(user_id=user.id).filter(Attendance.date >= start_date, Attendance.date <= today_dt).all()
            emotions = []
            for r in records:
                if r:
                    for emo in (r.mark_in_emotion, r.break_out_emotion, r.break_in_emotion, r.mark_out_emotion):
                        if emo and emo != 'not recorded':
                            emotions.append(emo.lower())
            if not emotions:
                return {"success": True, "response": "No emotion data recorded for you in the past 7 days."}
            counts = {}
            for emo in emotions:
                counts[emo] = counts.get(emo, 0) + 1
            trend_lines = [f"- **{emo.capitalize()}**: {cnt} times" for emo, cnt in counts.items()]
            return {"success": True, "response": " **Your Weekly Mood Trend:**\n" + "\n".join(trend_lines)}
            
        # 20. Was my attendance email sent successfully?
        if "attendance email sent successfully" in p or "email sent successfully" in p:
            latest_email = db.session.execute(
                db.text("SELECT subject, status, sent_time FROM email_report WHERE email_address = :email ORDER BY sent_time DESC LIMIT 1"),
                {'email': user.email}
            ).fetchone()
            if latest_email:
                status_emoji = "" if latest_email[1] == 'sent' else ""
                sent_time_str = latest_email[2]
                if isinstance(sent_time_str, str):
                    try:
                        date_str = sent_time_str.split('.')[0]
                        dt = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                        sent_time_formatted = dt.strftime('%Y-%m-%d %I:%M %p')
                    except Exception:
                        sent_time_formatted = sent_time_str
                else:
                    sent_time_formatted = sent_time_str.strftime('%Y-%m-%d %I:%M %p') if sent_time_str else 'N/A'
                return {"success": True, "response": f"{status_emoji} Your last attendance email ('{latest_email[0]}') was sent successfully at **{sent_time_formatted}**."}
            return {"success": True, "response": "No attendance emails have been sent to you yet."}

        # Check greetings for Employee
        words = p.split()
        if any(k in words for k in ["hello", "hi", "hey"]):
            return {"success": True, "response": f"Hello {user.name}! I'm TrackHub, your Employee Dashboard AI Assistant. Ask me any of the standard dashboard questions, and I will give you accurate answers."}
        if any(k in words for k in ["bye", "goodbye"]):
            return {"success": True, "response": "Goodbye! Have a productive day!"}
        if any(k in words or k in p for k in ["thanks", "thank you"]):
            return {"success": True, "response": "You're very welcome!"}

        # Fallback for Employee
        return {
            "success": True,
            "response": "I'm TrackHub, your AI assistant. You can ask me any of the following questions:\n"
                        "1. How many days was I present this month?\n"
                        "2. How many half days do I have?\n"
                        "3. What is my attendance percentage?\n"
                        "4. What are my present dates in May?\n"
                        "5. On which days was I absent?\n"
                        "6. Show my attendance history\n"
                        "7. Show weekly attendance report\n"
                        "8. Am I present today?\n"
                        "9. What is my working time today?\n"
                        "10. Did I complete full day today?\n"
                        "11. Did I take break today?\n"
                        "12. How many hours did I work today?\n"
                        "13. Did I do overtime today?\n"
                        "14. What is my monthly overtime?\n"
                        "15. Did I come late today?\n"
                        "16. Do I have incomplete session?\n"
                        "17. Did I miss break-in today?\n"
                        "18. What is my emotion today?\n"
                        "19. Show my weekly mood trend\n"
                        "20. Was my attendance email sent successfully?"
        }
    
def get_available_months():
    from datetime import date, timedelta
    from dateutil.relativedelta import relativedelta
    months = []
    curr = date.today()
    start = date(2025, 9, 1)
    while curr >= start:
        months.append({
            "name": curr.strftime("%B %Y"),
            "month": curr.month,
            "year": curr.year
        })
        curr -= relativedelta(months=1)
    return months


# ---------------- ROUTE REGISTRATION -----------------
def register_routes(app):

    @app.route('/')
    def home():
        return render_template('home.html')

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            user = User.query.filter_by(username=username).first()

            if user and user.check_password(password) and user.is_active:
                login_user(user)
                return redirect(url_for('admin_dashboard' if user.is_admin else 'employee_dashboard'))
            else:
                flash('Invalid username or password', 'error')
        return render_template('login.html')

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        flash('You have been logged out.', 'info')
        return redirect(url_for('home'))

    # ---------------- FORGOT PASSWORD -----------------
    @app.route('/api/forgot-password/check-user', methods=['POST'])
    def check_user_role():
        data = request.json
        username = data.get('username')
        if not username:
            return jsonify({'success': False, 'message': 'Username required'})
        
        user = User.query.filter_by(username=username).first()
        if not user:
            return jsonify({'success': False, 'message': 'User not found'})
            
        if user.is_admin:
            return jsonify({
                'success': True,
                'is_admin': True
            })
        else:
            # It's an employee, generate token and send email
            import uuid
            from email_service import send_password_reset_email
            
            if not user.email:
                return jsonify({'success': False, 'message': 'No email associated with this employee'})
                
            token = str(uuid.uuid4())
            user.reset_token = token
            user.reset_token_expiry = datetime.utcnow() + timedelta(minutes=10)
            db.session.commit()
            
            reset_url = request.host_url.rstrip('/') + url_for('reset_password', token=token)
            sent = send_password_reset_email(user, reset_url)
            
            if sent:
                return jsonify({'success': True, 'is_admin': False})
            else:
                return jsonify({'success': False, 'message': 'Failed to send email. Please check configuration.'})

    @app.route('/api/forgot-password/reset-admin', methods=['POST'])
    def reset_admin_password():
        data = request.json
        username = data.get('username')
        answer = data.get('answer')
        pin = data.get('pin')
        new_password = data.get('new_password')
        
        if not all([username, answer, pin, new_password]):
            return jsonify({'success': False, 'message': 'All fields required'})
            
        user = User.query.filter_by(username=username, is_admin=True).first()
        if not user:
            return jsonify({'success': False, 'message': 'Admin not found'})
            
        from werkzeug.security import check_password_hash
        
        if not check_password_hash(user.security_answer_hash, answer):
            return jsonify({'success': False, 'message': 'Incorrect security answer'})
            
        if not check_password_hash(user.admin_pin_hash, pin):
            return jsonify({'success': False, 'message': 'Incorrect admin PIN'})
            
        user.set_password(new_password)
        db.session.commit()
        return jsonify({'success': True})

    @app.route('/admin/forgot-password', methods=['GET', 'POST'])
    def admin_forgot_password():
        if request.method == 'POST':
            username = request.form.get('username')
            secret_key = request.form.get('secret_key')
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')

            if not all([username, secret_key, password, confirm_password]):
                flash('All fields are required.', 'error')
                return render_template('admin_forgot_password.html')

            if password != confirm_password:
                flash('Passwords do not match.', 'error')
                return render_template('admin_forgot_password.html')

            is_valid, msg_or_errors = validate_password_strength(password)
            if not is_valid:
                for err in msg_or_errors:
                    flash(err, 'error')
                return render_template('admin_forgot_password.html')

            user = User.query.filter_by(username=username, is_admin=True).first()
            if not user:
                flash('Admin username not found.', 'error')
                return render_template('admin_forgot_password.html')

            if user.secret_key != secret_key:
                flash('Incorrect recovery secret key.', 'error')
                return render_template('admin_forgot_password.html')

            user.set_password(password)
            db.session.commit()
            
            flash(f"{msg_or_errors} Admin password has been reset successfully. You can now login.", 'success')
            return redirect(url_for('login'))

        return render_template('admin_forgot_password.html')

    @app.route('/reset-password/<token>', methods=['GET', 'POST'])
    def reset_password(token):
        user = User.query.filter_by(reset_token=token).first()
        if not user or not user.reset_token_expiry or user.reset_token_expiry < datetime.utcnow():
            flash('Invalid or expired reset token.', 'error')
            return redirect(url_for('login'))
            
        if request.method == 'POST':
            new_password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')

            if not new_password or not confirm_password:
                flash('All fields are required.', 'error')
                return render_template('reset_password.html', token=token)

            if new_password != confirm_password:
                flash('Passwords do not match.', 'error')
                return render_template('reset_password.html', token=token)

            is_valid, msg_or_errors = validate_password_strength(new_password)
            if not is_valid:
                for err in msg_or_errors:
                    flash(err, 'error')
                return render_template('reset_password.html', token=token)

            user.set_password(new_password)
            user.reset_token = None
            user.reset_token_expiry = None
            db.session.commit()
            flash(f"{msg_or_errors} Password has been reset successfully. You can now login.", 'success')
            return redirect(url_for('login'))
                
        return render_template('reset_password.html', token=token)

    @app.route('/uploads/<filename>')
    def uploaded_file(filename):
        from flask import send_from_directory
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

    # ---------------- ADMIN DASHBOARD -----------------

    @app.route('/admin/dashboard')
    @login_required
    def admin_dashboard():
        if not current_user.is_admin:
            return redirect(url_for('employee_dashboard'))

        today = date.today()
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date() if start_date_str else today
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date() if end_date_str else today

        all_employees = User.query.filter_by(is_admin=False, is_active=True).all()
        total_employees = len(all_employees)

        attendances = Attendance.query.filter(Attendance.date >= start_date, Attendance.date <= end_date).all()
        
        duration_days = (end_date - start_date).days + 1
        if duration_days < 1:
            duration_days = 1

        attendance_report = []
        for emp in all_employees:
            emp_attendances = [a for a in attendances if a.user_id == emp.id and a.mark_in_time and a.status != 'absent']
            present_days = len(emp_attendances)
            absent_days = max(0, duration_days - present_days)
            
            attendance_report.append({
                "name": emp.name,
                "department": emp.department,
                "present_days": present_days,
                "absent_days": absent_days
            })

        present_count = sum(emp['present_days'] for emp in attendance_report)
        absent_count = sum(emp['absent_days'] for emp in attendance_report)
        total_records = present_count + absent_count

        # Today's Specific Counts (Always Today)
        today_atts = Attendance.query.filter_by(date=today).all()
        today_present = sum(1 for a in today_atts if a.mark_in_time and a.status != 'absent')
        today_absent = max(0, total_employees - today_present)

        predicted_absences = predictive_analytics.predict_absent_employees() or []
        punctuality_data = employee_insights.get_punctuality_analytics() or {}
        emotion_trends = employee_insights.get_emotion_trends() or {}

        # Fetch images for employees
        employees_with_images = []
        for emp in all_employees:
            # Priority: 1. user.profile_pic, 2. Latest FaceEncoding
            image_url = None
            if emp.profile_pic:
                image_url = url_for('uploaded_file', filename=os.path.basename(emp.profile_pic))
            
            if not image_url:
                face_encoding = FaceEncoding.query.filter_by(user_id=emp.id).order_by(FaceEncoding.created_at.desc()).first()
                if face_encoding and face_encoding.image_path:
                    image_url = url_for('uploaded_file', filename=os.path.basename(face_encoding.image_path))
            
            # Fetch today's attendance from the already-fetched today_atts list
            # (today_atts is always scoped to today, independent of the date range filter)
            today_att = next((a for a in today_atts if a.user_id == emp.id), None)
            
            # Most recent emotion: prefer the latest event recorded
            recent_emotion = '-'
            if today_att:
                for emo_field in (today_att.mark_out_emotion, today_att.break_in_emotion,
                                  today_att.break_out_emotion, today_att.mark_in_emotion):
                    if emo_field and emo_field.strip().lower() not in ('', 'none', 'null', 'not recorded'):
                        recent_emotion = emo_field.strip().capitalize()
                        break

            att_info = {
                'mark_in': today_att.mark_in_time.strftime('%I:%M %p') if today_att and today_att.mark_in_time else '-',
                'break_out': today_att.break_out_time.strftime('%I:%M %p') if today_att and today_att.break_out_time else '-',
                'break_in': today_att.break_in_time.strftime('%I:%M %p') if today_att and today_att.break_in_time else '-',
                'mark_out': today_att.mark_out_time.strftime('%I:%M %p') if today_att and today_att.mark_out_time else '-',
                'emotion': recent_emotion
            }
            
            employees_with_images.append({
                'id': emp.id,
                'name': emp.name,
                'username': emp.username,
                'email': emp.email,
                'department': emp.department,
                'image_url': image_url,
                'today_attendance': att_info
            })

        # Generate rolling window for reports (Since Sept 1, 2025)
        attendance_dates = []
        curr = today
        limit = date(2025, 9, 1)
        while curr >= limit:
            attendance_dates.append(curr.strftime('%Y-%m-%d'))
            curr -= timedelta(days=1)

        return render_template(
            'admin_dashboard.html',
            total_employees=total_employees,
            total_attendances=total_records,
            present_count=present_count,
            absent_count=absent_count,
            predicted_absences=predicted_absences,
            punctuality_data=punctuality_data,
            emotion_trends=emotion_trends,
            employees=employees_with_images,
            attendance_report=attendance_report,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            attendance_dates=attendance_dates,
            available_months=get_available_months(),
            today_present=today_present,
            today_absent=today_absent
        )


# ---------------- ADMIN EMPLOYEE DETAILS API -----------------
    @app.route('/api/admin/employee_details/<int:user_id>')
    @login_required
    def employee_details_api(user_id):
        if not current_user.is_admin:
            return jsonify({"success": False, "message": "Unauthorized"}), 403

        user = User.query.get_or_404(user_id)
        
        # Calculate stats
        today = date.today()
        all_attendances = Attendance.query.filter_by(user_id=user.id).all()
        total_present = sum(1 for att in all_attendances if att and att.mark_in_time and att.status != 'absent')
        
        # Calculate Full/Half/Short day based on timing logic
        total_full_day = 0
        total_half_day = 0
        total_short_day = 0
        for att in all_attendances:
            if not att or not att.mark_in_time or att.status == 'absent':
                continue
            
            if att.work_type == 'full_day':
                total_full_day += 1
            elif att.work_type == 'half_day':
                total_half_day += 1
            elif att.work_type == 'short_day':
                total_short_day += 1
        
        valid_attendances = [att for att in all_attendances if att]
        if valid_attendances:
            first_day = min(att.date for att in valid_attendances)
        else:
            first_day = today
        
        total_days = sum(1 for i in range((today - first_day).days + 1)
                         if (first_day + timedelta(days=i)).weekday() < 6)
        total_absent = max(total_days - total_present, 0)
        
        # Emotion trend
        try:
            emotion_trend_data = emotion_detector.get_emotion_trend(user.id, days=7)
            emotion_counts = emotion_trend_data.get('counts', {})
        except Exception:
            emotion_counts = {}
            for att in all_attendances:
                if att:
                    for emo in (att.mark_in_emotion, att.break_out_emotion, att.break_in_emotion, att.mark_out_emotion):
                        if emo and emo != 'not recorded':
                            emotion_counts[emo.lower()] = emotion_counts.get(emo.lower(), 0) + 1
        
        notifications = []
        
        # Query from email_report view
        email_rows = db.session.execute(
            db.text("SELECT subject, status, sent_time FROM email_report WHERE email_address = :email ORDER BY sent_time DESC"),
            {'email': user.email}
        ).fetchall()
        
        email_logs = []
        for row in email_rows:
            sent_time_val = row[2]
            if isinstance(sent_time_val, str):
                try:
                    date_str = sent_time_val.split('.')[0]
                    dt = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                except Exception:
                    dt = datetime.utcnow()
            else:
                dt = sent_time_val or datetime.utcnow()
            
            class DummyLog:
                def __init__(self, subject, status, sent_at):
                    self.subject = subject
                    self.status = status
                    self.sent_at = sent_at
            
            email_logs.append(DummyLog(row[0], row[1], dt))
        
        # Profile image
        # Priority: 1. user.profile_pic, 2. Latest FaceEncoding
        image_url = None
        if user.profile_pic:
            image_url = url_for('uploaded_file', filename=os.path.basename(user.profile_pic))
        
        if not image_url:
            face_encoding = FaceEncoding.query.filter_by(user_id=user.id).order_by(FaceEncoding.created_at.desc()).first()
            if face_encoding and face_encoding.image_path:
                image_url = url_for('uploaded_file', filename=os.path.basename(face_encoding.image_path))

        return jsonify({
            "success": True,
            "profile": {
                "name": user.name,
                "username": user.username,
                "email": user.email,
                "department": user.department,
                "mobile": user.mobile or 'N/A',
                "image_url": image_url
            },
            "stats": {
                "present": total_present,
                "absent": total_absent,
                "total": total_days,
                "full_day": total_full_day,
                "half_day": total_half_day,
                "short_day": total_short_day
            },
            "emotion_trend": emotion_counts,
            "notifications": [
                {"title": n.title, "message": n.message, "created_at": n.created_at.strftime('%Y-%m-%d %H:%M')}
                for n in notifications
            ],
            "email_logs": [
                {"subject": l.subject, "status": l.status, "sent_at": l.sent_at.strftime('%Y-%m-%d %H:%M')}
                for l in email_logs
            ]
        })

    # ---------------- ADMIN APPROVE ATTENDANCE API -----------------
    @app.route('/api/admin/approve_attendance', methods=['POST'])
    @login_required
    def approve_attendance():
        if not current_user.is_admin:
            return jsonify({"success": False, "message": "Unauthorized"}), 403

        data = request.json or {}
        employee_id = data.get('employee_id')
        date_str = data.get('date')
        decision = data.get('decision') # 'full_day' or 'half_day'

        if not employee_id or not date_str or not decision:
            return jsonify({"success": False, "message": "Missing parameters"}), 400

        if decision not in ('full_day', 'half_day', 'short_day', 'absent'):
            return jsonify({"success": False, "message": "Invalid decision. Must be full_day, half_day, short_day, or absent."}), 400

        try:
            query_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({"success": False, "message": "Invalid date format"}), 400

        attendance = Attendance.query.filter_by(user_id=employee_id, date=query_date).first()
        if not attendance:
            return jsonify({"success": False, "message": "Attendance record not found"}), 404

        if attendance.work_type != 'admin_approval' or attendance.approval_status != 'pending':
            return jsonify({"success": False, "message": "This record does not require approval"}), 400

        if decision == 'absent':
            attendance.status = 'absent'
            attendance.work_type = 'absent'
            attendance.working_hours = 0.0
            attendance.overtime_hours = 0.0
            attendance.approval_status = 'approved'
            msg = "Attendance marked as Absent."
        else:
            attendance.work_type = decision
            attendance.status = 'present'
            attendance.approval_status = 'approved'
            if decision == 'full_day':
                attendance.working_hours = 8.0
                if not attendance.overtime_hours:
                    attendance.overtime_hours = 0.0
            elif decision == 'half_day':
                attendance.working_hours = 4.0
                if not attendance.overtime_hours:
                    attendance.overtime_hours = 0.0
            elif decision == 'short_day':
                attendance.working_hours = min(attendance.working_hours or 0.0, 4.0)
                if not attendance.overtime_hours:
                    attendance.overtime_hours = 0.0
            msg = f"Attendance successfully approved as {decision.replace('_', ' ').title()}."

        db.session.commit()
        return jsonify({"success": True, "message": msg})


# ---------------- ADMIN ATTENDANCE REPORT -----------------
    @app.route('/api/admin/attendance_report')
    @login_required
    def attendance_report_api():
        if not current_user.is_admin:
            return jsonify({"success": False, "message": "Unauthorized"}), 403

        date_str = request.args.get('date')
        if not date_str:
            return jsonify({"success": False, "message": "Date required"}), 400

        from datetime import datetime, date
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        today = date.today()

    # ATTENDANCE REPORT
        attendances = Attendance.query.filter(db.func.date(Attendance.date) == date_obj).all()
        employees = User.query.filter_by(is_admin=False, is_active=True).all()

        #  HOLIDAY CHECK (Sunday) - Only if NO records exist
        if date_obj.weekday() == 6 and not attendances:  # Sunday=6
            return jsonify({
                "success": True,
                "special": True,
                "type": "holiday",
                "message": f" It's Sunday — a weekend holiday! No attendance recorded.",
                "report": {"present": [], "absent": []}
        })

        present, absent = [], []
        present_ids = {a.user_id for a in attendances if a.status != 'absent'}

        for emp in employees:
            if emp.id in present_ids:
                att = next((a for a in attendances if a.user_id == emp.id), None)
                present.append({
                    "name": emp.name,
                    "department": emp.department,
                    "mark_in": att.mark_in_time.strftime("%H:%M") if att.mark_in_time else "-",
                    "mark_out": att.mark_out_time.strftime("%H:%M") if att.mark_out_time else "-"
            })
            else:
                absent.append({
                    "name": emp.name,
                    "department": emp.department,
                    "mark_in": "-",
                    "mark_out": "-"
            })

        return jsonify({
            "success": True,
            "special": False,
            "type": "normal",
            "message": f"Attendance report for {date_obj.strftime('%d-%m-%Y')}",
            "report": {"present": present, "absent": absent}
    })
        
    # ---------------- EMPLOYEE DASHBOARD -----------------
    @app.route('/employee/dashboard')
    @login_required
    def employee_dashboard():
        if current_user.is_admin:
            return redirect(url_for('admin_dashboard'))

        today = date.today()
        today_attendance = Attendance.query.filter_by(user_id=current_user.id, date=today).first()

        all_attendances = Attendance.query.filter_by(user_id=current_user.id).all()
        total_present = sum(1 for att in all_attendances if att and att.mark_in_time)

        valid_attendances = [att for att in all_attendances if att]
        if valid_attendances:
            first_day = min(att.date for att in valid_attendances)
        else:
            first_day = today
        
        # Pre-calculate attendance dates for the dropdown (From Sept 1, 2025)
        attendance_dates = []
        dropdown_start = date(2025, 9, 1)
        curr_date = today
        while curr_date >= dropdown_start:
            attendance_dates.append(curr_date.strftime('%Y-%m-%d'))
            curr_date -= timedelta(days=1)

        # Calculate statistics from first day
        total_days_count = sum(1 for i in range((today - first_day).days + 1)
                               if (first_day + timedelta(days=i)).weekday() < 6)
        total_absent_count = max(0, total_days_count - total_present)

        notifications = []
        
        # Query from email_report view
        email_rows = db.session.execute(
            db.text("SELECT subject, status, sent_time FROM email_report WHERE email_address = :email ORDER BY sent_time DESC"),
            {'email': current_user.email}
        ).fetchall()
        
        email_logs = []
        for row in email_rows:
            sent_time_val = row[2]
            if isinstance(sent_time_val, str):
                try:
                    date_str = sent_time_val.split('.')[0]
                    dt = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                except Exception:
                    dt = datetime.utcnow()
            else:
                dt = sent_time_val or datetime.utcnow()
            
            class DummyLog:
                def __init__(self, subject, status, sent_at):
                    self.subject = subject
                    self.status = status
                    self.sent_at = sent_at
            
            email_logs.append(DummyLog(row[0], row[1], dt))

        # Emotion data (Strictly Weekly - Last 7 Days)
        try:
            emotion_trend_data = emotion_detector.get_emotion_trend(current_user.id, days=7)
            emotion_counts = {k: v for k, v in emotion_trend_data.get('counts', {}).items() if v > 0}
        except Exception:
            emotion_counts = {}
            seven_days_ago = today - timedelta(days=7)
            recent_attendances = [a for a in all_attendances if a and a.date >= seven_days_ago]
            for att in recent_attendances:
                if att:
                    for emo in (att.mark_in_emotion, att.break_out_emotion, att.break_in_emotion, att.mark_out_emotion):
                        if emo and emo != 'not recorded':
                            emotion_counts[emo.lower()] = emotion_counts.get(emo.lower(), 0) + 1

        emotion_has_data = bool(emotion_counts)
        
        # Calculate Full/Half/Short day based on timing logic (Historical & Real-time)
        total_full_day = 0
        total_half_day = 0
        total_short_day = 0
        for att in all_attendances:
            if not att or not att.mark_in_time or att.status == 'absent':
                continue
            
            if att.work_type == 'full_day':
                total_full_day += 1
            elif att.work_type == 'half_day':
                total_half_day += 1
            elif att.work_type == 'short_day':
                total_short_day += 1

        # Profile image
        image_url = None
        if current_user.profile_pic:
            image_url = url_for('uploaded_file', filename=os.path.basename(current_user.profile_pic))
        else:
            face_encoding = FaceEncoding.query.filter_by(user_id=current_user.id).order_by(FaceEncoding.created_at.desc()).first()
            if face_encoding and face_encoding.image_path:
                image_url = url_for('uploaded_file', filename=os.path.basename(face_encoding.image_path))

        return render_template(
            'employee_dashboard.html',
            attendance=today_attendance,
            total_attendances=total_days_count,
            present_count=total_present,
            absent_count=total_absent_count,
            full_day_count=total_full_day,
            half_day_count=total_half_day,
            short_day_count=total_short_day,
            notifications=notifications,
            email_logs=email_logs,
            emotion_trend=emotion_counts,
            emotion_has_data=emotion_has_data,
            total_present=total_present,
            total_absent=total_absent_count,
            attendance_dates=attendance_dates,
            available_months=get_available_months(),
            image_url=image_url
        )


    # ---------------- MONTHLY STATS API -----------------
    @app.route('/api/attendance/monthly-stats')
    @login_required
    def monthly_stats_api():
        user_id = request.args.get('employee_id')
        month = int(request.args.get('month', date.today().month))
        year = int(request.args.get('year', date.today().year))

        if not user_id:
            user_id = current_user.id
        
        # Security check
        if not current_user.is_admin and int(current_user.id) != int(user_id):
            return jsonify({"success": False, "message": "Unauthorized"}), 403

        # Start and end of the month
        import calendar
        last_day = calendar.monthrange(year, month)[1]
        start_date = date(year, month, 1)
        end_date = date(year, month, last_day)
        
        # Don't count days in the future
        today = date.today()
        if end_date > today:
            end_date = today

        # Calculate working days (Mon-Sat)
        total_working_days = 0
        curr = start_date
        while curr <= end_date:
            if curr.weekday() < 6: # Monday (0) to Saturday (5)
                total_working_days += 1
            curr += timedelta(days=1)

        # Get attendance records (Only those not finalized as absent)
        attendances = Attendance.query.filter(
            Attendance.user_id == user_id,
            Attendance.date >= start_date,
            Attendance.date <= end_date,
            Attendance.mark_in_time.isnot(None),
            Attendance.status != 'absent'
        ).all()

        present_count = len(attendances)
        absent_count = max(0, total_working_days - present_count)
        
        # Full/Half/Short Day breakdown
        full_day = 0
        half_day = 0
        short_day = 0
        total_working_hours = 0
        total_overtime_hours = 0

        for att in attendances:
            working_hours = att.working_hours or 0.0
            overtime = att.overtime_hours or 0.0
            total_working_hours += working_hours
            total_overtime_hours += overtime
            
            if att.work_type == 'full_day':
                full_day += 1
            elif att.work_type == 'half_day':
                half_day += 1
            elif att.work_type == 'short_day':
                short_day += 1

        attendance_percentage = (present_count / total_working_days * 100) if total_working_days > 0 else 0

        return jsonify({
            "success": True,
            "stats": {
                "total_working_days": total_working_days,
                "present_count": present_count,
                "absent_count": absent_count,
                "full_day": full_day,
                "half_day": half_day,
                "short_day": short_day,
                "percentage": round(attendance_percentage, 1),
                "working_time": format_duration(total_working_hours),
                "overtime": format_duration(total_overtime_hours)
            }
        })
    @app.route('/api/get-attendance', methods=['GET'])
    @login_required
    def get_attendance():
        user_id = request.args.get('employee_id')
        date_str = request.args.get('date')

        if not user_id:
            user_id = str(current_user.id)

        if not date_str:
            return jsonify({'success': False, 'message': 'Missing date parameter'})
            
        # Ensure user can only query themselves unless admin
        if not current_user.is_admin and str(current_user.id) != user_id:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403

        try:
            query_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid date format'})

        # Check if the employee was registered on/before the queried date
        user = User.query.get(int(user_id))
        if not user:
            return jsonify({'success': False, 'message': 'Employee not found'})

        if user.created_at:
            registration_date = user.created_at.date()
            if query_date < registration_date:
                return jsonify({
                    'success': True,
                    'is_not_registered': True,
                    'date': date_str,
                    'message': f'Not Registered - Employee was registered on {registration_date.strftime("%Y-%m-%d")}'
                })

        attendance = Attendance.query.filter_by(user_id=user_id, date=query_date).first()

        #  HOLIDAY CHECK (Sunday) - Only if NO record exists
        if query_date.weekday() == 6 and (not attendance or not attendance.mark_in_time):
            return jsonify({
                'success': True,
                'is_holiday': True,
                'date': date_str,
                'message': 'Sunday Holiday - Enjoy your weekend!'
            })

        attendance = Attendance.query.filter_by(user_id=user_id, date=query_date).first()

        if not attendance or not attendance.mark_in_time:
            return jsonify({
                'success': True,
                'is_absent': True,
                'date': date_str,
                'message': 'Absent - No complete marking found'
            })

        # 1. Determine Effective Out (Session End)
        effective_out = attendance.mark_out_time
        if not effective_out:
            if attendance.break_in_time:
                effective_out = attendance.break_in_time
            elif attendance.break_out_time:
                effective_out = attendance.break_out_time

        # 2. Calculate Break Deduction & Flagging
        deduction_mins = 0
        actual_break_mins = 0
        short_break = False
        forgot_break_in = False

        if attendance.break_out_time and attendance.break_in_time:
            # Case A: Full Break
            actual_break_mins = (attendance.break_in_time - attendance.break_out_time).total_seconds() / 60
            deduction_mins = max(60, actual_break_mins)
            if actual_break_mins < 60:
                short_break = True
        elif attendance.break_out_time and attendance.mark_out_time:
            # Case B: Forgot Break In
            deduction_mins = 60  # Deduct 60 mins as requested
            forgot_break_in = True
        # Case C & D: Left during break or No Break -> Deduction = 0

        # 3. Calculate Working Time
        if attendance.status == 'incomplete_session' or attendance.mark_out_time:
            working_hours = attendance.working_hours or 0.0
            overtime = attendance.overtime_hours or 0.0
        else:
            # Active session: calculate on the fly
            working_hours = 0
            if attendance.mark_in_time and effective_out:
                if attendance.break_out_time and attendance.break_in_time:
                    seg1 = max(0, (attendance.break_out_time - attendance.mark_in_time).total_seconds() / 60)
                    seg2 = max(0, (effective_out - attendance.break_in_time).total_seconds() / 60)
                    working_hours = (seg1 + seg2) / 60
                elif attendance.break_out_time and not attendance.break_in_time:
                    seg1 = max(0, (attendance.break_out_time - attendance.mark_in_time).total_seconds() / 60)
                    working_hours = seg1 / 60
                else:
                    total_mins = (effective_out - attendance.mark_in_time).total_seconds() / 60
                    working_hours = max(0, total_mins) / 60
            
            overtime = 0
            if query_date.weekday() == 6: # Sunday
                overtime = working_hours
                working_hours = 0
            else:
                if working_hours > 8:
                    overtime = working_hours - 8
                    working_hours = 8
                else:
                    overtime = 0

        # 4. Status and Flags
        incomplete_session = (attendance.mark_out_time is None)
        
        # Calculate time-based flags
        is_early_entry = False
        is_on_time_entry = False
        is_late_entry = False
        if attendance.mark_in_time:
            _tot = attendance.mark_in_time.hour * 3600 + attendance.mark_in_time.minute * 60 + attendance.mark_in_time.second
            if _tot < 9 * 3600:
                is_early_entry = True
            elif _tot <= 9 * 3600 + 15 * 60:
                is_on_time_entry = True
            else:
                is_late_entry = True

        early_break = False
        on_time_break = False
        late_break = False
        if attendance.break_out_time:
            _tot = attendance.break_out_time.hour * 3600 + attendance.break_out_time.minute * 60 + attendance.break_out_time.second
            if _tot < 12 * 3600:
                early_break = True
            elif _tot <= 12 * 3600 + 15 * 60:
                on_time_break = True
            else:
                late_break = True

        early_break_return = False
        on_time_break_return = False
        late_break_return = False
        long_break = False
        if attendance.break_in_time:
            _tot = attendance.break_in_time.hour * 3600 + attendance.break_in_time.minute * 60 + attendance.break_in_time.second
            
            # Check break duration
            break_duration_hours = 0.0
            if attendance.break_out_time:
                break_duration_hours = (attendance.break_in_time - attendance.break_out_time).total_seconds() / 3600.0
            
            if break_duration_hours > 1.0:
                long_break = True
            else:
                if _tot < 13 * 3600:
                    early_break_return = True
                elif _tot <= 13 * 3600 + 15 * 60:
                    on_time_break_return = True
                else:
                    late_break_return = True

        is_early_exit = False
        is_on_time_exit = False
        is_late_exit = False
        if attendance.mark_out_time:
            _tot = attendance.mark_out_time.hour * 3600 + attendance.mark_out_time.minute * 60 + attendance.mark_out_time.second
            if _tot < 18 * 3600:
                is_early_exit = True
            elif _tot <= 18 * 3600 + 15 * 60:
                is_on_time_exit = True
            else:
                is_late_exit = True

        break_incomplete = bool(attendance.break_out_time and not attendance.break_in_time)

        # Format break duration label
        break_label = format_duration(actual_break_mins / 60)

        # Determine day type flag (only for completed sessions)
        day_type = None
        if attendance.mark_out_time:
            if attendance.work_type == 'full_day':
                day_type = 'Full Day'
            elif attendance.work_type == 'half_day':
                day_type = 'Half Day'
            elif attendance.work_type == 'short_day':
                day_type = 'Short Day'
            else:
                # Fallback calculation if work_type is not populated
                if working_hours >= 8.0:
                    day_type = 'Full Day'
                elif working_hours >= 4.0:
                    day_type = 'Half Day'
                else:
                    day_type = 'Short Day'

        data = {
            'success': True,
            'mark_in': attendance.mark_in_time.strftime('%I:%M %p') if attendance.mark_in_time else '-',
            'break_out': attendance.break_out_time.strftime('%I:%M %p') if attendance.break_out_time else '-',
            'break_in': attendance.break_in_time.strftime('%I:%M %p') if attendance.break_in_time else '-',
            'mark_out': attendance.mark_out_time.strftime('%I:%M %p') if attendance.mark_out_time else '-',
            'metrics': {
                'working_time': format_duration(working_hours),
                'break_duration': break_label,
                'overtime': format_duration(overtime)
            },
            'flags': {
                'on_time': not is_late_entry,
                'late_entry': is_late_entry,
                'early_entry': is_early_entry,
                'on_time_entry': is_on_time_entry,
                'early_break': early_break,
                'on_time_break': on_time_break,
                'late_break': late_break,
                'early_break_return': early_break_return,
                'on_time_break_return': on_time_break_return,
                'late_break_return': late_break_return,
                'long_break': long_break,
                'early_exit': is_early_exit,
                'on_time_exit': is_on_time_exit,
                'late_exit': is_late_exit,
                'has_overtime': overtime > 0,
                'break_incomplete': break_incomplete,
                'incomplete_session': incomplete_session or (attendance.status == 'incomplete_session'),
                'short_break': short_break,
                'forgot_break_in': forgot_break_in,
                'admin_approval': (attendance.work_type == 'admin_approval' and attendance.approval_status == 'pending'),
                'admin_approved': (attendance.approval_status == 'approved'),
                'day_type': day_type
            }
        }

        return jsonify(data)

    # ---------------- MARK ATTENDANCE -----------------
    @app.route('/api/mark_attendance', methods=['POST'])
    def mark_attendance():
        try:
            data = request.json or {}
            image_data = data.get('image')
            action = data.get('action')
            latitude = data.get('latitude')
            longitude = data.get('longitude')
            request_id = data.get('request_id')
            
            # Idempotency Check
            if request_id:
                idemp_log = IdempotencyLog.query.get(request_id)
                if idemp_log:
                    import json
                    return jsonify(json.loads(idemp_log.response_payload))

            # Geolocation check
            if latitude is None or longitude is None:
                return jsonify({'success': False, 'message': 'Location data is required to mark attendance.'})

            try:
                lat_val = float(latitude)
                lon_val = float(longitude)
            except (ValueError, TypeError):
                return jsonify({'success': False, 'message': 'Invalid location format.'})

            # Fixed office coordinates
            OFFICE_LAT = 20.004549671968228
            OFFICE_LON = 73.75789772498837
            MAX_DISTANCE_METERS = 500.0

            # Haversine formula to compute distance in meters
            import math
            phi_1 = math.radians(lat_val)
            phi_2 = math.radians(OFFICE_LAT)
            delta_phi = math.radians(OFFICE_LAT - lat_val)
            delta_lambda = math.radians(OFFICE_LON - lon_val)

            a = math.sin(delta_phi / 2.0) ** 2 + \
                math.cos(phi_1) * math.cos(phi_2) * \
                math.sin(delta_lambda / 2.0) ** 2
            c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
            distance = 6371000.0 * c

            if distance > MAX_DISTANCE_METERS:
                return jsonify({'success': False, 'message': 'You are outside the allowed location. Attendance not allowed.'})


            if not image_data or not isinstance(image_data, str):
                return jsonify({'success': False, 'message': 'Invalid or missing image data.'})

            if ',' in image_data:
                image_data = image_data.split(',', 1)[1].strip()

            img_bytes = base64.b64decode(image_data)
            frame = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
            if frame is None:
                return jsonify({'success': False, 'message': 'Unable to decode image.'})

            face_locations = face_recognition_system.detect_faces(frame)
            if not face_locations:
                return jsonify({'success': False, 'message': 'No face detected.'})

            largest_face = max(face_locations, key=lambda box: (box[2] - box[0]) * (box[1] - box[3]))
            top, right, bottom, left = largest_face
            face_crop = frame[top:bottom, left:right]

            spoof_result = spoof_detector.detect_spoof(frame, largest_face)
            if spoof_result.get('is_spoof'):
                return jsonify({'success': False, 'message': 'Spoof detected.'})

            user_id, user_name = face_recognition_system.recognize_face(face_crop)
            if not user_id:
                return jsonify({'success': False, 'message': 'Face not recognized.'})

            emotion_result = emotion_detector.detect_emotion(frame, largest_face)
            detected_emotion = emotion_result.get('emotion', 'neutral')

            user = User.query.get(user_id)
            today = date.today()
            # Concurrency safety relies on database UniqueConstraint and Idempotency keys, not with_for_update()
            attendance = Attendance.query.filter_by(user_id=user_id, date=today).first()

            # Handle Mark In
            if action == 'in':
                if attendance and attendance.mark_in_time:
                    return jsonify({'success': False, 'message': f'Hi {user.name}, you have already Marked In today at {attendance.mark_in_time.strftime("%I:%M %p")}. Mark In is not allowed again.'})
                
                if not attendance:
                    attendance = Attendance(user_id=user_id, username=user.username, date=today, status='present')
                    db.session.add(attendance)
                
                attendance.mark_in_time = datetime.now()
                attendance.mark_in_emotion = detected_emotion
                attendance.is_spoof = spoof_result.get('is_spoof', False)
                attendance.latitude = lat_val
                attendance.longitude = lon_val
                
                # Status and Mark In arrival status based on new rules
                _mi_h = attendance.mark_in_time.hour
                _mi_m = attendance.mark_in_time.minute
                _mi_s = attendance.mark_in_time.second
                _mi_total_sec = _mi_h * 3600 + _mi_m * 60 + _mi_s

                # Early Entry: < 09:00 AM (32400 sec)
                # on time entry: 09:00 AM to 09:15 AM (inclusive, 32400 to 33300 sec)
                # Late Entry: > 09:15 AM (33300 sec)
                if _mi_total_sec < 9 * 3600:
                    arrival_status = "Early Entry"
                    attendance.status = 'present'
                elif _mi_total_sec <= 9 * 3600 + 15 * 60:
                    arrival_status = "on time entry"
                    attendance.status = 'present'
                else:
                    arrival_status = "Late Entry"
                    attendance.status = 'present'

                attendance.mark_in_status = arrival_status

                msg = f"Marked In Successful for {user.name}"
                current_time = attendance.mark_in_time.strftime('%I:%M %p')
                display_msg = f"{msg} [{arrival_status}]"

                response_data = {'success': True, 'message': msg, 'emotion': detected_emotion, 'time': current_time}
                
                # Idempotency tracking
                if request_id:
                    import json
                    idemp_entry = IdempotencyLog(request_id=request_id, response_payload=json.dumps(response_data))
                    db.session.add(idemp_entry)
                    
                db.session.commit()
                
                # Direct email notification after successful commit
                try:
                    send_mark_in_notification(user, attendance.mark_in_time)
                except Exception as e:
                    print(f"Email notification failed: {e}")
                
                return jsonify({'success': True, 'message': display_msg, 'emotion': detected_emotion, 'time': current_time})

            # Handle Break Out
            elif action == 'break_out':
                if not attendance or not attendance.mark_in_time:
                    return jsonify({'success': False, 'message': f'Hi {user.name}, Mark In has not been done yet today. Please Mark In first before going on Break.'})
                if attendance.mark_out_time:
                    return jsonify({'success': False, 'message': f'Hi {user.name}, your attendance session is already completed (Marked Out at {attendance.mark_out_time.strftime("%I:%M %p")}). No further actions allowed.'})
                if attendance.break_out_time and not attendance.break_in_time:
                    return jsonify({'success': False, 'message': f'Hi {user.name}, you are already on a break (since {attendance.break_out_time.strftime("%I:%M %p")}). Please Mark Break In first before starting a new break.'})
                if attendance.break_out_time and attendance.break_in_time:
                    return jsonify({'success': False, 'message': f'Hi {user.name}, only one break is allowed per day. Your break was already completed today.'})
                
                attendance.break_out_time = datetime.now()
                attendance.break_out_emotion = detected_emotion
                current_time = attendance.break_out_time.strftime('%I:%M %p')
                # Break Out status
                _bo_h = attendance.break_out_time.hour
                _bo_m = attendance.break_out_time.minute
                _bo_s = attendance.break_out_time.second
                _bo_total_sec = _bo_h * 3600 + _bo_m * 60 + _bo_s

                # Early Break: < 12:00 PM (43200 sec)
                # On time Break: 12:00 PM to 12:15 PM (inclusive, 43200 to 44100 sec)
                # Late Break: > 12:15 PM (44100 sec)
                if _bo_total_sec < 12 * 3600:
                    break_out_status = "Early Break"
                elif _bo_total_sec <= 12 * 3600 + 15 * 60:
                    break_out_status = "On time Break"
                else:
                    break_out_status = "Late Break"

                attendance.break_out_status = break_out_status

                msg = f'Break Out Recorded for {user.name}'
                display_msg = f"{msg} [{break_out_status}]"
                response_data = {'success': True, 'message': msg, 'emotion': detected_emotion, 'time': current_time}
                
                # Idempotency tracking
                if request_id:
                    import json
                    idemp_entry = IdempotencyLog(request_id=request_id, response_payload=json.dumps(response_data))
                    db.session.add(idemp_entry)
                    
                db.session.commit()
                
                # Direct email notification after successful commit
                try:
                    send_break_out_notification(user, attendance.break_out_time)
                except Exception as e:
                    print(f"Email notification failed: {e}")
                
                return jsonify({'success': True, 'message': display_msg, 'emotion': detected_emotion, 'time': current_time})

            # Handle Break In
            elif action == 'break_in':
                if not attendance or not attendance.mark_in_time:
                    return jsonify({'success': False, 'message': f'Hi {user.name}, Mark In has not been done yet today. Please Mark In first.'})
                if attendance.mark_out_time:
                    return jsonify({'success': False, 'message': f'Hi {user.name}, your attendance session is already completed (Marked Out at {attendance.mark_out_time.strftime("%I:%M %p")}). No further actions allowed.'})
                if not attendance.break_out_time:
                    return jsonify({'success': False, 'message': f'Hi {user.name}, you have not started a break yet. Please click Break Out first.'})
                if attendance.break_in_time:
                    return jsonify({'success': False, 'message': f'Hi {user.name}, you have already returned from your break (at {attendance.break_in_time.strftime("%I:%M %p")}). Break In is not allowed again.'})
                
                attendance.break_in_time = datetime.now()
                attendance.break_in_emotion = detected_emotion
                current_time = attendance.break_in_time.strftime('%I:%M %p')
                # Break In return status
                _bi_h = attendance.break_in_time.hour
                _bi_m = attendance.break_in_time.minute
                _bi_s = attendance.break_in_time.second
                _bi_total_sec = _bi_h * 3600 + _bi_m * 60 + _bi_s

                # Check break duration
                break_duration_hours = 0.0
                if attendance.break_out_time:
                    break_duration_hours = (attendance.break_in_time - attendance.break_out_time).total_seconds() / 3600.0

                if break_duration_hours > 1.0:
                    break_in_status = "Long Break"
                else:
                    # early Break return: < 01:00 PM (46800 sec)
                    # On time Break retuen: 01:00 PM to 01:15 PM (inclusive, 46800 to 47700 sec)
                    # late Break return: > 01:15 PM (47700 sec)
                    if _bi_total_sec < 13 * 3600:
                        break_in_status = "early Break return"
                    elif _bi_total_sec <= 13 * 3600 + 15 * 60:
                        break_in_status = "On time Break retuen"
                    else:
                        break_in_status = "late Break return"

                attendance.break_in_status = break_in_status

                msg = f'Break In Recorded for {user.name}'
                display_msg = f"{msg} [{break_in_status}]"
                response_data = {'success': True, 'message': msg, 'emotion': detected_emotion, 'time': current_time}
                
                # Idempotency tracking
                if request_id:
                    import json
                    idemp_entry = IdempotencyLog(request_id=request_id, response_payload=json.dumps(response_data))
                    db.session.add(idemp_entry)
                    
                db.session.commit()
                
                # Direct email notification after successful commit
                try:
                    send_break_in_notification(user, attendance.break_in_time)
                except Exception as e:
                    print(f"Email notification failed: {e}")
                
                return jsonify({'success': True, 'message': display_msg, 'emotion': detected_emotion, 'time': current_time})

            # Handle Mark Out
            elif action == 'out':
                if not attendance or not attendance.mark_in_time:
                    return jsonify({'success': False, 'message': f'Hi {user.name}, Mark In has not been done yet today. Please Mark In first before marking out.'})
                if attendance.mark_out_time:
                    return jsonify({'success': False, 'message': f'Hi {user.name}, you have already Marked Out today at {attendance.mark_out_time.strftime("%I:%M %p")}. Mark Out is not allowed again.'})

                attendance.mark_out_time = datetime.now()
                attendance.mark_out_emotion = detected_emotion

                # Determine if sequence is complete:
                # Complete: no break at all (break_out=None) OR full break (break_out+break_in both present)
                # Auto-complete: break_out present but break_in missing → auto-generate break_in = mark_out
                # Incomplete: any other combination that does not satisfy the above
                break_out_done = attendance.break_out_time is not None
                break_in_done = attendance.break_in_time is not None

                # Auto-generate break_in if mark_in + break_out + mark_out present but break_in missing
                if break_out_done and not break_in_done:
                    attendance.break_in_time = attendance.mark_out_time
                    attendance.break_in_auto_generated = True
                    # Leave status empty — no real user action occurred
                    attendance.break_in_status = None
                    break_in_done = True

                incomplete_break = False  # break_in is now always filled when break_out exists

                if incomplete_break:
                    # Sequence broken: Break Out happened but Break In was never done
                    attendance.status = 'incomplete_session'
                    attendance.work_type = 'admin_approval'
                    attendance.approval_status = 'pending'
                    # Estimate hours up to break_out only (worked before break)
                    diff_secs = (attendance.break_out_time - attendance.mark_in_time).total_seconds()
                    wh = max(0.0, diff_secs / 3600.0)
                    if today.weekday() == 6:  # Sunday
                        attendance.working_hours = 0.0
                        attendance.overtime_hours = wh
                    else:
                        if wh > 8.0:
                            attendance.working_hours = 8.0
                            attendance.overtime_hours = wh - 8.0
                        else:
                            attendance.working_hours = wh
                            attendance.overtime_hours = 0.0
                else:
                    # Complete sequence — classify immediately
                    total_mins = (attendance.mark_out_time - attendance.mark_in_time).total_seconds() / 60.0
                    deduction_mins = 0.0
                    if attendance.break_out_time and attendance.break_in_time:
                        deduction_mins = (attendance.break_in_time - attendance.break_out_time).total_seconds() / 60.0

                    net_working_mins = max(0, total_mins - deduction_mins)
                    net_working_hours = net_working_mins / 60.0

                    # Overtime
                    if today.weekday() == 6:  # Sunday: all hours = overtime
                        attendance.working_hours = 0.0
                        attendance.overtime_hours = net_working_hours
                    else:
                        if net_working_hours > 8.0:
                            attendance.working_hours = 8.0
                            attendance.overtime_hours = net_working_hours - 8.0
                        else:
                            attendance.working_hours = net_working_hours
                            attendance.overtime_hours = 0.0

                    # Work Type Classification (subcategory of 'present')
                    attendance.status = 'present'
                    if net_working_hours >= 8.0:
                        attendance.work_type = 'full_day'
                    elif net_working_hours >= 4.0:
                        attendance.work_type = 'half_day'
                    else:
                        attendance.work_type = 'short_day'

                current_time = attendance.mark_out_time.strftime('%I:%M %p')
                status_label = (attendance.work_type or 'Present').replace("_", " ").title()

                # Mark Out departure status
                _mo_h = attendance.mark_out_time.hour
                _mo_m = attendance.mark_out_time.minute
                _mo_s = attendance.mark_out_time.second
                _mo_total_sec = _mo_h * 3600 + _mo_m * 60 + _mo_s

                # Early Departure: < 06:00 PM (64800 sec)
                # on time Departure: 06:00 PM to 06:15 PM (inclusive, 64800 to 65700 sec)
                # Late Departure: > 06:15 PM (65700 sec)
                if _mo_total_sec < 18 * 3600:
                    departure_status = "Early Departure"
                elif _mo_total_sec <= 18 * 3600 + 15 * 60:
                    departure_status = "on time Departure"
                else:
                    departure_status = "Late Departure"

                attendance.mark_out_status = departure_status

                msg = f'Marked Out Successful for {user.name} ({status_label})'
                display_msg = f"{msg} [{departure_status}]"
                response_data = {'success': True, 'message': msg, 'emotion': detected_emotion, 'time': current_time}
                
                # Idempotency tracking
                if request_id:
                    import json
                    idemp_entry = IdempotencyLog(request_id=request_id, response_payload=json.dumps(response_data))
                    db.session.add(idemp_entry)
                    
                db.session.commit()
                
                # Direct email notification after successful commit
                try:
                    send_mark_out_notification(user, attendance.mark_out_time)
                except Exception as e:
                    print(f"Email notification failed: {e}")
                
                return jsonify({'success': True, 'message': display_msg, 'emotion': detected_emotion, 'time': current_time})

            else:
                return jsonify({'success': False, 'message': 'Invalid action specified.'})

        except Exception as e:
            # Explicit rollback on any uncaught failure to ensure data integrity
            db.session.rollback()
            print(f"Error in mark_attendance: {e}")
            return jsonify({'success': False, 'message': str(e)})

    # ---------------- REGISTER EMPLOYEE -----------------
    @app.route('/admin/register_employee', methods=['GET', 'POST'])
    @login_required
    def register_employee():
        if not current_user.is_admin:
            return redirect(url_for('employee_dashboard'))

        if request.method == 'POST':
            try:
                name = request.form.get('name')
                username = request.form.get('username')
                password = request.form.get('password')
                email = request.form.get('email')
                mobile = request.form.get('mobile')
                department = request.form.get('department')

                if mobile:
                    mobile = mobile.strip()
                    if not mobile.isdigit() or len(mobile) != 10:
                        flash('plz enter valid number (must be exactly 10 digits)', 'error')
                        return redirect(url_for('register_employee'))

                import re
                email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                if not email or not re.match(email_regex, email):
                    flash('Please enter a valid email address', 'error')
                    return redirect(url_for('register_employee'))

                if User.query.filter_by(username=username).first():
                    flash('Username already exists', 'error')
                    return redirect(url_for('register_employee'))
                if User.query.filter_by(email=email).first():
                    flash('Email already exists', 'error')
                    return redirect(url_for('register_employee'))

                user = User(name=name, username=username, email=email,
                            mobile=mobile, department=department, is_admin=False)
                user.set_password(password)
                db.session.add(user)
                db.session.flush()

                uploaded_files = request.files.getlist('face_images')
                captured_images_raw = request.form.get('captured_images')
                saved_images = []

                # Handle Profile Picture (first uploaded file)
                if uploaded_files and uploaded_files[0] and allowed_file(uploaded_files[0].filename):
                    profile_file = uploaded_files[0]
                    filename = secure_filename(f"profile_{user.id}_{profile_file.filename}")
                    path = os.path.join('uploads', filename)
                    profile_file.save(path)
                    user.profile_pic = path
                    saved_images.append(path)
                    
                    # If there are more files, save them too
                    for file in uploaded_files[1:]:
                        if file and allowed_file(file.filename):
                            filename = secure_filename(f"{user.id}_{file.filename}")
                            path = os.path.join('uploads', filename)
                            file.save(path)
                            saved_images.append(path)

                if captured_images_raw:
                    try:
                        captured_images = json.loads(captured_images_raw)
                        for img in captured_images:
                            if img and ',' in img:
                                img = img.split(',', 1)[1]
                            img_bytes = base64.b64decode(img)
                            filename = secure_filename(f"{user.id}_capture_{uuid4().hex}.jpg")
                            path = os.path.join('uploads', filename)
                            with open(path, 'wb') as f:
                                f.write(img_bytes)
                            saved_images.append(path)
                    except Exception as err:
                        print(f"Captured image error: {err}")

                if saved_images:
                    face_recognition_system.train_user_face(user.id, saved_images)
                    flash(f'Employee registered successfully with {len(saved_images)} face images', 'success')
                else:
                    flash('Employee registered but no face images added.', 'warning')

                db.session.commit()
                return redirect(url_for('admin_dashboard'))

            except Exception as e:
                db.session.rollback()
                flash(f'Error: {e}', 'error')

        return render_template('register_employee.html')

    # ---------------- Dashboard helper -----------------
    @app.route('/api/ai_chat', methods=['POST'])
    @login_required
    def ai_chat_route():
        try:
            data = request.get_json(silent=True)
            if not data:
                data = request.form.to_dict()
            if not data and request.data:
                try:
                    data = json.loads(request.data.decode('utf-8'))
                except Exception:
                    data = {}

            prompt = data.get('message') or data.get('msg') or data.get('text')
            if not prompt:
                return jsonify({"success": False, "message": "Prompt missing"}), 400

            role = 'admin' if getattr(current_user, 'is_admin', False) else 'employee'
            result = get_ai_response(prompt, user=current_user, role=role)
            return jsonify(result)

        except Exception as e:
            print(f"AI Chat Error: {e}")
            return jsonify({"success": False, "message": "Server error"}), 500

    # ---------------- HELPER FUNCTIONS -----------------
    def allowed_file(filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in ['png', 'jpg', 'jpeg']

    def speak_text(text):
        def run_tts(msg):
            try:
                import pyttsx3
                # Initialize inside the thread to avoid COM errors
                engine = pyttsx3.init()
                engine.setProperty('rate', 150)
                engine.say(msg)
                engine.runAndWait()
                # Clean up engine
                del engine
            except Exception as e:
                print(f"TTS Thread Error: {e}")

        import threading
        thread = threading.Thread(target=run_tts, args=(text,))
        thread.start()

    # ---------------- DELETE EMPLOYEE -----------------
    @app.route('/api/employees/<int:user_id>', methods=['DELETE'])
    @login_required
    def delete_employee(user_id):
        if not current_user.is_admin:
            return jsonify({'success': False, 'message': 'Unauthorized access.'}), 403

        try:
            user = User.query.get(user_id)
            if not user:
                return jsonify({'success': False, 'message': 'Employee not found.'}), 404

            from models import FaceEncoding
            # Collect all attendance IDs for this user (needed for future audit if required)
            Attendance.query.filter_by(user_id=user_id).delete()

            FaceEncoding.query.filter_by(user_id=user_id).delete()

            face_data_folder = os.path.join('face_data', str(user_id))
            if os.path.exists(face_data_folder):
                for f in os.listdir(face_data_folder):
                    try:
                        os.remove(os.path.join(face_data_folder, f))
                    except Exception as e:
                        print(f"File delete error: {e}")
                try:
                    os.rmdir(face_data_folder)
                except Exception as e:
                    print(f"Folder delete error: {e}")

            db.session.delete(user)
            db.session.commit()

            return jsonify({'success': True, 'message': f'Employee {user.name} deleted successfully.'})

        except Exception as e:
            db.session.rollback()
            print(f"Error deleting employee: {e}")
            return jsonify({'success': False, 'message': 'Server error occurred.'}), 500

    # ---------------- UPDATE EMPLOYEE -----------------
    @app.route('/api/admin/update_employee/<int:user_id>', methods=['POST'])
    @login_required
    def update_employee_api(user_id):
        if not current_user.is_admin:
            return jsonify({"success": False, "message": "Unauthorized"}), 403

        user = User.query.get_or_404(user_id)
        
        name = request.form.get('name')
        username = request.form.get('username')
        email = request.form.get('email')
        mobile = request.form.get('mobile')
        department = request.form.get('department')
        
        if not name or not username or not email or not department:
            return jsonify({"success": False, "message": "Missing required fields"}), 400

        if mobile:
            mobile = mobile.strip()
            if not mobile.isdigit() or len(mobile) != 10:
                return jsonify({"success": False, "message": "plz enter valid number (must be exactly 10 digits)"}), 400

        # Check unique username/email
        existing_username = User.query.filter(User.username == username, User.id != user_id).first()
        if existing_username:
            return jsonify({"success": False, "message": "Username already exists"}), 400

        existing_email = User.query.filter(User.email == email, User.id != user_id).first()
        if existing_email:
            return jsonify({"success": False, "message": "Email already exists"}), 400

        # Update details
        user.name = name
        user.username = username
        user.email = email
        user.mobile = mobile
        user.department = department

        # Handle profile photo upload
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file and file.filename != '':
                # Save file
                filename = secure_filename(f"user_{user.id}_profile_{uuid4().hex[:8]}_{file.filename}")
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                user.profile_pic = file_path

        try:
            db.session.commit()
            return jsonify({"success": True, "message": "Employee profile updated successfully"})
        except Exception as e:
            db.session.rollback()
            print(f"Error updating employee: {e}")
            return jsonify({"success": False, "message": "Failed to update profile. Server error."}), 500
