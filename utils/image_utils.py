"""
Image processing utilities for MAIA.
Handles image preprocessing, enhancement, and feature extraction.
"""
import cv2
import numpy as np
from typing import Optional, Tuple, Dict, List
import logging
from datetime import datetime

_LOGGER = logging.getLogger(__name__)

class ImagePreprocessor:
    def __init__(self):
        # Image processing parameters
        self.target_size = (224, 224)
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        
        # Enhancement parameters
        self.contrast_limit = 3.0
        self.tile_grid_size = (8, 8)
        
        # Face detection parameters
        self.min_face_size = (30, 30)
        self.scale_factor = 1.1
        self.min_neighbors = 5

    def preprocess(self, image: np.ndarray) -> np.ndarray:
        """
        Preprocess image for face recognition.
        
        Args:
            image: Input image as numpy array
            
        Returns:
            Preprocessed image
        """
        try:
            # Convert to RGB if needed
            if len(image.shape) == 2:
                image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
            elif image.shape[2] == 4:
                image = cv2.cvtColor(image, cv2.COLOR_RGBA2RGB)
                
            # Resize
            image = self._resize_image(image)
            
            # Enhance
            enhanced = self._enhance_image(image)
            
            # Normalize
            normalized = self._normalize_image(enhanced)
            
            return normalized
            
        except Exception as e:
            _LOGGER.error(f"Error preprocessing image: {str(e)}")
            return image

    def detect_faces(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detect faces in image with additional metadata.
        
        Args:
            image: Input image
            
        Returns:
            List of detected faces with metadata
        """
        try:
            # Convert to grayscale for detection
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
            
            # Detect faces
            faces = self.face_cascade.detectMultiScale(
                gray,
                scaleFactor=self.scale_factor,
                minNeighbors=self.min_neighbors,
                minSize=self.min_face_size
            )
            
            # Process each face
            face_data = []
            for (x, y, w, h) in faces:
                face = {
                    'bbox': (x, y, w, h),
                    'confidence': self._calculate_detection_confidence(gray[y:y+h, x:x+w]),
                    'timestamp': datetime.now().isoformat(),
                    'size': (w, h),
                    'center': (x + w//2, y + h//2)
                }
                face_data.append(face)
                
            return face_data
            
        except Exception as e:
            _LOGGER.error(f"Error detecting faces: {str(e)}")
            return []

    def extract_face_features(self, face_image: np.ndarray) -> Dict[str, np.ndarray]:
        """
        Extract features from a face image.
        
        Args:
            face_image: Cropped face image
            
        Returns:
            Dictionary of extracted features
        """
        try:
            # Ensure correct size
            face_image = cv2.resize(face_image, self.target_size)
            
            # Extract features
            features = {
                'histogram': self._calculate_histogram(face_image),
                'gradients': self._calculate_gradients(face_image),
                'landmarks': self._detect_landmarks(face_image)
            }
            
            return features
            
        except Exception as e:
            _LOGGER.error(f"Error extracting face features: {str(e)}")
            return {}

    def _resize_image(self, image: np.ndarray) -> np.ndarray:
        """Resize image maintaining aspect ratio."""
        h, w = image.shape[:2]
        target_h, target_w = self.target_size
        
        # Calculate scaling factor
        scale = min(target_w/w, target_h/h)
        
        # Calculate new dimensions
        new_w = int(w * scale)
        new_h = int(h * scale)
        
        # Resize
        resized = cv2.resize(image, (new_w, new_h))
        
        # Create target sized image with padding
        target = np.zeros((target_h, target_w, 3), dtype=np.uint8)
        y_offset = (target_h - new_h) // 2
        x_offset = (target_w - new_w) // 2
        
        target[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = resized
        
        return target

    def _enhance_image(self, image: np.ndarray) -> np.ndarray:
        """Enhance image quality."""
        # Convert to LAB color space
        lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB)
        
        # Apply CLAHE to L channel
        clahe = cv2.createCLAHE(
            clipLimit=self.contrast_limit,
            tileGridSize=self.tile_grid_size
        )
        lab[..., 0] = clahe.apply(lab[..., 0])
        
        # Convert back to RGB
        enhanced = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
        
        return enhanced

    def _normalize_image(self, image: np.ndarray) -> np.ndarray:
        """Normalize image values."""
        return (image.astype(np.float32) - 127.5) / 127.5

    def _calculate_detection_confidence(self, face_region: np.ndarray) -> float:
        """Calculate confidence score for face detection."""
        # Simple heuristic based on variance and edge strength
        variance = np.var(face_region)
        edges = cv2.Sobel(face_region, cv2.CV_64F, 1, 1)
        edge_strength = np.mean(np.abs(edges))
        
        # Combine metrics
        confidence = (variance * edge_strength) / (255 * 255)
        return min(max(confidence, 0.0), 1.0)

    def _calculate_histogram(self, image: np.ndarray) -> np.ndarray:
        """Calculate color histogram features."""
        hist = cv2.calcHist(
            [image],
            [0, 1, 2],
            None,
            [8, 8, 8],
            [0, 256, 0, 256, 0, 256]
        )
        return cv2.normalize(hist, hist).flatten()

    def _calculate_gradients(self, image: np.ndarray) -> np.ndarray:
        """Calculate gradient features."""
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1)
        
        mag = cv2.magnitude(gx, gy)
        ang = cv2.phase(gx, gy)
        
        return np.concatenate([mag.flatten(), ang.flatten()])

    def _detect_landmarks(self, face_image: np.ndarray) -> np.ndarray:
        """Detect facial landmarks."""
        # Placeholder for actual landmark detection
        # This should be implemented with a proper facial landmark detector
        return np.array([]) 