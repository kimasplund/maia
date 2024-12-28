import logging
import logging.handlers
import json
import os
import sys
import time
import psutil
import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from functools import wraps

class StructuredLogger:
    """Custom logger that outputs structured JSON logs with extensive debugging capabilities."""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        
        # Set log level based on environment
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        self.logger.setLevel(getattr(logging, log_level))
        
        # Create logs directory if it doesn't exist
        os.makedirs("/data/logs", exist_ok=True)
        
        # Add rotating file handler for JSON logs
        json_handler = logging.handlers.RotatingFileHandler(
            filename="/data/logs/maia.json",
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5
        )
        json_handler.setFormatter(JsonFormatter())
        self.logger.addHandler(json_handler)
        
        # Add debug file handler
        debug_handler = logging.handlers.RotatingFileHandler(
            filename="/data/logs/maia.debug.log",
            maxBytes=50 * 1024 * 1024,  # 50MB
            backupCount=10
        )
        debug_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] - %(message)s'
        ))
        debug_handler.setLevel(logging.DEBUG)
        self.logger.addHandler(debug_handler)
        
        # Add console handler for development
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        self.logger.addHandler(console_handler)
        
        # Initialize request context
        self.request_id = None
    
    def set_request_id(self, request_id: Optional[str] = None):
        """Set request ID for the current context."""
        self.request_id = request_id or str(uuid.uuid4())
    
    def _get_system_metrics(self) -> Dict[str, Any]:
        """Get system metrics for debugging."""
        process = psutil.Process()
        return {
            "memory_usage": {
                "rss": process.memory_info().rss / 1024 / 1024,  # MB
                "vms": process.memory_info().vms / 1024 / 1024,  # MB
                "percent": process.memory_percent()
            },
            "cpu_percent": process.cpu_percent(),
            "thread_count": process.num_threads(),
            "open_files": len(process.open_files()),
            "connections": len(process.connections())
        }
    
    def _log(self, level: int, msg: str, **kwargs):
        """Internal logging method with additional context and metrics."""
        timestamp = datetime.utcnow()
        
        # Add system metrics for debug and error levels
        if level <= logging.DEBUG or level >= logging.ERROR:
            kwargs["system_metrics"] = self._get_system_metrics()
        
        extra = {
            "timestamp": timestamp.isoformat(),
            "request_id": self.request_id or "no_request",
            "process_id": os.getpid(),
            "thread_id": threading.get_ident(),
            "context": kwargs
        }
        
        # Add performance metrics if provided
        if "duration_ms" in kwargs:
            extra["performance"] = {
                "duration_ms": kwargs.pop("duration_ms")
            }
        
        # Add stack trace for debug level
        if level == logging.DEBUG:
            extra["stack_trace"] = traceback.format_stack()
        
        self.logger.log(level, msg, extra={"structured": extra})
    
    def debug(self, msg: str, **kwargs):
        """Log debug message with extensive system information."""
        self._log(logging.DEBUG, msg, **kwargs)
    
    def info(self, msg: str, **kwargs):
        """Log info message."""
        self._log(logging.INFO, msg, **kwargs)
    
    def warning(self, msg: str, **kwargs):
        """Log warning message."""
        self._log(logging.WARNING, msg, **kwargs)
    
    def error(self, msg: str, **kwargs):
        """Log error message with system metrics."""
        self._log(logging.ERROR, msg, **kwargs)
    
    def critical(self, msg: str, **kwargs):
        """Log critical message with full system state."""
        self._log(logging.CRITICAL, msg, **kwargs)
    
    def performance(self, operation: str):
        """Decorator to log function performance."""
        def decorator(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = await func(*args, **kwargs)
                    duration_ms = (time.time() - start_time) * 1000
                    self.debug(
                        f"Performance: {operation}",
                        operation=operation,
                        duration_ms=duration_ms,
                        status="success"
                    )
                    return result
                except Exception as e:
                    duration_ms = (time.time() - start_time) * 1000
                    self.error(
                        f"Performance: {operation} failed",
                        operation=operation,
                        duration_ms=duration_ms,
                        status="error",
                        error=str(e)
                    )
                    raise
            
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    duration_ms = (time.time() - start_time) * 1000
                    self.debug(
                        f"Performance: {operation}",
                        operation=operation,
                        duration_ms=duration_ms,
                        status="success"
                    )
                    return result
                except Exception as e:
                    duration_ms = (time.time() - start_time) * 1000
                    self.error(
                        f"Performance: {operation} failed",
                        operation=operation,
                        duration_ms=duration_ms,
                        status="error",
                        error=str(e)
                    )
                    raise
            
            return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
        return decorator

class JsonFormatter(logging.Formatter):
    """Formatter that outputs JSON strings with extensive context."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format the record as JSON with additional debugging information."""
        log_data: Dict[str, Any] = {
            "timestamp": getattr(record, "timestamp", datetime.utcnow().isoformat()),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line_number": record.lineno,
            "process_id": record.process,
            "thread_id": record.thread,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info)
            }
        
        # Add extra context if present
        if hasattr(record, "structured"):
            log_data.update(record.structured)
        
        return json.dumps(log_data)

def get_logger(name: str) -> StructuredLogger:
    """Get a structured logger instance with debugging capabilities."""
    return StructuredLogger(name)

# Add middleware for request tracking
def log_request_middleware(app: FastAPI):
    @app.middleware("http")
    async def log_request(request: Request, call_next):
        # Generate request ID
        request_id = str(uuid.uuid4())
        logger = get_logger("maia.request")
        logger.set_request_id(request_id)
        
        # Log request details
        logger.debug(
            "Request started",
            method=request.method,
            url=str(request.url),
            headers=dict(request.headers),
            client_host=request.client.host if request.client else None
        )
        
        start_time = time.time()
        try:
            response = await call_next(request)
            duration_ms = (time.time() - start_time) * 1000
            
            # Log response details
            logger.debug(
                "Request completed",
                method=request.method,
                url=str(request.url),
                status_code=response.status_code,
                duration_ms=duration_ms
            )
            
            return response
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                "Request failed",
                method=request.method,
                url=str(request.url),
                error=str(e),
                duration_ms=duration_ms,
                traceback=traceback.format_exc()
            )
            raise 