"""
Image processing utilities for MAIA.
"""
import cv2
import numpy as np
from typing import Optional, Tuple, List
import asyncio
import logging

_LOGGER = logging.getLogger(__name__)

class ImagePreprocessor:
    """Image preprocessing utilities."""
    
    def __init__(self):
        """Initialize image preprocessor."""
        self.target_size = (640, 480)  # Default target size
        self.min_face_size = (30, 30)  # Minimum face size
        self.equalize_hist = True      # Whether to equalize histogram
        self.denoise = True            # Whether to apply denoising
        
    async def preprocess(self, image: np.ndarray) -> np.ndarray:
        """Preprocess image for face detection."""
        try:
            # Ensure RGB format
            if len(image.shape) == 2:
                image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
            elif image.shape[2] == 4:
                image = cv2.cvtColor(image, cv2.COLOR_RGBA2RGB)
                
            # Resize image if needed
            if image.shape[:2] != self.target_size:
                image = cv2.resize(
                    image,
                    self.target_size,
                    interpolation=cv2.INTER_AREA
                )
                
            # Convert to grayscale for preprocessing
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
            
            # Apply histogram equalization if enabled
            if self.equalize_hist:
                gray = cv2.equalizeHist(gray)
                
            # Apply denoising if enabled
            if self.denoise:
                gray = cv2.fastNlMeansDenoising(gray)
                
            # Convert back to RGB
            processed = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)
            
            return processed
            
        except Exception as e:
            _LOGGER.error(f"Image preprocessing failed: {str(e)}")
            return image
            
    def detect_faces(
        self,
        image: np.ndarray,
        cascade_file: str = "haarcascade_frontalface_default.xml"
    ) -> List[Tuple[int, int, int, int]]:
        """Detect faces in image using Haar cascade."""
        try:
            # Load cascade classifier
            face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + cascade_file
            )
            
            # Convert to grayscale
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
            
            # Detect faces
            faces = face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=self.min_face_size
            )
            
            return [(x, y, x + w, y + h) for (x, y, w, h) in faces]
            
        except Exception as e:
            _LOGGER.error(f"Face detection failed: {str(e)}")
            return []
            
    def extract_face(
        self,
        image: np.ndarray,
        bbox: Tuple[int, int, int, int],
        padding: float = 0.2
    ) -> Optional[np.ndarray]:
        """Extract face region from image with padding."""
        try:
            # Get bbox coordinates
            x1, y1, x2, y2 = bbox
            
            # Calculate padding
            w = x2 - x1
            h = y2 - y1
            pad_x = int(w * padding)
            pad_y = int(h * padding)
            
            # Apply padding with bounds checking
            x1 = max(0, x1 - pad_x)
            y1 = max(0, y1 - pad_y)
            x2 = min(image.shape[1], x2 + pad_x)
            y2 = min(image.shape[0], y2 + pad_y)
            
            # Extract face region
            face = image[y1:y2, x1:x2]
            
            return face
            
        except Exception as e:
            _LOGGER.error(f"Face extraction failed: {str(e)}")
            return None
            
    def align_face(
        self,
        image: np.ndarray,
        landmarks: dict
    ) -> Optional[np.ndarray]:
        """Align face based on facial landmarks."""
        try:
            if not landmarks or "left_eye" not in landmarks or "right_eye" not in landmarks:
                return image
                
            # Get eye centers
            left_eye = np.mean(landmarks["left_eye"], axis=0)
            right_eye = np.mean(landmarks["right_eye"], axis=0)
            
            # Calculate angle to align eyes horizontally
            dy = right_eye[1] - left_eye[1]
            dx = right_eye[0] - left_eye[0]
            angle = np.degrees(np.arctan2(dy, dx))
            
            # Get center of rotation
            center = tuple(np.array(image.shape[1::-1]) / 2)
            
            # Get rotation matrix
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            
            # Apply rotation
            aligned = cv2.warpAffine(
                image,
                M,
                image.shape[1::-1],
                flags=cv2.INTER_CUBIC
            )
            
            return aligned
            
        except Exception as e:
            _LOGGER.error(f"Face alignment failed: {str(e)}")
            return image
            
    def enhance_face(
        self,
        face: np.ndarray,
        target_size: Optional[Tuple[int, int]] = None
    ) -> np.ndarray:
        """Enhance face image quality."""
        try:
            # Resize if target size specified
            if target_size:
                face = cv2.resize(
                    face,
                    target_size,
                    interpolation=cv2.INTER_LANCZOS4
                )
                
            # Convert to LAB color space
            lab = cv2.cvtColor(face, cv2.COLOR_RGB2LAB)
            
            # Split channels
            l, a, b = cv2.split(lab)
            
            # Apply CLAHE to L channel
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            cl = clahe.apply(l)
            
            # Merge channels
            enhanced_lab = cv2.merge([cl, a, b])
            
            # Convert back to RGB
            enhanced = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2RGB)
            
            return enhanced
            
        except Exception as e:
            _LOGGER.error(f"Face enhancement failed: {str(e)}")
            return face 