"""
Voice processing system for MAIA.
"""
import asyncio
import logging
import numpy as np
from typing import Dict, List, Optional, Any, Callable
import speech_recognition as sr
import pyttsx3
from transformers import pipeline
from ..database.storage import CommandStorage
from ..core.openai_integration import OpenAIIntegration
import aiohttp

class VoiceProcessor:
    """Voice processing system for speech recognition and synthesis."""
    
    def __init__(
        self,
        command_storage: CommandStorage,
        openai_integration: OpenAIIntegration,
        language: str = "en-US",
        confidence_threshold: float = 0.6
    ):
        """Initialize voice processor."""
        self.command_storage = command_storage
        self.openai_integration = openai_integration
        self.language = language
        self.confidence_threshold = confidence_threshold
        self.logger = logging.getLogger(__name__)
        
        # Initialize speech recognizer
        self.recognizer = sr.Recognizer()
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.energy_threshold = 4000
        
        # Initialize text-to-speech engine
        self.tts_engine = pyttsx3.init()
        self.tts_engine.setProperty("rate", 150)
        
        # Initialize NLU pipeline
        self.nlu_pipeline = None
        self._gpu_url = None
        self._gpu_session = None
        self._setup_nlu_pipeline()
        
        # Initialize command handlers
        self.command_handlers: Dict[str, Callable] = {}
        
    def _setup_nlu_pipeline(self):
        """Set up NLU pipeline."""
        if self._gpu_url:
            # Use remote GPU pipeline
            self.nlu_pipeline = None  # Will use companion service
        else:
            # Use local CPU pipeline
            self.nlu_pipeline = pipeline(
                "text-classification",
                model="distilbert-base-uncased",
                device=-1  # CPU
            )
        
    def enable_gpu(self, gpu_url: str):
        """Enable GPU processing using companion service."""
        self._gpu_url = gpu_url.rstrip('/')
        self._gpu_session = aiohttp.ClientSession()
        self._setup_nlu_pipeline()
        self.logger.info(f"Enabled GPU processing using companion at {gpu_url}")
        
    def disable_gpu(self):
        """Disable GPU processing."""
        if self._gpu_session:
            asyncio.create_task(self._gpu_session.close())
        self._gpu_url = None
        self._gpu_session = None
        self._setup_nlu_pipeline()
        self.logger.info("Disabled GPU processing")
        
    async def process_audio(self, audio_data: bytes) -> Dict[str, Any]:
        """Process audio data."""
        try:
            # Try GPU processing first
            if self._gpu_url and self._gpu_session:
                try:
                    result = await self._process_audio_gpu(audio_data)
                    if result:
                        return result
                except Exception as e:
                    self.logger.error(f"GPU processing failed, falling back to CPU: {str(e)}")
            
            # Fall back to CPU processing
            return await self._process_audio_cpu(audio_data)
            
        except Exception as e:
            self.logger.error(f"Audio processing failed: {str(e)}")
            return {"error": str(e)}
            
    async def _process_audio_gpu(self, audio_data: bytes) -> Optional[Dict[str, Any]]:
        """Process audio using GPU companion service."""
        try:
            # Send to companion service
            data = aiohttp.FormData()
            data.add_field('audio', audio_data,
                          filename='audio.wav',
                          content_type='audio/wav')
            data.add_field('language', self.language)
            
            async with self._gpu_session.post(
                f"{self._gpu_url}/process_audio",
                data=data
            ) as response:
                if response.status == 200:
                    return await response.json()
                return None
                
        except Exception as e:
            self.logger.error(f"GPU audio processing failed: {str(e)}")
            return None
            
    async def _process_audio_cpu(self, audio_data: bytes) -> Dict[str, Any]:
        """Process audio using CPU."""
        try:
            # Convert audio data to AudioData
            audio = sr.AudioData(audio_data, 16000, 2)
            
            # Perform speech recognition
            text = self.recognizer.recognize_google(
                audio,
                language=self.language
            )
            
            # Perform NLU if pipeline is available
            intent = None
            if self.nlu_pipeline:
                result = self.nlu_pipeline(text)
                if result[0]["score"] >= self.confidence_threshold:
                    intent = result[0]["label"]
            
            return {
                "text": text,
                "intent": intent,
                "confidence": result[0]["score"] if intent else 0.0
            }
            
        except sr.UnknownValueError:
            return {"error": "Speech not recognized"}
        except sr.RequestError as e:
            return {"error": f"Recognition service error: {str(e)}"}
        except Exception as e:
            return {"error": str(e)}
        
    def register_command_handler(
        self,
        command: str,
        handler: Callable[[Dict[str, Any]], None]
    ) -> None:
        """Register a handler for a specific command."""
        self.command_handlers[command] = handler
        
    async def synthesize_speech(
        self,
        text: str,
        voice: Optional[str] = None,
        rate: Optional[int] = None,
        volume: Optional[float] = None
    ) -> Optional[np.ndarray]:
        """Synthesize speech from text."""
        try:
            # Configure TTS properties
            if voice:
                self.tts_engine.setProperty("voice", voice)
            if rate:
                self.tts_engine.setProperty("rate", rate)
            if volume:
                self.tts_engine.setProperty("volume", volume)
                
            # Create a buffer to store audio data
            audio_buffer = []
            
            def callback(data):
                audio_buffer.append(data)
                
            # Set up callback
            self.tts_engine.connect("data", callback)
            
            # Synthesize speech
            self.tts_engine.say(text)
            self.tts_engine.runAndWait()
            
            # Convert buffer to numpy array
            if audio_buffer:
                audio_data = np.frombuffer(b"".join(audio_buffer), dtype=np.int16)
                return audio_data
                
            return None
            
        except Exception as e:
            self.logger.error(f"Error synthesizing speech: {str(e)}")
            return None
            
    async def start_listening(
        self,
        callback: Callable[[Dict[str, Any]], None],
        device_index: Optional[int] = None
    ) -> None:
        """Start listening for voice commands in background."""
        try:
            # Initialize microphone
            with sr.Microphone(device_index=device_index) as source:
                self.recognizer.adjust_for_ambient_noise(source)
                
                while True:
                    try:
                        # Listen for audio
                        audio = self.recognizer.listen(source)
                        
                        # Convert to numpy array
                        audio_data = np.frombuffer(
                            audio.get_raw_data(),
                            dtype=np.int16
                        )
                        
                        # Process audio
                        result = await self.process_audio(
                            audio_data,
                            sample_rate=audio.sample_rate
                        )
                        
                        if result:
                            # Call callback with result
                            callback(result)
                            
                    except sr.WaitTimeoutError:
                        continue
                        
                    except Exception as e:
                        self.logger.error(f"Error in listening loop: {str(e)}")
                        await asyncio.sleep(1)
                        
        except Exception as e:
            self.logger.error(f"Error starting voice listener: {str(e)}")
            
    async def get_command_history(
        self,
        limit: int = 100,
        intent: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get command history from storage."""
        try:
            commands = await self.command_storage.get_commands(
                limit=limit,
                intent=intent
            )
            return commands
            
        except Exception as e:
            self.logger.error(f"Error getting command history: {str(e)}")
            return [] 