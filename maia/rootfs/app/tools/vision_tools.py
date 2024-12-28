"""
Vision processing tools for MAIA.
"""
from typing import Dict, List, Optional, Any, Tuple
import logging
import cv2
import numpy as np
from PIL import Image
import io
import base64
import os
from pathlib import Path
from ..core.openai_integration import OpenAIIntegration
from ..database.storage import CommandStorage

_LOGGER = logging.getLogger(__name__)

class VisionTools:
    """Vision processing tools."""
    
    def __init__(
        self,
        openai: OpenAIIntegration,
        storage: CommandStorage,
        models_dir: Optional[str] = None
    ):
        """Initialize vision tools."""
        self.openai = openai
        self.storage = storage
        self.models_dir = models_dir or os.path.join(os.path.dirname(__file__), 'models')
        os.makedirs(self.models_dir, exist_ok=True)
        
        # Model paths
        self.yolo_weights = os.path.join(self.models_dir, 'yolov3.weights')
        self.yolo_cfg = os.path.join(self.models_dir, 'yolov3.cfg')
        self.coco_names = os.path.join(self.models_dir, 'coco.names')
        self.face_cascade_path = os.path.join(
            cv2.data.haarcascades,
            'haarcascade_frontalface_default.xml'
        )
        
        # Validate model files exist
        self._validate_models()
        
    def _validate_models(self):
        """Validate required model files exist."""
        missing_files = []
        
        if not os.path.exists(self.yolo_weights):
            missing_files.append(self.yolo_weights)
        if not os.path.exists(self.yolo_cfg):
            missing_files.append(self.yolo_cfg)
        if not os.path.exists(self.coco_names):
            missing_files.append(self.coco_names)
        if not os.path.exists(self.face_cascade_path):
            missing_files.append(self.face_cascade_path)
            
        if missing_files:
            _LOGGER.warning(
                f"Missing model files: {', '.join(missing_files)}. "
                "Some vision features may be unavailable."
            )
        
    async def process_image(
        self,
        image_data: bytes,
        prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process image using OpenAI vision model."""
        try:
            # Convert image to base64
            image_b64 = base64.b64encode(image_data).decode('utf-8')
            
            # Create messages for vision API
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt or "What do you see in this image?"
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_b64}"
                            }
                        }
                    ]
                }
            ]
            
            # Process with OpenAI
            result = await self.openai.process_vision(messages)
            
            # Store result
            await self.storage.store_command({
                "type": "vision_analysis",
                "prompt": prompt,
                "result": result
            })
            
            return result
            
        except Exception as e:
            _LOGGER.error(f"Failed to process image: {str(e)}")
            return {"error": str(e)}
            
    async def detect_faces(self, image_data: bytes) -> List[Dict[str, Any]]:
        """Detect faces in image."""
        try:
            # Validate face cascade file exists
            if not os.path.exists(self.face_cascade_path):
                raise FileNotFoundError(
                    "Face cascade classifier not found. Please ensure "
                    "haarcascade_frontalface_default.xml is available."
                )
            
            # Convert bytes to numpy array
            nparr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            # Load face cascade
            face_cascade = cv2.CascadeClassifier(self.face_cascade_path)
            
            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Detect faces
            faces = face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(30, 30)
            )
            
            # Process results
            results = []
            for (x, y, w, h) in faces:
                face_dict = {
                    "x": int(x),
                    "y": int(y),
                    "width": int(w),
                    "height": int(h)
                }
                results.append(face_dict)
                
            return results
            
        except Exception as e:
            _LOGGER.error(f"Failed to detect faces: {str(e)}")
            return []
            
    async def analyze_scene(self, image_data: bytes) -> Dict[str, Any]:
        """Analyze scene content and context."""
        try:
            # Process with OpenAI
            result = await self.process_image(
                image_data,
                "Analyze this scene and describe the key elements, activities, and context."
            )
            
            return result
            
        except Exception as e:
            _LOGGER.error(f"Failed to analyze scene: {str(e)}")
            return {"error": str(e)}
            
    async def detect_objects(
        self,
        image_data: bytes,
        confidence_threshold: float = 0.5
    ) -> List[Dict[str, Any]]:
        """Detect objects in image using YOLO."""
        try:
            # Validate required files exist
            if not all(os.path.exists(f) for f in [self.yolo_weights, self.yolo_cfg, self.coco_names]):
                raise FileNotFoundError(
                    "Required YOLO model files not found. Please ensure yolov3.weights, "
                    "yolov3.cfg, and coco.names are present in the models directory."
                )
            
            # Convert bytes to numpy array
            nparr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            # Load YOLO model
            net = cv2.dnn.readNet(
                self.yolo_weights,
                self.yolo_cfg
            )
            
            # Load class names
            with open(self.coco_names, "r") as f:
                classes = [line.strip() for line in f.readlines()]
                
            # Get output layers
            layer_names = net.getLayerNames()
            output_layers = [layer_names[i - 1] for i in net.getUnconnectedOutLayers()]
            
            # Prepare image for YOLO
            height, width, _ = img.shape
            blob = cv2.dnn.blobFromImage(
                img,
                0.00392,
                (416, 416),
                (0, 0, 0),
                True,
                crop=False
            )
            
            net.setInput(blob)
            outs = net.forward(output_layers)
            
            # Process results
            class_ids = []
            confidences = []
            boxes = []
            
            for out in outs:
                for detection in out:
                    scores = detection[5:]
                    class_id = np.argmax(scores)
                    confidence = scores[class_id]
                    
                    if confidence > confidence_threshold:
                        # Object detected
                        center_x = int(detection[0] * width)
                        center_y = int(detection[1] * height)
                        w = int(detection[2] * width)
                        h = int(detection[3] * height)
                        
                        # Rectangle coordinates
                        x = int(center_x - w / 2)
                        y = int(center_y - h / 2)
                        
                        boxes.append([x, y, w, h])
                        confidences.append(float(confidence))
                        class_ids.append(class_id)
                        
            # Apply non-maximum suppression
            indexes = cv2.dnn.NMSBoxes(
                boxes,
                confidences,
                confidence_threshold,
                0.4
            )
            
            # Prepare results
            results = []
            for i in range(len(boxes)):
                if i in indexes:
                    x, y, w, h = boxes[i]
                    results.append({
                        "class": classes[class_ids[i]],
                        "confidence": confidences[i],
                        "box": {
                            "x": x,
                            "y": y,
                            "width": w,
                            "height": h
                        }
                    })
                    
            return results
            
        except Exception as e:
            _LOGGER.error(f"Failed to detect objects: {str(e)}")
            return []
            
    async def compare_faces(
        self,
        face1_data: bytes,
        face2_data: bytes
    ) -> Dict[str, Any]:
        """Compare two faces for similarity."""
        try:
            # Convert bytes to numpy arrays
            nparr1 = np.frombuffer(face1_data, np.uint8)
            nparr2 = np.frombuffer(face2_data, np.uint8)
            
            img1 = cv2.imdecode(nparr1, cv2.IMREAD_COLOR)
            img2 = cv2.imdecode(nparr2, cv2.IMREAD_COLOR)
            
            # Convert to grayscale
            gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
            gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
            
            # Initialize face detector
            face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )
            
            # Detect faces
            faces1 = face_cascade.detectMultiScale(gray1, 1.1, 4)
            faces2 = face_cascade.detectMultiScale(gray2, 1.1, 4)
            
            if len(faces1) == 0 or len(faces2) == 0:
                return {
                    "error": "No faces detected in one or both images"
                }
                
            # Get first face from each image
            (x1, y1, w1, h1) = faces1[0]
            (x2, y2, w2, h2) = faces2[0]
            
            # Extract face ROIs
            roi1 = gray1[y1:y1+h1, x1:x1+w1]
            roi2 = gray2[y2:y2+h2, x2:x2+w2]
            
            # Resize to same size
            roi1 = cv2.resize(roi1, (100, 100))
            roi2 = cv2.resize(roi2, (100, 100))
            
            # Compare using various metrics
            ssim = cv2.matchTemplate(roi1, roi2, cv2.TM_CCOEFF_NORMED)[0][0]
            mse = np.mean((roi1 - roi2) ** 2)
            
            return {
                "similarity_score": float(ssim),
                "mean_squared_error": float(mse),
                "match": ssim > 0.8
            }
            
        except Exception as e:
            _LOGGER.error(f"Failed to compare faces: {str(e)}")
            return {"error": str(e)} 