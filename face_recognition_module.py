
import face_recognition
import cv2
import numpy as np
import os
import pickle
from models import db, User, FaceEncoding

class FaceRecognitionSystem:
    def __init__(self, tolerance=0.45):  # stricter = fewer wrong matches
        self.tolerance = tolerance
        self.face_encodings_folder = 'face_encodings'
        os.makedirs(self.face_encodings_folder, exist_ok=True)

    # ---------- HELPER FUNCTIONS ----------

    def load_face_encodings(self, user_id):
        """Load saved encodings for a user"""
        encodings = []
        for record in FaceEncoding.query.filter_by(user_id=user_id).all():
            if os.path.exists(record.encoding_path):
                with open(record.encoding_path, 'rb') as f:
                    encodings.extend(pickle.load(f))
        return encodings

    def encode_face_from_image(self, image_path):
        """Encode a face from a static image (only if one clear face is found)"""
        try:
            image = face_recognition.load_image_file(image_path)
            face_locations = face_recognition.face_locations(image)

            # Skip unclear images
            if len(face_locations) != 1:
                print(f" Skipping {image_path}: found {len(face_locations)} faces.")
                return []

            encoding = face_recognition.face_encodings(image, known_face_locations=face_locations)[0]
            return [encoding]
        except Exception as e:
            print(f"Error encoding face: {e}")
            return []

    def encode_face_from_frame(self, frame):
        """Encode face from a webcam frame (uses the largest detected face)"""
        try:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            face_locations = face_recognition.face_locations(rgb_frame)

            if not face_locations:
                return []

            # Pick the largest face (best for front camera)
            largest_face = max(face_locations, key=lambda box: (box[2] - box[0]) * (box[1] - box[3]))
            encoding = face_recognition.face_encodings(rgb_frame, [largest_face])[0]
            return [encoding]
        except Exception as e:
            print(f"Error encoding face from frame: {e}")
            return []

    def save_face_encoding(self, user_id, encoding, image_path):
        """Save a single face encoding"""
        os.makedirs(self.face_encodings_folder, exist_ok=True)
        count = FaceEncoding.query.filter_by(user_id=user_id).count()
        encoding_file = os.path.join(self.face_encodings_folder, f"user_{user_id}_{count}.pkl")

        with open(encoding_file, 'wb') as f:
            pickle.dump([encoding], f)

        record = FaceEncoding(user_id=user_id, encoding_path=encoding_file, image_path=image_path)
        db.session.add(record)
        db.session.commit()

    # ---------- CORE FUNCTIONS ----------

    def train_user_face(self, user_id, image_paths):
        """Train (register) a user with multiple good images"""
        successful_encodings = 0
        for image_path in image_paths:
            encodings = self.encode_face_from_image(image_path)
            if encodings:
                self.save_face_encoding(user_id, encodings[0], image_path)
                successful_encodings += 1
        print(f" Trained {successful_encodings} valid encodings for user {user_id}")
        return successful_encodings

    def detect_faces(self, frame):
        """Detect faces for debugging"""
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return face_recognition.face_locations(rgb_frame)

    def recognize_face(self, frame):
        """Recognize the face in frame -> return (user_id, user_name/message)"""
        users_with_faces = db.session.query(User).join(FaceEncoding).distinct().all()
        if not users_with_faces:
            return None, "No registered faces"

        frame_encodings = self.encode_face_from_frame(frame)
        if not frame_encodings:
            return None, "No face detected"

        face_encoding = frame_encodings[0]
        best_match_user = None
        lowest_distance = 1.0

        # Compare with all users
        for user in users_with_faces:
            known_encodings = self.load_face_encodings(user.id)
            if not known_encodings:
                continue

            distances = face_recognition.face_distance(known_encodings, face_encoding)
            min_distance = np.min(distances)

            if min_distance < self.tolerance and min_distance < lowest_distance:
                lowest_distance = min_distance
                best_match_user = user

        if best_match_user:
            return best_match_user.id, best_match_user.name

        return None, "Face not recognized"
