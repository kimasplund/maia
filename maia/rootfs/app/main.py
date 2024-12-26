"""
MAIA - My AI Assistant
Main application entry point.
"""
import os
import sys
import logging
import asyncio
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import app as api_app
from web.app import app as web_app
from core.config import ConfigManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('maia.log')
    ]
)

_LOGGER = logging.getLogger(__name__)

# Create main application
app = FastAPI(
    title="MAIA",
    description="My AI Assistant for Home Assistant",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Mount API and web applications
app.mount("/api", api_app)
app.mount("/", web_app)

def main():
    """Main entry point."""
    try:
        # Load configuration
        config_path = os.environ.get("MAIA_CONFIG", "config.yaml")
        config = ConfigManager(config_path)
        
        # Start application
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=8000,
            reload=False,
            workers=1
        )
        
    except Exception as e:
        _LOGGER.error(f"Failed to start MAIA: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 