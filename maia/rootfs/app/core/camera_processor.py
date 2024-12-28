"""
Camera processing module for MAIA.
Handles video streams, face recognition, and user verification.
"""
import face_recognition
import cv2
import numpy as np
import asyncio
from typing import Dict, List, Optional, Tuple, Any, Set
from datetime import datetime, timedelta
import logging
from pathlib import Path
from cachetools import TTLCache, LRUCache
from threadpoolctl import threadpool_limits, ThreadpoolController
from ..utils.image_utils import ImagePreprocessor
from ..database.storage import FaceStorage
from concurrent.futures import ThreadPoolExecutor
import aiohttp
import time

_LOGGER = logging.getLogger(__name__)

class FaceRecognitionConfig(Dict):
    """Configuration for face recognition."""
    model_type: str = "hog"  # 'hog' or 'cnn'
    tolerance: float = 0.6
    min_detection_size: int = 20
    batch_size: int = 128
    num_workers: int = 4
    use_gpu: bool = False
    detect_landmarks: bool = True
    detect_attributes: bool = True
    unknown_face_threshold: float = 0.8
    remember_unknown_faces: bool = True
    max_unknown_faces: int = 100
    cache_ttl: int = 300  # 5 minutes
    max_cache_size: int = 1000
    batch_processing: bool = True
    max_batch_size: int = 32

class CameraProcessor:
    """Camera processor for MAIA."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize camera processor."""
        self.config = config or {}
        self.image_preprocessor = ImagePreprocessor()
        self.face_storage = FaceStorage()
        
        # Initialize thread pool controller
        self.threadpool_controller = ThreadpoolController()
        self.thread_limits = self.config.get("thread_limits", {
            "openmp": 4,  # Limit OpenMP threads
            "blas": 2,    # Limit BLAS threads
        })
        
        # Apply thread limits
        for prefix, limit in self.thread_limits.items():
            self.threadpool_controller.limit(limits={prefix: limit})
            _LOGGER.info(f"Applied {prefix} thread limit: {limit}")
        
        # Initialize face recognition settings
        self.model_type = "hog"  # Default to CPU
        self._gpu_url = None
        self._gpu_session = None
        
        # Initialize caches
        self.encoding_cache = TTLCache(
            maxsize=self.config.get("max_cache_size", 1000),
            ttl=self.config.get("cache_ttl", 3600)
        )
        self.recognition_cache = LRUCache(maxsize=self.config.get("max_cache_size", 1000))
        self.landmark_cache = TTLCache(
            maxsize=self.config.get("max_cache_size", 1000),
            ttl=self.config.get("cache_ttl", 3600)
        )
        
        # Performance metrics
        self.metrics = {
            "cache_hits": 0,
            "cache_misses": 0,
            "total_processing_time": 0,
            "processed_frames": 0,
            "batch_sizes": [],
            "recognition_times": [],
            "thread_info": self.threadpool_controller.info()
        }
        
        # Initialize thread pool for batch processing with controlled limits
        self.executor = ThreadPoolExecutor(
            max_workers=min(
                self.config.get("num_workers", 4),
                self.thread_limits["openmp"] * 2
            )
        )
        
        # Apply thread limits
        self._apply_thread_limits()
        
    def enable_gpu(self, gpu_url: str):
        """Enable GPU processing using companion service."""
        self._gpu_url = gpu_url.rstrip('/')
        self._gpu_session = aiohttp.ClientSession()
        self.model_type = "cnn"
        _LOGGER.info(f"Enabled GPU processing using companion at {gpu_url}")
        
    def disable_gpu(self):
        """Disable GPU processing."""
        if self._gpu_session:
            asyncio.create_task(self._gpu_session.close())
        self._gpu_url = None
        self._gpu_session = None
        self.model_type = "hog"
        _LOGGER.info("Disabled GPU processing")
        
    async def process_frame(self, frame: np.ndarray) -> Dict[str, Any]:
        """Process video frame."""
        try:
            start_time = time.time()
            
            # Preprocess frame
            processed_frame = self.image_preprocessor.preprocess(frame)
            
            # Try GPU processing first
            if self._gpu_url and self._gpu_session:
                try:
                    result = await self._process_frame_gpu(processed_frame)
                    if result:
                        return result
                except Exception as e:
                    _LOGGER.error(f"GPU processing failed, falling back to CPU: {str(e)}")
            
            # Fall back to CPU processing
            return await self._process_frame_cpu(processed_frame)
            
        except Exception as e:
            _LOGGER.error(f"Frame processing failed: {str(e)}")
            return {"error": str(e)}
            
    async def _process_frame_gpu(self, frame: np.ndarray) -> Optional[Dict[str, Any]]:
        """Process frame using GPU companion service."""
        try:
            # Encode frame as JPEG
            _, buffer = cv2.imencode('.jpg', frame)
            
            # Send to companion service
            data = aiohttp.FormData()
            data.add_field('frame', buffer.tobytes(), 
                          filename='frame.jpg',
                          content_type='image/jpeg')
            
            async with self._gpu_session.post(
                f"{self._gpu_url}/process_frame",
                data=data
            ) as response:
                if response.status == 200:
                    return await response.json()
                return None
                
        except Exception as e:
            _LOGGER.error(f"GPU frame processing failed: {str(e)}")
            return None
            
    async def _process_frame_cpu(self, frame: np.ndarray) -> Dict[str, Any]:
        """Process frame using CPU."""
        try:
            # Apply thread limits for image processing
            with threadpool_limits(limits=self.thread_limits):
                # Preprocess frame
                processed_frame = await self.image_preprocessor.preprocess(frame)
                
                # Check cache
                frame_hash = hash(processed_frame.tobytes())
                if frame_hash in self.recognition_cache:
                    self.metrics["cache_hits"] += 1
                    return self.recognition_cache[frame_hash]
                    
                self.metrics["cache_misses"] += 1
                
                # Detect faces
                face_locations = face_recognition.face_locations(
                    processed_frame,
                    model=self.model_type,
                    number_of_times_to_upsample=1
                )
                
                if not face_locations:
                    return self._create_empty_result()
                    
                # Get face encodings
                face_encodings = face_recognition.face_encodings(
                    processed_frame,
                    face_locations,
                    model=self.model_type
                )
                
                # Process faces in parallel
                if self.config["batch_processing"] and len(face_encodings) > 1:
                    tasks = []
                    for encoding in face_encodings:
                        tasks.append(
                            asyncio.get_event_loop().run_in_executor(
                                self.executor,
                                self._match_face_sync,
                                encoding
                            )
                        )
                    face_matches = await asyncio.gather(*tasks)
                else:
                    face_matches = [
                        await asyncio.get_event_loop().run_in_executor(
                            self.executor,
                            self._match_face_sync,
                            encoding
                        )
                        for encoding in face_encodings
                    ]
                
                # Process landmarks if enabled
                landmarks = None
                if self.config["detect_landmarks"]:
                    landmarks = face_recognition.face_landmarks(
                        processed_frame,
                        face_locations
                    )
                
                # Create result
                result = {
                    "faces": [
                        {
                            "location": location,
                            "match": match,
                            "landmarks": lm if landmarks else None
                        }
                        for location, match, lm in zip(
                            face_locations,
                            face_matches,
                            landmarks or [None] * len(face_locations)
                        )
                    ],
                    "timestamp": datetime.now().isoformat(),
                    "metrics": self.metrics
                }
                
                # Cache result
                self.recognition_cache[frame_hash] = result
                
                return result
                
        except Exception as e:
            _LOGGER.error(f"Frame processing failed: {str(e)}")
            return self._create_error_result(str(e))

    def _match_face_sync(self, encoding: np.ndarray) -> Optional[Dict[str, Any]]:
        """Synchronous version of face matching for thread pool."""
        try:
            known_encodings = self.face_storage.get_all_encodings_sync()
            if not known_encodings:
                return None
                
            known_array = np.array(list(known_encodings.values()))
            distances = face_recognition.face_distance(known_array, encoding)
            
            best_match_idx = np.argmin(distances)
            min_distance = distances[best_match_idx]
            
            if min_distance <= self.config["tolerance"]:
                user_id = list(known_encodings.keys())[best_match_idx]
                user_info = self.face_storage.get_user_info_sync(user_id)
                
                return {
                    "user_id": user_id,
                    "name": user_info.get("name", "Unknown"),
                    "confidence": 1 - min_distance,
                    "distance": min_distance
                }
                
            return None
            
        except Exception as e:
            _LOGGER.error(f"Face matching failed: {str(e)}")
            return None

    def _create_empty_result(self) -> Dict[str, Any]:
        """Create empty result when no faces are detected."""
        return {
            "faces": [],
            "timestamp": datetime.now().isoformat(),
            "metrics": self.metrics
        }

    def _create_error_result(self, error: str) -> Dict[str, Any]:
        """Create error result."""
        return {
            "error": error,
            "timestamp": datetime.now().isoformat(),
            "metrics": self.metrics
        }

    def cleanup(self):
        """Clean up resources."""
        # Reset thread limits to default
        self.threadpool_controller.reset()
        _LOGGER.info("Reset thread limits to default")
        
        # Shutdown thread pool
        self.executor.shutdown(wait=True)
        _LOGGER.info("Thread pool executor shut down") 