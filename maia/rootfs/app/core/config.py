"""Configuration management for MAIA."""
from dataclasses import dataclass
from typing import Dict, Optional, List
import voluptuous as vol
import yaml
import logging

_LOGGER = logging.getLogger(__name__)

@dataclass
class TTSConfig:
    """TTS configuration settings."""
    engine: str = "pyttsx3"
    default_voice: Optional[str] = None
    default_rate: int = 150
    default_volume: float = 0.9
    custom_pronunciations: Dict[str, str] = None
    save_directory: str = "tts_cache"
    async_mode: bool = False

    @classmethod
    def from_dict(cls, config: Dict) -> 'TTSConfig':
        """Create config from dictionary."""
        return cls(
            engine=config.get('engine', cls.engine),
            default_voice=config.get('default_voice', cls.default_voice),
            default_rate=config.get('default_rate', cls.default_rate),
            default_volume=config.get('default_volume', cls.default_volume),
            custom_pronunciations=config.get('custom_pronunciations', {}),
            save_directory=config.get('save_directory', cls.save_directory),
            async_mode=config.get('async_mode', cls.async_mode)
        )

@dataclass
class VoiceProcessingConfig:
    """Voice processing configuration."""
    vad_enabled: bool = True
    vad_sensitivity: int = 3
    noise_update_interval: int = 300
    offline_mode: bool = False
    preferred_engine: str = "google"
    fallback_engines: List[str] = None
    
    @classmethod
    def from_dict(cls, config: Dict) -> 'VoiceProcessingConfig':
        """Create config from dictionary."""
        return cls(
            vad_enabled=config.get('vad_enabled', cls.vad_enabled),
            vad_sensitivity=config.get('vad_sensitivity', cls.vad_sensitivity),
            noise_update_interval=config.get('noise_update_interval', cls.noise_update_interval),
            offline_mode=config.get('offline_mode', cls.offline_mode),
            preferred_engine=config.get('preferred_engine', cls.preferred_engine),
            fallback_engines=config.get('fallback_engines', ["sphinx", "vosk"])
        )

class ConfigManager:
    """Configuration manager for MAIA."""
    
    CONFIG_SCHEMA = vol.Schema({
        vol.Optional('tts'): {
            vol.Optional('engine'): str,
            vol.Optional('default_voice'): vol.Any(str, None),
            vol.Optional('default_rate'): int,
            vol.Optional('default_volume'): vol.All(float, vol.Range(min=0, max=1)),
            vol.Optional('custom_pronunciations'): {str: str},
            vol.Optional('save_directory'): str,
            vol.Optional('async_mode'): bool
        },
        vol.Optional('voice_processing'): {
            vol.Optional('vad_enabled'): bool,
            vol.Optional('vad_sensitivity'): vol.All(int, vol.Range(min=1, max=10)),
            vol.Optional('noise_update_interval'): int,
            vol.Optional('offline_mode'): bool,
            vol.Optional('preferred_engine'): str,
            vol.Optional('fallback_engines'): [str]
        }
    })

    def __init__(self, config_path: Optional[str] = None):
        """Initialize configuration manager."""
        self.config_path = config_path
        self.config = {}
        self.tts_config = TTSConfig()
        self.voice_config = VoiceProcessingConfig()
        
        if config_path:
            self.load_config()

    def load_config(self) -> None:
        """Load configuration from file."""
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            # Validate config
            config = self.CONFIG_SCHEMA(config)
            
            # Update configurations
            if 'tts' in config:
                self.tts_config = TTSConfig.from_dict(config['tts'])
            if 'voice_processing' in config:
                self.voice_config = VoiceProcessingConfig.from_dict(config['voice_processing'])
                
            self.config = config
            
        except Exception as e:
            _LOGGER.error("Failed to load configuration: %s", str(e))
            raise

    def save_config(self) -> None:
        """Save current configuration to file."""
        if not self.config_path:
            raise ValueError("No config path specified")
            
        try:
            config = {
                'tts': {
                    'engine': self.tts_config.engine,
                    'default_voice': self.tts_config.default_voice,
                    'default_rate': self.tts_config.default_rate,
                    'default_volume': self.tts_config.default_volume,
                    'custom_pronunciations': self.tts_config.custom_pronunciations,
                    'save_directory': self.tts_config.save_directory,
                    'async_mode': self.tts_config.async_mode
                },
                'voice_processing': {
                    'vad_enabled': self.voice_config.vad_enabled,
                    'vad_sensitivity': self.voice_config.vad_sensitivity,
                    'noise_update_interval': self.voice_config.noise_update_interval,
                    'offline_mode': self.voice_config.offline_mode,
                    'preferred_engine': self.voice_config.preferred_engine,
                    'fallback_engines': self.voice_config.fallback_engines
                }
            }
            
            with open(self.config_path, 'w') as f:
                yaml.safe_dump(config, f)
                
        except Exception as e:
            _LOGGER.error("Failed to save configuration: %s", str(e))
            raise 