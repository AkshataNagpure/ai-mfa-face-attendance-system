from deepface import DeepFace
import cv2
import numpy as np

class EmotionDetection:
    def __init__(self):
        # Common emotion labels used by DeepFace
        self.emotions = ['angry', 'disgust', 'fear', 'happy', 'sad', 'surprise', 'neutral']

    def detect_emotion(self, frame, face_location=None):
        """
        Detect emotion from a given frame (BGR image).
        Args:
            frame: numpy array (OpenCV BGR image)
            face_location: tuple (top, right, bottom, left) or None
        Returns:
            dict with emotion and confidence
        """
        try:
            if frame is None or not isinstance(frame, np.ndarray):
                raise ValueError("Invalid frame for emotion detection")

            # Crop face if location provided
            if face_location:
                top, right, bottom, left = face_location
                face_img = frame[top:bottom, left:right]
                if face_img.size == 0:
                    raise ValueError("Empty cropped face")
            else:
                face_img = frame

            # Convert to RGB for DeepFace
            rgb_img = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)

            # Perform emotion analysis
            result = DeepFace.analyze(
                rgb_img,
                actions=['emotion'],
                enforce_detection=False,
                silent=True
            )

            # Extract emotion result
            if isinstance(result, list):
                result = result[0]

            emotion = result.get('dominant_emotion', 'neutral')
            emotion_scores = result.get('emotion', {})

            # Normalize emotion key casing
            emotion = emotion.lower()
            if emotion not in self.emotions:
                emotion = 'neutral'

            return {
                'emotion': emotion,
                'confidence': emotion_scores.get(emotion, 0),
                'all_emotions': emotion_scores
            }

        except Exception as e:
            print(f"[EmotionDetection] Error detecting emotion: {e}")
            return {
                'emotion': 'neutral',
                'confidence': 0,
                'all_emotions': {}
            }

    def get_emotion_trend(self, user_id, days=7):
        """
        Build aggregated emotion data for a user across the requested window.
        Reads from all 4 per-event emotion columns: mark_in, break_out, break_in, mark_out.
        Returns counts per emotion and a day-by-day breakdown for charts.
        """
        from models import Attendance
        from datetime import datetime, timedelta

        try:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days - 1)

            attendances = Attendance.query.filter(
                Attendance.user_id == user_id,
                Attendance.date >= start_date,
                Attendance.date <= end_date,
            ).order_by(Attendance.date).all()

            # Initialize counters
            emotion_counts = {emotion: 0 for emotion in self.emotions}
            daily_counts = {}
            for i in range(days):
                day = start_date + timedelta(days=i)
                day_key = day.strftime('%Y-%m-%d')
                daily_counts[day_key] = {emotion: 0 for emotion in self.emotions}

            # All 4 per-event emotion columns
            event_fields = ['mark_in_emotion', 'break_out_emotion', 'break_in_emotion', 'mark_out_emotion']

            for attendance in attendances:
                day_key = attendance.date.strftime('%Y-%m-%d')

                for field in event_fields:
                    raw_emotion = getattr(attendance, field, None)
                    if not raw_emotion:
                        continue
                    # Handle comma-separated values defensively
                    emotions = [e.strip().lower() for e in raw_emotion.split(',')]
                    for emotion in emotions:
                        if not emotion:
                            continue
                        if emotion not in emotion_counts:
                            emotion_counts[emotion] = 0
                            for counts in daily_counts.values():
                                counts.setdefault(emotion, 0)

                        emotion_counts[emotion] += 1
                        if day_key not in daily_counts:
                            daily_counts[day_key] = {e: 0 for e in emotion_counts}
                        daily_counts[day_key][emotion] = daily_counts[day_key].get(emotion, 0) + 1

            has_data = any(count > 0 for count in emotion_counts.values())
            timeline = [
                {'date': date_key, 'emotions': day_counts}
                for date_key, day_counts in sorted(daily_counts.items())
            ]

            return {
                'counts': emotion_counts,
                'timeline': timeline,
                'has_data': has_data
            }

        except Exception as e:
            print(f"[EmotionDetection] Error building emotion trend: {e}")
            return {
                'counts': {emotion: 0 for emotion in self.emotions},
                'timeline': [],
                'has_data': False
            }
