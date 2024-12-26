"""
Audio processing utilities for MAIA.
"""
import numpy as np
import soundfile as sf
import librosa
from typing import Optional, Tuple
import asyncio
import logging

_LOGGER = logging.getLogger(__name__)

class AudioPreprocessor:
    """Audio preprocessing utilities."""
    
    def __init__(self):
        """Initialize audio preprocessor."""
        self.sample_rate = 16000  # Default sample rate
        self.frame_length = 512   # Frame length for processing
        self.hop_length = 128     # Hop length between frames
        
    async def preprocess(
        self,
        audio_data: bytes,
        enable_noise_reduction: bool = True
    ) -> np.ndarray:
        """Preprocess audio data."""
        try:
            # Convert bytes to numpy array
            audio = np.frombuffer(audio_data, dtype=np.int16)
            audio = audio.astype(np.float32) / 32768.0  # Normalize to [-1, 1]
            
            # Apply preprocessing steps
            if enable_noise_reduction:
                audio = await self._reduce_noise(audio)
                
            # Apply additional preprocessing
            audio = await self._apply_preprocessing(audio)
            
            return audio
            
        except Exception as e:
            _LOGGER.error(f"Audio preprocessing failed: {str(e)}")
            return np.array([])
            
    async def _reduce_noise(self, audio: np.ndarray) -> np.ndarray:
        """Apply noise reduction to audio signal."""
        try:
            # Estimate noise profile from non-speech segments
            noise_profile = librosa.effects.trim(
                audio,
                top_db=20,
                frame_length=self.frame_length,
                hop_length=self.hop_length
            )[1]
            
            if len(noise_profile) > 0:
                # Compute noise reduction filter
                noise_stft = librosa.stft(
                    noise_profile,
                    n_fft=self.frame_length,
                    hop_length=self.hop_length
                )
                noise_spec = np.mean(np.abs(noise_stft), axis=1)
                
                # Apply noise reduction
                audio_stft = librosa.stft(
                    audio,
                    n_fft=self.frame_length,
                    hop_length=self.hop_length
                )
                audio_spec = np.abs(audio_stft)
                
                # Wiener filter
                gain = (audio_spec ** 2) / (audio_spec ** 2 + noise_spec[:, np.newaxis] ** 2)
                audio_stft_denoised = audio_stft * gain
                
                # Inverse STFT
                audio = librosa.istft(
                    audio_stft_denoised,
                    hop_length=self.hop_length,
                    length=len(audio)
                )
                
            return audio
            
        except Exception as e:
            _LOGGER.error(f"Noise reduction failed: {str(e)}")
            return audio
            
    async def _apply_preprocessing(self, audio: np.ndarray) -> np.ndarray:
        """Apply additional preprocessing steps."""
        try:
            # Apply pre-emphasis filter
            audio = librosa.effects.preemphasis(audio)
            
            # Normalize audio level
            audio = librosa.util.normalize(audio)
            
            # Remove DC offset
            audio = audio - np.mean(audio)
            
            return audio
            
        except Exception as e:
            _LOGGER.error(f"Additional preprocessing failed: {str(e)}")
            return audio
            
    def save_audio(
        self,
        audio: np.ndarray,
        filename: str,
        sample_rate: Optional[int] = None
    ) -> bool:
        """Save audio data to file."""
        try:
            if sample_rate is None:
                sample_rate = self.sample_rate
                
            # Convert to int16
            audio = np.int16(audio * 32768.0)
            
            # Save to file
            sf.write(filename, audio, sample_rate)
            return True
            
        except Exception as e:
            _LOGGER.error(f"Failed to save audio: {str(e)}")
            return False
            
    def load_audio(
        self,
        filename: str
    ) -> Tuple[Optional[np.ndarray], Optional[int]]:
        """Load audio data from file."""
        try:
            # Load audio file
            audio, sample_rate = sf.read(filename)
            
            # Convert to float32 and normalize
            audio = audio.astype(np.float32)
            if audio.max() > 1.0:
                audio = audio / 32768.0
                
            return audio, sample_rate
            
        except Exception as e:
            _LOGGER.error(f"Failed to load audio: {str(e)}")
            return None, None 