"""
Audio processing utilities for MAIA.
Handles audio preprocessing, noise reduction, and feature extraction.
"""
import numpy as np
from typing import Optional, Tuple, Dict
import logging
from scipy import signal
import soundfile as sf
import librosa

_LOGGER = logging.getLogger(__name__)

class AudioPreprocessor:
    def __init__(self):
        # Audio processing parameters
        self.sample_rate = 16000
        self.frame_length = 512
        self.hop_length = 128
        self.n_mels = 40
        
        # Noise reduction parameters
        self.noise_reduce_strength = 0.15
        self.noise_threshold = 0.1

    async def process_stream(self, audio_stream,
                           duration: Optional[float] = None) -> Optional[np.ndarray]:
        """
        Process an audio stream for voice recognition.
        
        Args:
            audio_stream: Input audio stream
            duration: Optional duration to process in seconds
            
        Returns:
            Processed audio as numpy array or None if failed
        """
        try:
            # Read audio data
            audio_data = await self._read_stream(audio_stream, duration)
            if audio_data is None:
                return None
                
            # Preprocess audio
            processed_audio = self._preprocess_audio(audio_data)
            
            return processed_audio
            
        except Exception as e:
            _LOGGER.error(f"Error processing audio stream: {str(e)}")
            return None

    def reduce_noise(self, audio_data: np.ndarray) -> np.ndarray:
        """
        Apply noise reduction to audio data.
        
        Args:
            audio_data: Input audio data
            
        Returns:
            Noise-reduced audio data
        """
        try:
            # Estimate noise profile
            noise_profile = self._estimate_noise_profile(audio_data)
            
            # Apply spectral subtraction
            denoised = self._spectral_subtraction(
                audio_data,
                noise_profile
            )
            
            return denoised
            
        except Exception as e:
            _LOGGER.error(f"Error reducing noise: {str(e)}")
            return audio_data

    def extract_features(self, audio_data: np.ndarray) -> Dict[str, np.ndarray]:
        """
        Extract audio features for voice processing.
        
        Args:
            audio_data: Input audio data
            
        Returns:
            Dictionary of extracted features
        """
        try:
            # Extract mel spectrogram
            mel_spec = librosa.feature.melspectrogram(
                y=audio_data,
                sr=self.sample_rate,
                n_mels=self.n_mels,
                hop_length=self.hop_length
            )
            
            # Extract MFCC
            mfcc = librosa.feature.mfcc(
                y=audio_data,
                sr=self.sample_rate,
                n_mfcc=13,
                hop_length=self.hop_length
            )
            
            # Extract pitch
            pitches, magnitudes = librosa.piptrack(
                y=audio_data,
                sr=self.sample_rate,
                hop_length=self.hop_length
            )
            
            return {
                'mel_spectrogram': mel_spec,
                'mfcc': mfcc,
                'pitch': pitches,
                'magnitude': magnitudes
            }
            
        except Exception as e:
            _LOGGER.error(f"Error extracting features: {str(e)}")
            return {}

    async def _read_stream(self, audio_stream,
                          duration: Optional[float] = None) -> Optional[np.ndarray]:
        """Read audio data from stream."""
        try:
            if duration:
                num_samples = int(duration * self.sample_rate)
                audio_data = np.frombuffer(
                    await audio_stream.read(num_samples),
                    dtype=np.float32
                )
            else:
                audio_data = np.frombuffer(
                    await audio_stream.read(),
                    dtype=np.float32
                )
                
            return audio_data
            
        except Exception as e:
            _LOGGER.error(f"Error reading audio stream: {str(e)}")
            return None

    def _preprocess_audio(self, audio_data: np.ndarray) -> np.ndarray:
        """Apply preprocessing steps to audio data."""
        # Normalize
        audio_data = audio_data / np.max(np.abs(audio_data))
        
        # Apply pre-emphasis
        pre_emphasis = 0.97
        emphasized = np.append(
            audio_data[0],
            audio_data[1:] - pre_emphasis * audio_data[:-1]
        )
        
        return emphasized

    def _estimate_noise_profile(self, audio_data: np.ndarray) -> np.ndarray:
        """Estimate noise profile from audio data."""
        # Use first 100ms as noise profile
        noise_samples = int(0.1 * self.sample_rate)
        noise_profile = audio_data[:noise_samples]
        
        return np.mean(np.abs(noise_profile))

    def _spectral_subtraction(self, audio_data: np.ndarray,
                            noise_profile: float) -> np.ndarray:
        """Apply spectral subtraction for noise reduction."""
        # Compute STFT
        stft = librosa.stft(
            audio_data,
            n_fft=self.frame_length,
            hop_length=self.hop_length
        )
        
        # Compute magnitude and phase
        magnitude = np.abs(stft)
        phase = np.angle(stft)
        
        # Apply spectral subtraction
        magnitude_db = librosa.amplitude_to_db(magnitude)
        noise_db = librosa.amplitude_to_db(noise_profile)
        
        mask = (magnitude_db - noise_db) > self.noise_threshold
        magnitude_db = np.maximum(
            magnitude_db - noise_db * self.noise_reduce_strength,
            noise_db
        )
        magnitude_db = magnitude_db * mask
        
        # Reconstruct signal
        magnitude = librosa.db_to_amplitude(magnitude_db)
        stft_denoised = magnitude * np.exp(1j * phase)
        
        return librosa.istft(
            stft_denoised,
            hop_length=self.hop_length
        ) 