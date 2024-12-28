"""
Face recognition pipeline for MAIA.
"""
import cv2
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
import face_recognition
import logging
from concurrent.futures import ThreadPoolExecutor
from ..database.storage import FaceStorage

@dataclass
class FaceDetection:
    """Face detection result."""
    bbox: Tuple[int, int, int, int]  # (top, right, bottom, left)
    confidence: float
    landmarks: Dict[str, Tuple[int, int]]
    encoding: np.ndarray

class FaceRecognitionPipeline:
    """Pipeline for face detection, recognition, and tracking."""
    
    def __init__(
        self,
        face_storage: FaceStorage,
        model: str = "hog",  # 'hog' or 'cnn'
        num_jitters: int = 1,
        distance_threshold: float = 0.6,
        min_face_size: int = 20,
        max_workers: int = 4
    ):
        """Initialize face recognition pipeline."""
        self.face_storage = face_storage
        self.model = model
        self.num_jitters = num_jitters
        self.distance_threshold = distance_threshold
        self.min_face_size = min_face_size
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.logger = logging.getLogger(__name__)
        
    async def process_frame(
        self,
        frame: np.ndarray,
        return_face_locations: bool = True,
        return_landmarks: bool = True
    ) -> List[Dict[str, Any]]:
        """Process a single frame and detect/recognize faces."""
        try:
            # Convert frame to RGB (face_recognition uses RGB)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Detect face locations
            face_locations = face_recognition.face_locations(
                rgb_frame,
                model=self.model,
                number_of_times_to_upsample=1
            )
            
            if not face_locations:
                return []
                
            # Get face landmarks
            face_landmarks = face_recognition.face_landmarks(rgb_frame, face_locations)
            
            # Compute face encodings
            face_encodings = face_recognition.face_encodings(
                rgb_frame,
                face_locations,
                num_jitters=self.num_jitters
            )
            
            # Match faces against known faces
            known_faces = await self.face_storage.get_all_faces()
            known_encodings = [face["encoding"] for face in known_faces]
            known_names = [face["name"] for face in known_faces]
            
            results = []
            for location, landmarks, encoding in zip(
                face_locations, face_landmarks, face_encodings
            ):
                result = {
                    "bbox": location,
                    "confidence": 1.0,  # Default confidence
                }
                
                if return_landmarks:
                    result["landmarks"] = landmarks
                    
                if known_encodings:
                    # Compare against known faces
                    distances = face_recognition.face_distance(known_encodings, encoding)
                    if len(distances) > 0:
                        best_match_idx = np.argmin(distances)
                        min_distance = distances[best_match_idx]
                        
                        if min_distance <= self.distance_threshold:
                            result["name"] = known_names[best_match_idx]
                            result["confidence"] = 1 - min_distance
                        else:
                            result["name"] = "unknown"
                            result["confidence"] = 1 - min_distance
                else:
                    result["name"] = "unknown"
                
                # Filter out small faces
                height = location[2] - location[0]
                width = location[1] - location[3]
                if min(height, width) >= self.min_face_size:
                    results.append(result)
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error processing frame: {str(e)}")
            return []
            
    async def register_face(
        self,
        frame: np.ndarray,
        name: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Register a new face in the database."""
        try:
            # Convert frame to RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Detect faces
            face_locations = face_recognition.face_locations(
                rgb_frame,
                model=self.model,
                number_of_times_to_upsample=1
            )
            
            if not face_locations:
                self.logger.warning("No face detected in frame")
                return False
                
            if len(face_locations) > 1:
                self.logger.warning("Multiple faces detected in frame")
                return False
                
            # Compute face encoding
            face_encodings = face_recognition.face_encodings(
                rgb_frame,
                face_locations,
                num_jitters=self.num_jitters
            )
            
            if not face_encodings:
                self.logger.warning("Failed to compute face encoding")
                return False
                
            # Store face in database
            face_data = {
                "name": name,
                "encoding": face_encodings[0],
                "metadata": metadata or {}
            }
            
            success = await self.face_storage.add_face(face_data)
            return success
            
        except Exception as e:
            self.logger.error(f"Error registering face: {str(e)}")
            return False
            
    async def update_face(
        self,
        name: str,
        frame: np.ndarray,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Update an existing face in the database."""
        try:
            # Convert frame to RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Detect faces
            face_locations = face_recognition.face_locations(
                rgb_frame,
                model=self.model,
                number_of_times_to_upsample=1
            )
            
            if not face_locations:
                self.logger.warning("No face detected in frame")
                return False
                
            if len(face_locations) > 1:
                self.logger.warning("Multiple faces detected in frame")
                return False
                
            # Compute face encoding
            face_encodings = face_recognition.face_encodings(
                rgb_frame,
                face_locations,
                num_jitters=self.num_jitters
            )
            
            if not face_encodings:
                self.logger.warning("Failed to compute face encoding")
                return False
                
            # Update face in database
            face_data = {
                "name": name,
                "encoding": face_encodings[0],
                "metadata": metadata or {}
            }
            
            success = await self.face_storage.update_face(name, face_data)
            return success
            
        except Exception as e:
            self.logger.error(f"Error updating face: {str(e)}")
            return False
            
    async def delete_face(self, name: str) -> bool:
        """Delete a face from the database."""
        try:
            success = await self.face_storage.delete_face(name)
            return success
            
        except Exception as e:
            self.logger.error(f"Error deleting face: {str(e)}")
            return False
            
    def draw_results(
        self,
        frame: np.ndarray,
        results: List[Dict[str, Any]],
        draw_landmarks: bool = True,
        draw_labels: bool = True
    ) -> np.ndarray:
        """Draw detection results on frame."""
        output = frame.copy()
        
        for result in results:
            bbox = result["bbox"]
            name = result.get("name", "unknown")
            confidence = result.get("confidence", 1.0)
            
            # Draw bounding box
            cv2.rectangle(
                output,
                (bbox[3], bbox[0]),  # left, top
                (bbox[1], bbox[2]),  # right, bottom
                (0, 255, 0),
                2
            )
            
            if draw_labels:
                # Draw name and confidence
                label = f"{name} ({confidence:.2f})"
                cv2.putText(
                    output,
                    label,
                    (bbox[3], bbox[0] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    2
                )
            
            if draw_landmarks and "landmarks" in result:
                # Draw facial landmarks
                for feature, points in result["landmarks"].items():
                    for point in points:
                        cv2.circle(
                            output,
                            point,
                            2,
                            (0, 0, 255),
                            -1
                        )
        
        return output 