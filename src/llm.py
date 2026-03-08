#!/usr/bin/env python3
"""
LLM Service Abstraction Layer

Provides a clean interface for LLM inference across different providers.
Currently supports: Ollama, Google Gemini, OpenRouter
Future: OpenAI, Anthropic, etc.
"""

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union
from enum import Enum
from pathlib import Path
from urllib import error as urllib_error
from urllib import request as urllib_request

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
    OPENROUTER = "openrouter"
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

    def to_openrouter_params(self) -> Dict[str, Any]:
        """
        Convert to OpenRouter/OpenAI-compatible params.

        Notes:
        - OpenRouter supports max_tokens, temperature, top_p, repetition_penalty, etc.
        - num_ctx is not sent here because context window is model/provider specific.
        """
        params: Dict[str, Any] = {
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": self.num_predict,
        }

        # OpenRouter supports repetition_penalty for compatible models.
        # Unsupported params are generally ignored or rejected depending on model/provider.
        if self.repeat_penalty is not None:
            params["repetition_penalty"] = self.repeat_penalty

        return params


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

# OpenRouter defaults
OPENROUTER_BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_TIMEOUT_SECONDS = float(os.environ.get("OPENROUTER_TIMEOUT_SECONDS", "180"))


def get_response(
    prompt: str,
    model: str,
    provider: Union[Provider, str, None] = None,
    system_prompt: Optional[str] = None,
    options: Optional[LLMOptions] = None,
    keep_alive: str = DEFAULT_KEEP_ALIVE,
    format_schema: Optional[Dict[str, Any]] = None,
) -> LLMResponse:
    """
    Get a response from an LLM.

    Args:
        prompt: The user prompt/query
        model: Model name
            Examples:
                - Ollama: "qwen2.5:3b-instruct"
                - Gemini direct: "gemini-2.5-flash"
                - OpenRouter: "openai/gpt-4o-mini", "anthropic/claude-3.7-sonnet",
                              "google/gemini-2.5-pro"
        provider: LLM provider (auto-detected from model name if not specified)
        system_prompt: Optional system prompt
        options: LLM options (uses defaults if not provided)
        keep_alive: How long to keep model loaded (default: "5m", Ollama only)
        format_schema: Optional JSON schema for structured output
            - Ollama: passed via "format"
            - OpenRouter: converted to response_format json_schema
            - Gemini direct: currently ignored in this implementation

    Returns:
        LLMResponse containing content and metadata
    """
    # Auto-detect provider from model name if not specified
    if provider is None:
        lower_model = model.lower()
        if lower_model.startswith("gemini"):
            provider = Provider.GOOGLE
        elif "/" in model:
            # Most OpenRouter models are namespaced, e.g. "openai/gpt-4o-mini"
            provider = Provider.OPENROUTER
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
    elif provider == Provider.OPENROUTER:
        return _openrouter_inference(
            prompt=prompt,
            model=model,
            system_prompt=system_prompt,
            options=options,
            format_schema=format_schema,
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


def _openrouter_inference(
    prompt: str,
    model: str,
    system_prompt: Optional[str],
    options: LLMOptions,
    format_schema: Optional[Dict[str, Any]] = None,
) -> LLMResponse:
    """Internal function for OpenRouter inference using the OpenAI-compatible Chat Completions API."""

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENROUTER_API_KEY not found. Set it in .env or as an environment variable."
        )

    messages: List[Dict[str, Any]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
    }
    payload.update(options.to_openrouter_params())

    # Structured output support:
    # Convert your existing format_schema into OpenRouter/OpenAI-style response_format.
    if format_schema is not None:
        payload["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "structured_output",
                "strict": True,
                "schema": format_schema,
            },
        }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # Optional OpenRouter attribution headers
    referer = os.environ.get("OPENROUTER_SITE_URL") or os.environ.get("OPENROUTER_HTTP_REFERER")
    title = os.environ.get("OPENROUTER_APP_NAME") or os.environ.get("OPENROUTER_TITLE")

    if referer:
        headers["HTTP-Referer"] = referer
    if title:
        headers["X-Title"] = title

    url = f"{OPENROUTER_BASE_URL.rstrip('/')}/chat/completions"
    body = json.dumps(payload).encode("utf-8")
    request = urllib_request.Request(url=url, data=body, headers=headers, method="POST")

    start_time = time.perf_counter()

    try:
        with urllib_request.urlopen(request, timeout=OPENROUTER_TIMEOUT_SECONDS) as response:
            response_bytes = response.read()
    except urllib_error.HTTPError as exc:
        error_text = exc.read().decode("utf-8", errors="replace")
        try:
            error_json = json.loads(error_text)
            message = error_json.get("error", {}).get("message", error_text)
        except json.JSONDecodeError:
            message = error_text or str(exc)
        raise RuntimeError(f"OpenRouter HTTP {exc.code}: {message}") from exc
    except urllib_error.URLError as exc:
        raise RuntimeError(f"OpenRouter request failed: {exc}") from exc

    end_time = time.perf_counter()
    inference_time = end_time - start_time

    try:
        response_json = json.loads(response_bytes.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError("OpenRouter returned non-JSON response") from exc

    content = _extract_openrouter_content(response_json)

    usage = response_json.get("usage") or {}
    input_tokens = int(usage.get("prompt_tokens") or 0)
    output_tokens = int(usage.get("completion_tokens") or 0)
    total_tokens = int(usage.get("total_tokens") or (input_tokens + output_tokens))

    # OpenRouter usage accounting includes cost in the usage object.
    cost_value = usage.get("cost", 0.0)
    try:
        cost_usd = float(cost_value or 0.0)
    except (TypeError, ValueError):
        cost_usd = 0.0

    metadata = InferenceMetadata(
        provider="openrouter",
        model=response_json.get("model", model),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        inference_time_seconds=inference_time,
        cost_usd=cost_usd,
    )

    return LLMResponse(
        content=content,
        metadata=metadata,
        raw_response=response_json,
    )


def _extract_openrouter_content(response_json: Dict[str, Any]) -> str:
    """
    Extract assistant content from an OpenRouter chat completion response.

    Handles:
    - Standard string content
    - Content blocks/lists from some providers
    """
    choices = response_json.get("choices") or []
    if not choices:
        return ""

    message = (choices[0] or {}).get("message") or {}
    content = message.get("content", "")

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if item.get("type") == "text" and isinstance(item.get("text"), str):
                    parts.append(item["text"])
                elif isinstance(item.get("content"), str):
                    parts.append(item["content"])
        return "".join(parts)

    return str(content)


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
