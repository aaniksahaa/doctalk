#!/usr/bin/env python3
"""
LLM Service Abstraction Layer

Provides a clean interface for LLM inference across different providers.
Currently supports: Ollama, Google Gemini
Future: OpenAI, Anthropic, etc.
"""

import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from enum import Enum
from pathlib import Path

from dotenv import load_dotenv
from ollama import chat as ollama_chat
from google import genai
from google.genai import types as genai_types

# Load .env from project root (one level up from src/)
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)


class Provider(str, Enum):
    """Supported LLM providers."""
    OLLAMA = "ollama"
    OPENAI = "openai"  
    ANTHROPIC = "anthropic"
    GOOGLE = "google"


@dataclass
class LLMOptions:
    """Configuration options for LLM inference."""
    num_ctx: int = 32768  # Context window size
    num_predict: int = 16384  # Max tokens to generate
    temperature: float = 0.1
    top_p: float = 0.9
    repeat_penalty: float = 1.1
    
    def to_ollama_options(self) -> Dict[str, Any]:
        """Convert to Ollama-compatible options dict."""
        return {
            "num_ctx": self.num_ctx,
            "num_predict": self.num_predict,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "repeat_penalty": self.repeat_penalty,
        }


@dataclass
class InferenceMetadata:
    """Metadata from an LLM inference call."""
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    inference_time_seconds: float
    cost_usd: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "provider": self.provider,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "inference_time_seconds": round(self.inference_time_seconds, 3),
            "cost_usd": self.cost_usd,
        }


@dataclass
class LLMResponse:
    """Response from an LLM inference call."""
    content: str
    metadata: InferenceMetadata
    raw_response: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "content": self.content,
            "metadata": self.metadata.to_dict(),
        }


# Default options instance
DEFAULT_OPTIONS = LLMOptions()

# Default keep_alive duration
DEFAULT_KEEP_ALIVE = "5m"


def get_response(
    prompt: str,
    model: str,
    provider: Union[Provider, str] = None,
    system_prompt: Optional[str] = None,
    options: Optional[LLMOptions] = None,
    keep_alive: str = DEFAULT_KEEP_ALIVE,
    format_schema: Optional[Dict[str, Any]] = None,
) -> LLMResponse:
    """
    Get a response from an LLM.
    
    Args:
        prompt: The user prompt/query
        model: Model name (e.g., "qwen2.5:3b-instruct" or "gemini-3-flash-preview")
        provider: LLM provider (auto-detected from model name if not specified)
        system_prompt: Optional system prompt
        options: LLM options (uses defaults if not provided)
        keep_alive: How long to keep model loaded (default: "5m", Ollama only)
        format_schema: Optional JSON schema for structured output (Ollama only)
    
    Returns:
        LLMResponse containing content and metadata
    
    Example:
        >>> response = get_response(
        ...     prompt="What is Python?",
        ...     model="qwen2.5:3b-instruct"
        ... )
        >>> print(response.content)
        >>> print(response.metadata.inference_time_seconds)
    """
    # Auto-detect provider from model name if not specified
    if provider is None:
        if model.lower().startswith("gemini"):
            provider = Provider.GOOGLE
        else:
            provider = Provider.OLLAMA
    
    # Normalize provider to enum
    if isinstance(provider, str):
        provider = Provider(provider.lower())
    
    # Use default options if not provided
    if options is None:
        options = DEFAULT_OPTIONS
    
    if provider == Provider.OLLAMA:
        return _ollama_inference(
            prompt=prompt,
            model=model,
            system_prompt=system_prompt,
            options=options,
            keep_alive=keep_alive,
            format_schema=format_schema,
        )
    elif provider == Provider.GOOGLE:
        return _gemini_inference(
            prompt=prompt,
            model=model,
            system_prompt=system_prompt,
            options=options,
        )
    elif provider == Provider.OPENAI:
        raise NotImplementedError("OpenAI provider not yet implemented")
    elif provider == Provider.ANTHROPIC:
        raise NotImplementedError("Anthropic provider not yet implemented")
    else:
        raise ValueError(f"Unsupported provider: {provider}")


def _ollama_inference(
    prompt: str,
    model: str,
    system_prompt: Optional[str],
    options: LLMOptions,
    keep_alive: str,
    format_schema: Optional[Dict[str, Any]] = None,
) -> LLMResponse:
    """Internal function for Ollama inference."""
    
    # Build messages
    messages: List[Dict[str, str]] = []
    
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    
    messages.append({"role": "user", "content": prompt})
    
    # Build kwargs
    kwargs = {
        "model": model,
        "messages": messages,
        "options": options.to_ollama_options(),
        "keep_alive": keep_alive,
        "stream": False,
    }
    
    # Add format schema if provided (for structured output)
    if format_schema is not None:
        kwargs["format"] = format_schema
    
    # Time the inference
    start_time = time.perf_counter()
    
    response = ollama_chat(**kwargs)
    
    end_time = time.perf_counter()
    inference_time = end_time - start_time
    
    # Extract content
    content = response.get("message", {}).get("content", "")
    
    # Extract token counts from response
    # Ollama provides these in different places depending on version
    input_tokens = response.get("prompt_eval_count", 0)
    output_tokens = response.get("eval_count", 0)
    total_tokens = input_tokens + output_tokens
    
    # Build metadata
    metadata = InferenceMetadata(
        provider="ollama",
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        inference_time_seconds=inference_time,
        cost_usd=0.0,  # Ollama is free/local
    )
    
    return LLMResponse(
        content=content,
        metadata=metadata,
        raw_response=response,
    )


def _gemini_inference(
    prompt: str,
    model: str,
    system_prompt: Optional[str],
    options: LLMOptions,
) -> LLMResponse:
    """Internal function for Google Gemini inference."""
    
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY not found. Set it in .env or as an environment variable."
        )
    
    client = genai.Client(api_key=api_key)
    
    # Build contents
    contents = [
        genai_types.Content(
            role="user",
            parts=[genai_types.Part.from_text(text=prompt)],
        ),
    ]
    
    # Build config
    config_kwargs = {
        "temperature": options.temperature,
        "top_p": options.top_p,
        "max_output_tokens": options.num_predict,
    }
    
    # Add thinking config for supported models
    # gemini-3-* supports thinking_level; gemini-2.5-* uses thinking_budget
    if model.startswith("gemini-3"):
        config_kwargs["thinking_config"] = genai_types.ThinkingConfig(
            thinking_level="HIGH",
        )
    elif model.startswith("gemini-2.5"):
        config_kwargs["thinking_config"] = genai_types.ThinkingConfig(
            thinking_budget=8192,
        )
    
    # Add system instruction if provided
    if system_prompt:
        config_kwargs["system_instruction"] = system_prompt
    
    generate_content_config = genai_types.GenerateContentConfig(**config_kwargs)
    
    # Time the inference
    start_time = time.perf_counter()
    
    # Collect streaming response
    full_text = ""
    raw_response = None
    for chunk in client.models.generate_content_stream(
        model=model,
        contents=contents,
        config=generate_content_config,
    ):
        if chunk.text:
            full_text += chunk.text
        raw_response = chunk  # Keep last chunk for metadata
    
    end_time = time.perf_counter()
    inference_time = end_time - start_time
    
    # Extract token counts from usage_metadata if available
    input_tokens = 0
    output_tokens = 0
    if raw_response and hasattr(raw_response, 'usage_metadata') and raw_response.usage_metadata:
        usage = raw_response.usage_metadata
        input_tokens = getattr(usage, 'prompt_token_count', 0) or 0
        output_tokens = getattr(usage, 'candidates_token_count', 0) or 0
    total_tokens = input_tokens + output_tokens
    
    # Build metadata
    metadata = InferenceMetadata(
        provider="google",
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        inference_time_seconds=inference_time,
        cost_usd=0.0,  # TODO: Calculate based on model pricing
    )
    
    return LLMResponse(
        content=full_text,
        metadata=metadata,
        raw_response=None,  # Gemini response objects aren't easily serializable
    )


# Convenience function with simpler signature
def quick_inference(
    prompt: str,
    model: str = "qwen2.5:3b-instruct",
    system_prompt: Optional[str] = None,
) -> str:
    """
    Quick inference with sensible defaults. Returns just the content string.
    
    Args:
        prompt: The user prompt
        model: Model name (default: qwen2.5:3b-instruct)
        system_prompt: Optional system prompt
    
    Returns:
        Response content as string
    
    Example:
        >>> answer = quick_inference("What is 2+2?")
        >>> print(answer)
    """
    response = get_response(
        prompt=prompt,
        model=model,
        system_prompt=system_prompt,
    )
    return response.content


# Export commonly used items
__all__ = [
    "Provider",
    "LLMOptions",
    "InferenceMetadata",
    "LLMResponse",
    "get_response",
    "quick_inference",
    "DEFAULT_OPTIONS",
    "DEFAULT_KEEP_ALIVE",
]
