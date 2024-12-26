"""
OpenAI integration module for MAIA.
Handles enhanced voice processing and natural language understanding.
"""
import os
import json
import logging
import httpx
import tiktoken
from typing import Dict, List, Optional, Any, TypedDict
from datetime import datetime
from openai import OpenAI, AsyncOpenAI
from tiktoken.core import Encoding

_LOGGER = logging.getLogger(__name__)

# Token limits for different models
MODEL_TOKEN_LIMITS = {
    "gpt-4": 8192,
    "gpt-4-32k": 32768,
    "gpt-3.5-turbo": 4096,
    "gpt-3.5-turbo-16k": 16384
}

DEFAULT_ENCODING = "cl100k_base"

class TokenInfo(TypedDict):
    """Token information."""
    token: str
    offset: int
    length: int
    special: bool

class OpenAIConfig(TypedDict):
    """OpenAI configuration."""
    model: str
    temperature: float
    max_tokens: int
    max_history: int
    response_format: str
    timeout: float
    max_context_tokens: Optional[int]
    debug_tokens: bool
    max_cache_size: int

class OpenAIIntegration:
    """OpenAI integration for enhanced voice processing."""
    
    DEFAULT_CONFIG: OpenAIConfig = {
        "model": "gpt-4",
        "temperature": 0.7,
        "max_tokens": 150,
        "max_history": 10,
        "response_format": "json",
        "timeout": 30.0,
        "max_context_tokens": None,  # Will be set based on model
        "debug_tokens": False,  # Enable token debugging
        "max_cache_size": 1000  # Maximum number of cached items
    }
    
    def __init__(self, config: Optional[OpenAIConfig] = None):
        """Initialize OpenAI integration."""
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}
        
        # Set max context tokens based on model if not specified
        if not self.config["max_context_tokens"]:
            self.config["max_context_tokens"] = MODEL_TOKEN_LIMITS.get(
                self.config["model"], 
                4096  # Default fallback
            )
        
        # Initialize tokenizer
        self.tokenizer = self._initialize_tokenizer()
        
        # Initialize both sync and async clients
        self.client = OpenAI(
            api_key=self.config.get('api_key', os.getenv("OPENAI_API_KEY")),
            timeout=httpx.Timeout(self.config["timeout"])
        )
        self.async_client = AsyncOpenAI(
            api_key=self.config.get('api_key', os.getenv("OPENAI_API_KEY")),
            timeout=httpx.Timeout(self.config["timeout"])
        )
        
        # Command history for context
        self.command_history: List[Dict[str, Any]] = []
        
        # Caches for various token analyses
        self._token_cache: Dict[str, List[TokenInfo]] = {}
        self._count_cache: Dict[str, int] = {}
        self._stats_cache: Dict[str, Dict[str, Any]] = {}
        self._message_count_cache: Dict[str, Dict[str, int]] = {}

    def _initialize_tokenizer(self) -> Encoding:
        """Initialize the tokenizer for the configured model."""
        try:
            return tiktoken.encoding_for_model(self.config["model"])
        except KeyError:
            return tiktoken.get_encoding(DEFAULT_ENCODING)

    def _cache_key_for_messages(self, messages: List[Dict[str, Any]]) -> str:
        """Generate a cache key for a list of messages."""
        return json.dumps([{k: v for k, v in m.items() if k != "content"} for m in messages])

    def _manage_cache_size(self):
        """Manage cache size to prevent memory issues."""
        for cache in [self._token_cache, self._count_cache, self._stats_cache, self._message_count_cache]:
            if len(cache) > self.config["max_cache_size"]:
                # Remove oldest entries (first 10%)
                num_to_remove = len(cache) // 10
                for _ in range(num_to_remove):
                    cache.pop(next(iter(cache)))

    def count_tokens(self, text: str) -> int:
        """Count tokens in a text string with caching."""
        if text in self._count_cache:
            return self._count_cache[text]
        
        tokens = self.tokenizer.encode(text)
        count = len(tokens)
        self._count_cache[text] = count
        self._manage_cache_size()
        return count

    async def process_command(self, command: str) -> Dict[str, Any]:
        """Process a voice command using OpenAI."""
        try:
            # Prepare messages with context
            messages = self._prepare_messages(command)
            
            # Get completion from OpenAI
            response = await self.async_client.chat.completions.create(
                model=self.config["model"],
                messages=messages,
                temperature=self.config["temperature"],
                max_tokens=self.config["max_tokens"],
                response_format={"type": self.config["response_format"]}
            )
            
            # Process response
            result = self._process_response(response)
            
            # Update command history
            self._update_history(command, result)
            
            return result
            
        except Exception as e:
            _LOGGER.error(f"OpenAI command processing failed: {str(e)}")
            return {
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    def _prepare_messages(self, command: str) -> List[Dict[str, str]]:
        """Prepare messages for OpenAI API with context."""
        messages = [{"role": "system", "content": self._get_system_prompt()}]
        
        # Add relevant history
        for hist in self.command_history[-self.config["max_history"]:]:
            messages.append({"role": "user", "content": hist["command"]})
            if "response" in hist:
                messages.append({"role": "assistant", "content": hist["response"]})
                
        # Add current command
        messages.append({"role": "user", "content": command})
        
        return messages

    def _get_system_prompt(self) -> str:
        """Get system prompt for OpenAI."""
        return """You are MAIA (My AI Assistant), a helpful voice assistant for Home Assistant.
        Process user commands naturally and return structured responses.
        Focus on home automation tasks and provide clear, concise responses."""

    def _process_response(self, response: Any) -> Dict[str, Any]:
        """Process OpenAI API response."""
        try:
            content = response.choices[0].message.content
            
            # Parse JSON if response format is json
            if self.config["response_format"] == "json":
                content = json.loads(content)
                
            return {
                "content": content,
                "tokens": {
                    "prompt": response.usage.prompt_tokens,
                    "completion": response.usage.completion_tokens,
                    "total": response.usage.total_tokens
                },
                "model": response.model,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            _LOGGER.error(f"Failed to process OpenAI response: {str(e)}")
            return {
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    def _update_history(self, command: str, result: Dict[str, Any]) -> None:
        """Update command history."""
        self.command_history.append({
            "command": command,
            "response": result.get("content"),
            "timestamp": result.get("timestamp")
        })
        
        # Trim history if needed
        while len(self.command_history) > self.config["max_history"]:
            self.command_history.pop(0)

    def cleanup(self):
        """Clean up resources."""
        # Clear caches
        self._token_cache.clear()
        self._count_cache.clear()
        self._stats_cache.clear()
        self._message_count_cache.clear()
        
        # Clear command history
        self.command_history.clear() 