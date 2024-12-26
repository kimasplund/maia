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

    async def process_audio(self, audio_data: bytes) -> Optional[Dict[str, Any]]:
        """Process audio data and return recognized command."""
        try:
            # Apply thread limits for audio processing
            with threadpool_limits(limits=self.thread_limits):
                # Preprocess audio
                processed_audio = await self.audio_preprocessor.preprocess(
                    audio_data,
                    enable_noise_reduction=self.config.enable_noise_reduction
                )
                
                # Check cache
                cache_key = hash(processed_audio.tobytes())
                if cache_key in self.recognition_cache:
                    self.metrics["cache_hits"] += 1
                    return self.recognition_cache[cache_key]
                    
                self.metrics["cache_misses"] += 1
                
                # Convert to AudioData for recognition
                audio = sr.AudioData(
                    processed_audio.tobytes(),
                    sample_rate=16000,
                    sample_width=2
                )
                
                # Recognize speech
                text = await self._recognize_speech(audio)
                if not text:
                    return None
                    
                # Check for wake word if enabled
                if self.config.use_wake_word and not any(
                    wake_word in text.lower() 
                    for wake_word in self.config.wake_words
                ):
                    return None
                    
                # Process command
                command = await self._process_command(text)
                if command:
                    self.recognition_cache[cache_key] = command
                    
                return command
                
        except Exception as e:
            _LOGGER.error(f"Error processing audio: {str(e)}")
            return None
            
    async def _recognize_speech(self, audio: sr.AudioData) -> Optional[str]:
        """Recognize speech from audio data."""
        try:
            if self.config.recognition_engine == "google":
                text = await asyncio.to_thread(
                    self.recognizer.recognize_google,
                    audio,
                    language=self.config.language
                )
            elif self.config.recognition_engine == "sphinx":
                text = await asyncio.to_thread(
                    self.recognizer.recognize_sphinx,
                    audio,
                    language=self.config.language
                )
            else:
                _LOGGER.error(f"Unsupported recognition engine: {self.config.recognition_engine}")
                return None
                
            return text
            
        except sr.UnknownValueError:
            _LOGGER.debug("Speech not recognized")
            return None
        except sr.RequestError as e:
            _LOGGER.error(f"Recognition error: {str(e)}")
            return None
            
    async def _process_command(self, text: str) -> Optional[Dict[str, Any]]:
        """Process recognized text into a command."""
        try:
            # Basic command processing
            command = {
                "text": text,
                "timestamp": datetime.now().isoformat(),
                "confidence": 0.8,  # Placeholder confidence
                "processed": False
            }
            
            # Store command in history
            self.command_history.append(command)
            
            # Update metrics
            self.metrics["commands_processed"] += 1
            
            return command
            
        except Exception as e:
            _LOGGER.error(f"Error processing command: {str(e)}")
            self.metrics["failed_commands"] += 1
            return None
            
    def cleanup(self):
        """Clean up resources."""
        # Reset thread limits to default
        self.threadpool_controller.reset()
        _LOGGER.info("Reset thread limits to default") 