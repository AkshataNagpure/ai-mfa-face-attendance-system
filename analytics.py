from models import db, Attendance, User
from datetime import datetime, timedelta
from collections import defaultdict
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder

class PredictiveAnalytics:
    def __init__(self):
        self.model = None
        self.le = LabelEncoder()
    
    def predict_absent_employees(self, days_ahead=7):
        """Predict which employees might be absent in the next N days"""
        try:
            # Get historical attendance data
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=30)  # Last 30 days
            
            # Get all employees
            employees = User.query.filter_by(is_admin=False, is_active=True).all()
            predictions = []
            
            for employee in employees:
                # Get attendance history
                attendances = Attendance.query.filter(
                    Attendance.user_id == employee.id,
                    Attendance.date >= start_date,
                    Attendance.date <= end_date
                ).all()
                
                if not attendances:
                    # NEW LOGIC: Employees with no records in past 30 days get 100% risk
                    predictions.append({
                        'employee_id': employee.id,
                        'employee_name': employee.name,
                        'department': employee.department,
                        'attendance_rate': 0.0,
                        'risk_score': 1.0,
                        'predicted_absent': True
                    })
                    continue
                
                # Calculate features
                attendance_rate = self._calculate_attendance_rate(attendances)
                recent_absent_days = self._count_recent_absences(attendances, days=14)
                consecutive_absent_days = self._max_consecutive_absences(attendances)
                weekday_pattern = self._analyze_weekday_pattern(attendances)
                
                # Simple scoring algorithm
                risk_score = self._calculate_risk_score(
                    attendance_rate,
                    recent_absent_days,
                    consecutive_absent_days,
                    weekday_pattern
                )
                
                predictions.append({
                    'employee_id': employee.id,
                    'employee_name': employee.name,
                    'department': employee.department,
                    'attendance_rate': attendance_rate,
                    'risk_score': risk_score,
                    'predicted_absent': risk_score > 0.6
                })
            
            # Sort by risk score (descending)
            predictions.sort(key=lambda x: x['risk_score'], reverse=True)
            
            return predictions  # Return all employees
        except Exception as e:
            print(f"Error in predictive analytics: {e}")
            return []
    
    def _calculate_attendance_rate(self, attendances):
        """Calculate attendance rate"""
        if not attendances:
            return 0.0
        
        present_count = sum(1 for a in attendances if a.status == 'present')
        return present_count / len(attendances) if attendances else 0.0
    
    def _count_recent_absences(self, attendances, days=14):
        """Count absences in recent days"""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        
        recent_absences = sum(
            1 for a in attendances
            if a.date >= start_date and a.status == 'absent'
        )
        return recent_absences
    
    def _max_consecutive_absences(self, attendances):
        """Find maximum consecutive absences"""
        sorted_attendances = sorted(attendances, key=lambda x: x.date)
        max_consecutive = 0
        current_consecutive = 0
        
        for att in sorted_attendances:
            if att.status == 'absent':
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0
        
        return max_consecutive
    
    def _analyze_weekday_pattern(self, attendances):
        """Analyze weekday attendance patterns"""
        weekday_absences = defaultdict(int)
        
        for att in attendances:
            if att.status == 'absent':
                weekday = att.date.weekday()
                weekday_absences[weekday] += 1
        
        # Return the day with most absences
        if weekday_absences:
            return max(weekday_absences.items(), key=lambda x: x[1])[0]
        return None
    
    def _calculate_risk_score(self, attendance_rate, recent_absences, consecutive_absences, weekday_pattern):
        """Calculate risk score for potential absence"""
        score = 0.0
        
        # Lower attendance rate = higher risk
        score += (1.0 - attendance_rate) * 0.4
        
        # Recent absences = higher risk
        score += min(recent_absences / 10.0, 1.0) * 0.3
        
        # Consecutive absences = higher risk
        score += min(consecutive_absences / 5.0, 1.0) * 0.3
        
        return min(score, 1.0)

class EmployeeInsights:
    def get_punctuality_analytics(self):
        """Get punctuality analytics for all employees"""
        employees = User.query.filter_by(is_admin=False, is_active=True).all()
        analytics = []
        
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=30)
        
        for employee in employees:
            attendances = Attendance.query.filter(
                Attendance.user_id == employee.id,
                Attendance.date >= start_date,
                Attendance.date <= end_date
            ).all()
            
            if not attendances:
                # NEW LOGIC: Include all employees even with no records
                analytics.append({
                    'employee_id': employee.id,
                    'employee_name': employee.name,
                    'department': employee.department,
                    'punctuality_rate': 0.0,
                    'avg_mark_in_time': 'N/A',
                    'total_days': 0
                })
                continue
            
            # Calculate average mark-in time
            mark_in_times = [a.mark_in_time for a in attendances if a.mark_in_time]
            
            if mark_in_times:
                avg_mark_in = self._calculate_average_time(mark_in_times)
                on_time_count = sum(1 for t in mark_in_times if t.hour < 10)
                punctuality_rate = on_time_count / len(mark_in_times) if mark_in_times else 0
            else:
                avg_mark_in = None
                punctuality_rate = 0
            
            analytics.append({
                'employee_id': employee.id,
                'employee_name': employee.name,
                'department': employee.department,
                'punctuality_rate': punctuality_rate,
                'avg_mark_in_time': avg_mark_in.strftime('%H:%M') if avg_mark_in else 'N/A',
                'total_days': len(attendances)
            })
        
        return sorted(analytics, key=lambda x: x['punctuality_rate'], reverse=True)
    
    def get_emotion_trends(self, days=7):
        """Get emotion trends across all employees for the last N days (default 7).
        Aggregates emotions from all 4 attendance events: mark-in, break-out, break-in, mark-out."""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days - 1)
        
        attendances = Attendance.query.filter(
            Attendance.date >= start_date,
            Attendance.date <= end_date
        ).all()
        
        emotion_counts = defaultdict(int)
        department_emotions = defaultdict(lambda: defaultdict(int))

        # All 4 per-event emotion columns
        event_fields = ['mark_in_emotion', 'break_out_emotion', 'break_in_emotion', 'mark_out_emotion']

        for att in attendances:
            for field in event_fields:
                raw_emotion = getattr(att, field, None)
                if not raw_emotion:
                    continue
                # Handle comma-separated emotions defensively
                emotions = [e.strip().lower() for e in raw_emotion.split(',')]
                for emotion in emotions:
                    if not emotion:
                        continue
                    emotion_counts[emotion] += 1
                    if att.user and att.user.department:
                        department_emotions[att.user.department][emotion] += 1
        
        return {
            'overall_emotions': dict(emotion_counts),
            'department_emotions': {dept: dict(emotions) for dept, emotions in department_emotions.items()}
        }
    
    def _calculate_average_time(self, times):
        """Calculate average time from datetime objects"""
        total_seconds = sum(
            (t.hour * 3600 + t.minute * 60 + t.second)
            for t in times
        )
        avg_seconds = total_seconds // len(times)
        
        hours = avg_seconds // 3600
        minutes = (avg_seconds % 3600) // 60
        
        result = datetime.now().replace(hour=hours, minute=minutes, second=0, microsecond=0)
        return result

