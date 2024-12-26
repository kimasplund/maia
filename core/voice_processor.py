"""
Voice processing module for MAIA.
Handles voice commands, speech recognition, and TTS.
"""
import asyncio
import logging
import speech_recognition as sr
import pyttsx3
from typing import Dict, List, Optional, Any, Deque
from collections import deque
from datetime import datetime, timedelta
from cachetools import TTLCache
from threadpoolctl import threadpool_limits, ThreadpoolController
from ..utils.audio_utils import AudioPreprocessor
from ..database.storage import CommandStorage

_LOGGER = logging.getLogger(__name__)

class VoiceProcessorConfig:
    def __init__(self, config: Dict[str, Any]):
        self.recognition_engine = config.get('recognition_engine', 'sphinx')
        self.language = config.get('language', 'en-US')
        self.enable_noise_reduction = config.get('enable_noise_reduction', True)
        self.command_timeout = config.get('command_timeout', 30)  # seconds
        self.max_retries = config.get('max_retries', 3)
        self.cache_ttl = config.get('cache_ttl', 300)  # 5 minutes
        self.max_cache_size = config.get('max_cache_size', 1000)
        self.command_history_size = config.get('command_history_size', 100)
        self.enable_command_learning = config.get('enable_command_learning', True)
        self.confidence_threshold = config.get('confidence_threshold', 0.6)
        self.use_wake_word = config.get('use_wake_word', True)
        self.wake_words = config.get('wake_words', ['hey maia', 'maia'])

class VoiceProcessor:
    def __init__(self, config: Dict[str, Any]):
        """Initialize voice processor."""
        self.config = VoiceProcessorConfig(config)
        self.audio_preprocessor = AudioPreprocessor()
        self.command_storage = CommandStorage()
        
        # Initialize thread pool controller
        self.threadpool_controller = ThreadpoolController()
        self.thread_limits = {
            "openmp": 2,  # Limit OpenMP threads for audio processing
            "blas": 1,    # Limit BLAS threads
        }
        
        # Apply thread limits
        for prefix, limit in self.thread_limits.items():
            self.threadpool_controller.limit(limits={prefix: limit})
            _LOGGER.info(f"Applied {prefix} thread limit: {limit}")
        
        # Initialize speech recognition
        self.recognizer = sr.Recognizer()
        if self.config.enable_noise_reduction:
            self.recognizer.dynamic_energy_threshold = True
            self.recognizer.energy_threshold = 4000
            
        # Initialize TTS engine
        self.tts_engine = pyttsx3.init()
        
        # Command processing state
        self.command_queue: Deque[Dict[str, Any]] = deque(maxlen=100)
        self.processing_commands: Dict[str, asyncio.Task] = {}
        self.command_history: Deque[Dict[str, Any]] = deque(
            maxlen=self.config.command_history_size
        )
        
        # Caching
        self.recognition_cache = TTLCache(
            maxsize=self.config.max_cache_size,
            ttl=self.config.cache_ttl
        )
        
        # Performance metrics
        self.metrics = {
            "commands_processed": 0,
            "successful_commands": 0,
            "failed_commands": 0,
            "average_processing_time": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "thread_info": self.threadpool_controller.info()
        }
        
    async def process_audio(self, audio_data: bytes) -> Dict[str, Any]:
        """Process audio data for voice commands."""
        try:
            # Apply thread limits for audio processing
            with threadpool_limits(limits=self.thread_limits["openmp"], user_api="openmp"):
                # Check cache first
                cache_key = self._generate_cache_key(audio_data)
                cached_result = self.recognition_cache.get(cache_key)
                if cached_result:
                    self.metrics["cache_hits"] += 1
                    return cached_result
                    
                self.metrics["cache_misses"] += 1
                
                # Preprocess audio
                processed_audio = await self.audio_preprocessor.process(
                    audio_data,
                    noise_reduction=self.config.enable_noise_reduction
                )
                
                # Convert to AudioData for recognition
                audio = sr.AudioData(
                    processed_audio,
                    sample_rate=16000,
                    sample_width=2
                )
                
                # Perform speech recognition
                text = await self._recognize_speech(audio)
                if not text:
                    return self._create_empty_result()
                    
                # Check for wake word if enabled
                if self.config.use_wake_word and not self._check_wake_word(text):
                    return self._create_empty_result()
                    
                # Process command
                command_result = await self._process_command(text)
                
                # Cache result
                self.recognition_cache[cache_key] = command_result
                
                return command_result
            
        except Exception as e:
            _LOGGER.error(f"Audio processing failed: {str(e)}")
            return self._create_error_result(str(e))
            
    async def _recognize_speech(self, audio: sr.AudioData) -> Optional[str]:
        """Perform speech recognition with error handling and retries."""
        retries = 0
        while retries < self.config.max_retries:
            try:
                if self.config.recognition_engine == 'sphinx':
                    text = self.recognizer.recognize_sphinx(audio)
                elif self.config.recognition_engine == 'google':
                    text = self.recognizer.recognize_google(audio)
                else:
                    _LOGGER.error(f"Unsupported recognition engine: {self.config.recognition_engine}")
                    return None
                    
                return text.lower()
                
            except sr.UnknownValueError:
                _LOGGER.debug("Speech not understood")
                retries += 1
            except sr.RequestError as e:
                _LOGGER.error(f"Recognition service error: {str(e)}")
                retries += 1
            except Exception as e:
                _LOGGER.error(f"Speech recognition failed: {str(e)}")
                retries += 1
                
            if retries < self.config.max_retries:
                await asyncio.sleep(1)
                
        return None
        
    def _check_wake_word(self, text: str) -> bool:
        """Check if the text contains a wake word."""
        return any(wake_word in text.lower() for wake_word in self.config.wake_words)
        
    async def _process_command(self, text: str) -> Dict[str, Any]:
        """Process recognized text as a command."""
        start_time = datetime.now()
        
        try:
            # Remove wake word if present
            for wake_word in self.config.wake_words:
                text = text.replace(wake_word, '').strip()
                
            # Get command intent and confidence
            intent_result = await self.command_storage.get_command_intent(text)
            
            if intent_result["confidence"] < self.config.confidence_threshold:
                return self._create_empty_result("Low confidence in command recognition")
                
            # Create command context
            command_id = f"cmd_{datetime.now().timestamp()}"
            command = {
                "id": command_id,
                "text": text,
                "intent": intent_result["intent"],
                "confidence": intent_result["confidence"],
                "timestamp": datetime.now().isoformat(),
                "status": "pending"
            }
            
            # Add to queue and history
            self.command_queue.append(command)
            self.command_history.append(command)
            
            # Start processing
            task = asyncio.create_task(
                self._execute_command(command_id, command)
            )
            self.processing_commands[command_id] = task
            
            # Wait for completion or timeout
            try:
                await asyncio.wait_for(task, timeout=self.config.command_timeout)
            except asyncio.TimeoutError:
                command["status"] = "timeout"
                self.metrics["failed_commands"] += 1
                
            # Update metrics
            processing_time = (datetime.now() - start_time).total_seconds()
            self._update_metrics(command["status"] == "completed", processing_time)
            
            return command
            
        except Exception as e:
            _LOGGER.error(f"Command processing failed: {str(e)}")
            self.metrics["failed_commands"] += 1
            return self._create_error_result(str(e))
            
    async def _execute_command(self, command_id: str, command: Dict[str, Any]) -> None:
        """Execute a voice command."""
        try:
            # Get command handler
            handler = await self.command_storage.get_command_handler(command["intent"])
            if not handler:
                command["status"] = "failed"
                command["error"] = "No handler found for command"
                return
                
            # Execute handler
            result = await handler(command)
            
            # Update command status
            command["status"] = "completed" if result.get("success") else "failed"
            command["result"] = result
            
            # Learn from successful commands if enabled
            if (self.config.enable_command_learning and 
                command["status"] == "completed"):
                await self.command_storage.learn_command(command)
                
        except Exception as e:
            command["status"] = "failed"
            command["error"] = str(e)
            _LOGGER.error(f"Command execution failed: {str(e)}")
            
        finally:
            if command_id in self.processing_commands:
                del self.processing_commands[command_id]
                
    def _generate_cache_key(self, audio_data: bytes) -> str:
        """Generate cache key for audio data."""
        return str(hash(audio_data))
        
    def _update_metrics(self, success: bool, processing_time: float) -> None:
        """Update performance metrics."""
        self.metrics["commands_processed"] += 1
        if success:
            self.metrics["successful_commands"] += 1
        else:
            self.metrics["failed_commands"] += 1
            
        # Update average processing time
        total_time = (self.metrics["average_processing_time"] * 
                     (self.metrics["commands_processed"] - 1) +
                     processing_time)
        self.metrics["average_processing_time"] = (
            total_time / self.metrics["commands_processed"]
        )
        
    def _create_empty_result(self, reason: Optional[str] = None) -> Dict[str, Any]:
        """Create empty result."""
        return {
            "success": True,
            "command_detected": False,
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
            "metrics": {
                **self.metrics,
                "thread_info": self.threadpool_controller.info()
            }
        }
        
    def _create_error_result(self, error: str) -> Dict[str, Any]:
        """Create error result."""
        return {
            "success": False,
            "error": error,
            "timestamp": datetime.now().isoformat(),
            "metrics": {
                **self.metrics,
                "thread_info": self.threadpool_controller.info()
            }
        }
        
    async def cleanup(self) -> None:
        """Cleanup resources."""
        # Cancel any processing commands
        for task in self.processing_commands.values():
            task.cancel()
            
        try:
            await asyncio.gather(*self.processing_commands.values())
        except asyncio.CancelledError:
            pass
            
        # Clear caches and queues
        self.recognition_cache.clear()
        self.command_queue.clear()
        self.command_history.clear()
        self.processing_commands.clear()
        
        # Reset thread limits to default
        self.threadpool_controller.reset()