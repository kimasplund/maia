"""
Voice processing tools for MAIA.
"""
from typing import Dict, List, Optional, Any
import logging
from ..core.openai_integration import OpenAIIntegration
from ..database.storage import CommandStorage

_LOGGER = logging.getLogger(__name__)

class VoiceTools:
    """Voice processing tools."""
    
    def __init__(self, openai: OpenAIIntegration, storage: CommandStorage):
        """Initialize voice tools."""
        self.openai = openai
        self.storage = storage
        
    async def process_command(self, text: str) -> Dict[str, Any]:
        """Process voice command using OpenAI."""
        try:
            # Process with OpenAI
            result = await self.openai.process_command(text)
            
            # Store command
            await self.storage.store_command({
                "text": text,
                "result": result,
                "type": "voice_command"
            })
            
            return result
            
        except Exception as e:
            _LOGGER.error(f"Failed to process voice command: {str(e)}")
            return {
                "error": str(e),
                "original_text": text
            }
            
    async def get_command_history(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get command history."""
        try:
            return await self.storage.get_recent_commands(limit, offset)
        except Exception as e:
            _LOGGER.error(f"Failed to get command history: {str(e)}")
            return []
            
    async def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """Analyze sentiment of voice command."""
        try:
            # Use OpenAI for sentiment analysis
            result = await self.openai.process_command(
                f"Analyze the sentiment of this text: {text}"
            )
            return result
        except Exception as e:
            _LOGGER.error(f"Failed to analyze sentiment: {str(e)}")
            return {
                "error": str(e),
                "original_text": text
            }
            
    async def generate_response(self, text: str) -> str:
        """Generate natural language response."""
        try:
            result = await self.openai.process_command(
                f"Generate a natural response to: {text}"
            )
            return result.get("content", "I'm sorry, I couldn't generate a response.")
        except Exception as e:
            _LOGGER.error(f"Failed to generate response: {str(e)}")
            return "I apologize, but I encountered an error generating a response." 