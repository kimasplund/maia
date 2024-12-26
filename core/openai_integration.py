"""OpenAI integration for MAIA voice processing."""
from typing import Dict, Optional, List, Any, TypedDict, Literal, Tuple, Set
import logging
import os
from pathlib import Path
import json
import httpx
import tiktoken
from tiktoken.core import Encoding
from openai import OpenAI, AsyncOpenAI
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionMessage,
    ChatCompletionMessageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam
)
from openai.types.audio import Transcription
from openai._types import NotGiven, FileTypes

_LOGGER = logging.getLogger(__name__)

# Token limits for different models
MODEL_TOKEN_LIMITS = {
    "gpt-4": 8192,
    "gpt-4-32k": 32768,
    "gpt-3.5-turbo": 4096,
    "gpt-3.5-turbo-16k": 16384
}

# Default encoding for unknown models
DEFAULT_ENCODING = "cl100k_base"

class TokenInfo(TypedDict):
    """Type definition for token information."""
    token_id: int
    token_bytes: bytes
    token_text: str
    token_role: str

class CommandResponse(TypedDict):
    """Type definition for command response."""
    text: str
    confidence: float
    requires_confirmation: bool
    intent: Optional[str]
    entities: Optional[Dict[str, Any]]
    actions: Optional[List[Dict[str, Any]]]
    tokens_used: int
    token_breakdown: Optional[Dict[str, int]]

class OpenAIConfig(TypedDict, total=False):
    """Configuration for OpenAI integration."""
    model: str
    temperature: float
    max_tokens: int
    max_history: int
    response_format: Literal["json", "text"]
    timeout: float
    max_context_tokens: Optional[int]
    debug_tokens: bool
    max_cache_size: int
    api_key: Optional[str]

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

    def count_message_tokens(self, messages: List[Dict[str, Any]]) -> Dict[str, int]:
        """Count tokens in a list of messages with caching."""
        cache_key = self._cache_key_for_messages(messages)
        if cache_key in self._message_count_cache:
            return self._message_count_cache[cache_key]
        
        counts = {
            "total": 0,
            "per_message": [],
            "system": 0,
            "user": 0,
            "assistant": 0
        }
        
        for message in messages:
            message_tokens = self.count_tokens(message.get("content", ""))
            role_tokens = self.count_tokens(message.get("role", "user"))
            total_message_tokens = message_tokens + role_tokens
            
            counts["total"] += total_message_tokens
            counts["per_message"].append(total_message_tokens)
            counts[message.get("role", "user")] += total_message_tokens
        
        self._message_count_cache[cache_key] = counts
        self._manage_cache_size()
        return counts

    def clear_caches(self):
        """Clear all token analysis caches."""
        self._token_cache.clear()
        self._count_cache.clear()
        self._stats_cache.clear()
        self._message_count_cache.clear()

    async def transcribe_audio(self, audio_file: FileTypes) -> Optional[str]:
        """Transcribe audio using OpenAI's Whisper API."""
        try:
            transcription: Transcription = await self.async_client.audio.transcriptions.create(
                file=audio_file,
                model="whisper-1",
                response_format="text"
            )
            return transcription.text
        except Exception as e:
            _LOGGER.error(f"Audio transcription failed: {str(e)}")
            return None

    async def analyze_command(self, command: str, context: Optional[List[Dict[str, Any]]] = None) -> CommandResponse:
        """Analyze a voice command using the OpenAI API."""
        try:
            messages: List[ChatCompletionMessageParam] = [
                {
                    "role": "system",
                    "content": "You are a home automation assistant. Analyze the user's command and provide structured response."
                },
                {
                    "role": "user",
                    "content": command
                }
            ]

            if context:
                # Add context but check token limits
                context_tokens = self.count_message_tokens(context)
                if context_tokens["total"] < self.config["max_context_tokens"]:
                    messages.extend([{"role": "assistant", "content": c["response"]} for c in context])

            # Count tokens and trim history if needed
            message_tokens = self.count_message_tokens(messages)
            while message_tokens["total"] > self.config["max_context_tokens"]:
                if len(messages) <= 2:  # Keep system and current user message
                    break
                messages.pop(1)  # Remove oldest message after system
                message_tokens = self.count_message_tokens(messages)

            response: ChatCompletion = await self.async_client.chat.completions.create(
                model=self.config["model"],
                messages=messages,
                temperature=self.config["temperature"],
                max_tokens=self.config["max_tokens"],
                response_format={"type": self.config["response_format"]}
            )

            result = response.choices[0].message.content
            if self.config["response_format"] == "json":
                result = json.loads(result)

            return CommandResponse(
                text=result.get("text", ""),
                confidence=result.get("confidence", 0.0),
                requires_confirmation=result.get("requires_confirmation", False),
                intent=result.get("intent"),
                entities=result.get("entities"),
                actions=result.get("actions"),
                tokens_used=response.usage.total_tokens,
                token_breakdown={
                    "prompt": response.usage.prompt_tokens,
                    "completion": response.usage.completion_tokens,
                    "total": response.usage.total_tokens
                }
            )

        except Exception as e:
            _LOGGER.error(f"Command analysis failed: {str(e)}")
            return CommandResponse(
                text="Error analyzing command",
                confidence=0.0,
                requires_confirmation=True,
                intent=None,
                entities=None,
                actions=None,
                tokens_used=0,
                token_breakdown=None
            )

    async def generate_response(self, command_response: CommandResponse) -> str:
        """Generate a natural language response based on command analysis."""
        try:
            messages: List[ChatCompletionMessageParam] = [
                {
                    "role": "system",
                    "content": "Generate a natural language response for the home automation command result."
                },
                {
                    "role": "user",
                    "content": json.dumps(command_response)
                }
            ]

            response: ChatCompletion = await self.async_client.chat.completions.create(
                model=self.config["model"],
                messages=messages,
                temperature=0.7,
                max_tokens=100,
                response_format={"type": "text"}
            )

            return response.choices[0].message.content

        except Exception as e:
            _LOGGER.error(f"Response generation failed: {str(e)}")
            return "I'm sorry, I couldn't process that command properly." 