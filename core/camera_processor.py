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
    """Handles camera streams and face recognition."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize camera processor."""
        self.config = FaceRecognitionConfig(**(config or {}))
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
        if self.config["use_gpu"]:
            if cv2.cuda.getCudaEnabledDeviceCount() > 0:
                self.model_type = "cnn"  # CNN model for GPU
                _LOGGER.info("GPU acceleration enabled for face recognition")
            else:
                self.model_type = "hog"  # Fall back to HOG
                _LOGGER.warning("GPU not available, falling back to CPU processing")
        else:
            self.model_type = "hog"  # HOG model for CPU
            
        # Initialize caches
        self.encoding_cache = TTLCache(
            maxsize=self.config["max_cache_size"],
            ttl=self.config["cache_ttl"]
        )
        self.recognition_cache = LRUCache(maxsize=self.config["max_cache_size"])
        self.landmark_cache = TTLCache(
            maxsize=self.config["max_cache_size"],
            ttl=self.config["cache_ttl"]
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
                self.config["num_workers"],
                self.thread_limits["openmp"] * 2
            )
        )
        
        # Apply thread limits
        self._apply_thread_limits()
        
    def _apply_thread_limits(self):
        """Apply thread limits to various libraries."""
        for prefix, limit in self.thread_limits.items():
            self.threadpool_controller.limit(limits={prefix: limit})
            _LOGGER.info(f"Applied {prefix} thread limit: {limit}")
        
    async def process_frame(self, frame: np.ndarray) -> Dict[str, Any]:
        """Process a single frame for face detection and recognition."""
        start_time = datetime.now()
        
        try:
            # Apply thread limits for frame processing
            with threadpool_limits(limits=self.thread_limits["openmp"], user_api="openmp"):
                # Check frame cache
                frame_hash = self._compute_frame_hash(frame)
                cached_result = self.recognition_cache.get(frame_hash)
                if cached_result:
                    self.metrics["cache_hits"] += 1
                    return cached_result
                    
                self.metrics["cache_misses"] += 1
                
                # Preprocess frame
                processed_frame = await self.image_preprocessor.preprocess(frame)
                
                # Detect faces
                face_locations = await self._detect_faces(processed_frame)
                if not face_locations:
                    return self._create_empty_result()
                    
                # Process faces in batches if enabled
                if self.config["batch_processing"] and len(face_locations) > 1:
                    results = await self._batch_process_faces(processed_frame, face_locations)
                else:
                    results = await self._process_faces_sequential(processed_frame, face_locations)
                    
                # Create final result
                result = {
                    "faces_detected": len(results),
                    "faces": results,
                    "timestamp": datetime.now().isoformat(),
                    "metrics": self._get_metrics()
                }
                
                # Cache result
                self.recognition_cache[frame_hash] = result
                
                # Update metrics
                processing_time = (datetime.now() - start_time).total_seconds()
                self.metrics["total_processing_time"] += processing_time
                self.metrics["processed_frames"] += 1
                self.metrics["recognition_times"].append(processing_time)
                
                return result
                
        except Exception as e:
            _LOGGER.error(f"Frame processing failed: {str(e)}")
            return self._create_error_result(str(e))
            # Check frame cache
            frame_hash = self._compute_frame_hash(frame)
            cached_result = self.recognition_cache.get(frame_hash)
            if cached_result:
                self.metrics["cache_hits"] += 1
                return cached_result
                
            self.metrics["cache_misses"] += 1
            
            # Preprocess frame
            processed_frame = await self.image_preprocessor.preprocess(frame)
            
            # Detect faces
            face_locations = await self._detect_faces(processed_frame)
            if not face_locations:
                return self._create_empty_result()
                
            # Process faces in batches if enabled
            if self.config["batch_processing"] and len(face_locations) > 1:
                results = await self._batch_process_faces(processed_frame, face_locations)
            else:
                results = await self._process_faces_sequential(processed_frame, face_locations)
                
            # Create final result
            result = {
                "faces_detected": len(results),
                "faces": results,
                "timestamp": datetime.now().isoformat(),
                "metrics": self._get_metrics()
            }
            
            # Cache result
            self.recognition_cache[frame_hash] = result
            
            # Update metrics
            processing_time = (datetime.now() - start_time).total_seconds()
            self.metrics["total_processing_time"] += processing_time
            self.metrics["processed_frames"] += 1
            self.metrics["recognition_times"].append(processing_time)
            
            return result
            
        except Exception as e:
            _LOGGER.error(f"Frame processing failed: {str(e)}")
            return self._create_error_result(str(e))
            
    async def _detect_faces(self, frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """Detect faces in frame with error handling."""
        try:
            return face_recognition.face_locations(
                frame,
                model=self.model_type,
                number_of_times_to_upsample=1
            )
        except Exception as e:
            _LOGGER.error(f"Face detection failed: {str(e)}")
            return []
            
    async def _batch_process_faces(
        self,
        frame: np.ndarray,
        face_locations: List[Tuple[int, int, int, int]]
    ) -> List[Dict[str, Any]]:
        """Process faces in batches for better performance."""
        results = []
        batch_size = min(self.config["max_batch_size"], len(face_locations))
        
        for i in range(0, len(face_locations), batch_size):
            batch_locations = face_locations[i:i + batch_size]
            
            # Process batch in thread pool
            batch_futures = []
            for location in batch_locations:
                future = self.executor.submit(
                    self._process_single_face,
                    frame,
                    location
                )
                batch_futures.append(future)
                
            # Collect batch results
            for future in batch_futures:
                try:
                    result = await asyncio.wrap_future(future)
                    if result:
                        results.append(result)
                except Exception as e:
                    _LOGGER.error(f"Batch face processing failed: {str(e)}")
                    
            self.metrics["batch_sizes"].append(len(batch_locations))
            
        return results
        
    def _process_single_face(
        self,
        frame: np.ndarray,
        face_location: Tuple[int, int, int, int]
    ) -> Optional[Dict[str, Any]]:
        """Process a single face with caching."""
        try:
            # Generate cache key
            face_hash = self._compute_face_hash(frame, face_location)
            
            # Check encoding cache
            encoding = self.encoding_cache.get(face_hash)
            if encoding is None:
                encoding = face_recognition.face_encodings(
                    frame,
                    [face_location],
                    model="large",
                    num_jitters=2 if self.config["use_gpu"] else 1
                )[0]
                self.encoding_cache[face_hash] = encoding
                
            # Get landmarks if enabled
            landmarks = None
            if self.config["detect_landmarks"]:
                landmarks = self.landmark_cache.get(face_hash)
                if landmarks is None:
                    landmarks = face_recognition.face_landmarks(
                        frame,
                        [face_location],
                        model="large"
                    )[0]
                    self.landmark_cache[face_hash] = landmarks
                    
            # Match face
            match = self._match_face_sync(encoding)
            
            return {
                "location": face_location,
                "encoding": encoding.tolist(),
                "match": match,
                "confidence": match.get("confidence", 0) if match else 0,
                "landmarks": landmarks
            }
            
        except Exception as e:
            _LOGGER.error(f"Single face processing failed: {str(e)}")
            return None
            
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
            
    def _compute_frame_hash(self, frame: np.ndarray) -> str:
        """Compute hash for frame caching."""
        return str(hash(frame.tobytes()))
        
    def _compute_face_hash(
        self,
        frame: np.ndarray,
        face_location: Tuple[int, int, int, int]
    ) -> str:
        """Compute hash for face region caching."""
        face_image = frame[
            face_location[0]:face_location[2],
            face_location[3]:face_location[1]
        ]
        return str(hash(face_image.tobytes()))
        
    def _get_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics."""
        total_requests = self.metrics["cache_hits"] + self.metrics["cache_misses"]
        avg_processing_time = (
            self.metrics["total_processing_time"] /
            max(1, self.metrics["processed_frames"])
        )
        
        return {
            "cache_hit_rate": self.metrics["cache_hits"] / max(1, total_requests),
            "average_processing_time": avg_processing_time,
            "average_batch_size": (
                sum(self.metrics["batch_sizes"]) /
                max(1, len(self.metrics["batch_sizes"]))
            ),
            "processed_frames": self.metrics["processed_frames"]
        }
        
    def _create_empty_result(self) -> Dict[str, Any]:
        """Create result for frames with no faces."""
        return {
            "faces_detected": 0,
            "faces": [],
            "timestamp": datetime.now().isoformat(),
            "metrics": self._get_metrics()
        }
        
    def _create_error_result(self, error: str) -> Dict[str, Any]:
        """Create result for processing errors."""
        return {
            "error": error,
            "timestamp": datetime.now().isoformat(),
            "metrics": self._get_metrics()
        }
        
    def clear_caches(self) -> None:
        """Clear all caches."""
        self.encoding_cache.clear()
        self.recognition_cache.clear()
        self.landmark_cache.clear()
        
    async def cleanup(self) -> None:
        """Cleanup resources."""
        self.clear_caches()
        self.executor.shutdown(wait=True) 