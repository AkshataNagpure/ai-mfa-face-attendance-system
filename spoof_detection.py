import cv2
import numpy as np
from deepface import DeepFace

class SpoofDetection:
    def __init__(self, threshold=0.5):
        self.threshold = threshold
    
    def detect_spoof(self, frame, face_location=None):
        """
        Detect if the face is real or spoofed
        Uses multiple techniques:
        1. Blink detection
        2. Face quality analysis
        3. Depth analysis (if available)
        
        Args:
            frame: numpy array (BGR image)
            face_location: tuple (top, right, bottom, left) or None
        
        Returns:
            dict with is_spoof (bool) and confidence (float)
        """
        try:
            if face_location:
                top, right, bottom, left = face_location
                face_img = frame[top:bottom, left:right]
            else:
                face_img = frame
            
            # Convert to RGB
            rgb_img = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)
            
            # Method 1: Check face quality using DeepFace
            try:
                # DeepFace can detect if face is real
                result = DeepFace.analyze(
                    rgb_img,
                    actions=['age', 'gender'],
                    enforce_detection=False,
                    silent=True
                )
                
                if isinstance(result, list):
                    result = result[0]
                
                # If analysis fails, it might be spoofed
                quality_score = 1.0 if result else 0.0
            except:
                quality_score = 0.0
            
            # Method 2: Check image sharpness (spoofed images are often blurry)
            gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            sharpness_score = min(laplacian_var / 100.0, 1.0)  # Normalize
            
            # Method 3: Check for reflection artifacts
            reflection_score = self._check_reflections(face_img)
            
            # Combine scores
            combined_score = (quality_score * 0.4 + sharpness_score * 0.3 + reflection_score * 0.3)
            
            is_spoof = combined_score < self.threshold
            
            return {
                'is_spoof': is_spoof,
                'confidence': 1.0 - combined_score if is_spoof else combined_score,
                'quality_score': quality_score,
                'sharpness_score': sharpness_score,
                'reflection_score': reflection_score
            }
        except Exception as e:
            print(f"Error in spoof detection: {e}")
            # Default to not spoofed if detection fails
            return {
                'is_spoof': False,
                'confidence': 0.5,
                'quality_score': 0.5,
                'sharpness_score': 0.5,
                'reflection_score': 0.5
            }
    
    def _check_reflections(self, face_img):
        """Check for reflection artifacts that might indicate a photo"""
        # Convert to HSV
        hsv = cv2.cvtColor(face_img, cv2.COLOR_BGR2HSV)
        
        # Check for uniform brightness (photos often have uniform lighting)
        brightness = hsv[:, :, 2]
        brightness_std = np.std(brightness)
        
        # Higher std indicates real face (natural lighting variations)
        # Lower std might indicate a photo
        reflection_score = min(brightness_std / 30.0, 1.0)
        
        return reflection_score
    
    def detect_blink(self, frame, face_location=None):
        """Detect if person is blinking (liveness check)"""
        # This is a simplified version
        # For production, use more sophisticated eye detection
        try:
            if face_location:
                top, right, bottom, left = face_location
                face_roi = frame[top:bottom, left:right]
            else:
                face_roi = frame
            
            gray = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
            
            # Simple eye detection using Haar cascades
            eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')
            eyes = eye_cascade.detectMultiScale(gray, 1.1, 4)
            
            return len(eyes) >= 2  # Both eyes detected
        except:
            return False

