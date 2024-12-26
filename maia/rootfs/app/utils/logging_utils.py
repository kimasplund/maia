"""
Logging utilities for MAIA.
"""
import logging
import asyncio
from typing import Any, Dict, Optional
from datetime import datetime
import json
import os
import sys

class AsyncLogger:
    """Asynchronous logger with structured logging support."""
    
    def __init__(self, name: str, level: int = logging.INFO):
        """Initialize async logger."""
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        
        # Add console handler if none exists
        if not self.logger.handlers:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(
                logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                )
            )
            self.logger.addHandler(console_handler)
            
    async def log(
        self,
        level: int,
        message: str,
        extra: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log message asynchronously."""
        try:
            # Create structured log entry
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "message": message,
                "level": logging.getLevelName(level)
            }
            
            # Add extra fields
            if extra:
                log_entry.update(extra)
                
            # Convert to JSON string
            log_str = json.dumps(log_entry)
            
            # Log using appropriate level
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.logger.log(level, log_str)
            )
            
        except Exception as e:
            # Fallback to basic logging
            self.logger.error(f"Logging failed: {str(e)}")
            self.logger.log(level, message)
            
    async def debug(
        self,
        message: str,
        extra: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log debug message."""
        await self.log(logging.DEBUG, message, extra)
        
    async def info(
        self,
        message: str,
        extra: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log info message."""
        await self.log(logging.INFO, message, extra)
        
    async def warning(
        self,
        message: str,
        extra: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log warning message."""
        await self.log(logging.WARNING, message, extra)
        
    async def error(
        self,
        message: str,
        extra: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log error message."""
        await self.log(logging.ERROR, message, extra)
        
    async def critical(
        self,
        message: str,
        extra: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log critical message."""
        await self.log(logging.CRITICAL, message, extra)
        
    def set_level(self, level: int) -> None:
        """Set logger level."""
        self.logger.setLevel(level)
        
    def add_file_handler(
        self,
        filename: str,
        level: int = logging.INFO
    ) -> None:
        """Add file handler to logger."""
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            
            # Create file handler
            file_handler = logging.FileHandler(filename)
            file_handler.setLevel(level)
            
            # Set formatter
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(formatter)
            
            # Add handler to logger
            self.logger.addHandler(file_handler)
            
        except Exception as e:
            self.logger.error(f"Failed to add file handler: {str(e)}")
            
    def remove_handlers(self) -> None:
        """Remove all handlers from logger."""
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler) 