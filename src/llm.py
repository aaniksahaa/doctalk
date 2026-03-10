#!/usr/bin/env python3
"""
LLM Service Abstraction Layer

Provides a clean interface for LLM inference across different providers.
Currently supports: Ollama, Google Gemini, OpenRouter, OpenAI, Together, Anthropic
Future: additional providers as needed
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
    TOGETHER = "together"


@dataclass
class LLMOptions:
    """Configuration options for LLM inference."""
    num_ctx: int = 32768  # Context window size
    num_predict: int = 16384  # Max tokens to generate
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: Optional[int] = None  # Top-K sampling (provider-dependent)
    repeat_penalty: float = 1.1

    def to_ollama_options(self) -> Dict[str, Any]:
        """Convert to Ollama-compatible options dict."""
        opts: Dict[str, Any] = {
            "num_ctx": self.num_ctx,
            "num_predict": self.num_predict,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "repeat_penalty": self.repeat_penalty,
        }
        if self.top_k is not None:
            opts["top_k"] = self.top_k
        return opts

    def to_openai_compatible_params(self) -> Dict[str, Any]:
        """
        Convert to OpenAI-compatible chat completion params.

        Used for:
        - OpenAI
        - OpenRouter
        - Together

        Notes:
        - num_ctx is not sent because context window is model/provider specific.
        - repetition_penalty is not universally supported across providers/models,
          so it is injected selectively by the caller.
        - top_k is not part of the OpenAI API; providers that support it
          should inject it separately.
        """
        return {
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": self.num_predict,
        }

    def to_openrouter_params(self) -> Dict[str, Any]:
        """
        Backward-compatible alias for existing code paths.
        """
        params = self.to_openai_compatible_params()
        if self.repeat_penalty is not None:
            params["repetition_penalty"] = self.repeat_penalty
        if self.top_k is not None:
            params["top_k"] = self.top_k
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


# ── Reasoning-model detection ────────────────────────────────────────────────

# OpenAI reasoning models do not support sampling parameters like temperature,
# top_p, etc.  Only the default value (1) is accepted.  We detect these models
# and automatically strip unsupported parameters so callers don't have to
# special-case them.

_OPENAI_REASONING_PREFIXES = (
    "o1",
    "o3",
    "o4",
)

_OPENAI_REASONING_SUBSTRINGS = (
    "gpt-5-mini",
)


def _is_openai_reasoning_model(model: str) -> bool:
    """Return True if *model* is a known OpenAI reasoning model.

    Reasoning models reject sampling parameters (temperature, top_p, …)
    with an HTTP 400 unless they are set to the default value.
    """
    lower = model.lower()
    for prefix in _OPENAI_REASONING_PREFIXES:
        if lower.startswith(prefix):
            return True
    for substr in _OPENAI_REASONING_SUBSTRINGS:
        if substr in lower:
            return True
    return False

# Default keep_alive duration
DEFAULT_KEEP_ALIVE = "5m"

# OpenRouter defaults
OPENROUTER_BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_TIMEOUT_SECONDS = float(os.environ.get("OPENROUTER_TIMEOUT_SECONDS", "180"))

# OpenAI defaults
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_TIMEOUT_SECONDS = float(os.environ.get("OPENAI_TIMEOUT_SECONDS", "180"))

# Together defaults
TOGETHER_BASE_URL = os.environ.get("TOGETHER_BASE_URL", "https://api.together.xyz/v1")
TOGETHER_TIMEOUT_SECONDS = float(os.environ.get("TOGETHER_TIMEOUT_SECONDS", "180"))

# Anthropic defaults
ANTHROPIC_BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
ANTHROPIC_TIMEOUT_SECONDS = float(os.environ.get("ANTHROPIC_TIMEOUT_SECONDS", "180"))
ANTHROPIC_VERSION = os.environ.get("ANTHROPIC_VERSION", "2023-06-01")


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
                - OpenRouter: "openai/gpt-4o-mini", "anthropic/claude-3.7-sonnet"
                - OpenAI: "gpt-4o-mini", "gpt-4.1-mini", "o3-mini"
                - Together: "meta-llama/Llama-3.3-70B-Instruct-Turbo"
                - Anthropic: "claude-sonnet-4-5", "claude-opus-4-1"
        provider: LLM provider (auto-detected from model name if not specified)
        system_prompt: Optional system prompt
        options: LLM options (uses defaults if not provided)
        keep_alive: How long to keep model loaded (default: "5m", Ollama only)
        format_schema: Optional JSON schema for structured output
            - Ollama: passed via "format"
            - OpenRouter/OpenAI/Together: converted to response_format json_schema
            - Gemini direct: currently ignored in this implementation
            - Anthropic: currently ignored in this implementation

    Returns:
        LLMResponse containing content and metadata
    """
    # Auto-detect provider from model name if not specified
    if provider is None:
        lower_model = model.lower()

        if lower_model.startswith("gemini"):
            provider = Provider.GOOGLE
        elif lower_model.startswith("claude"):
            provider = Provider.ANTHROPIC
        elif (
            lower_model.startswith("gpt-")
            or lower_model.startswith("o1")
            or lower_model.startswith("o3")
            or lower_model.startswith("o4")
            or lower_model.startswith("chatgpt")
        ):
            provider = Provider.OPENAI
        elif "/" in model:
            # Preserve existing behavior:
            # namespaced models default to OpenRouter unless provider is explicitly set to TOGETHER
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
        return _openai_inference(
            prompt=prompt,
            model=model,
            system_prompt=system_prompt,
            options=options,
            format_schema=format_schema,
        )
    elif provider == Provider.TOGETHER:
        return _together_inference(
            prompt=prompt,
            model=model,
            system_prompt=system_prompt,
            options=options,
            format_schema=format_schema,
        )
    elif provider == Provider.ANTHROPIC:
        return _anthropic_inference(
            prompt=prompt,
            model=model,
            system_prompt=system_prompt,
            options=options,
            format_schema=format_schema,
        )
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

    messages: List[Dict[str, str]] = []

    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    messages.append({"role": "user", "content": prompt})

    kwargs = {
        "model": model,
        "messages": messages,
        "options": options.to_ollama_options(),
        "keep_alive": keep_alive,
        "stream": False,
    }

    if format_schema is not None:
        kwargs["format"] = format_schema

    start_time = time.perf_counter()
    response = ollama_chat(**kwargs)
    end_time = time.perf_counter()
    inference_time = end_time - start_time

    content = response.get("message", {}).get("content", "")

    input_tokens = response.get("prompt_eval_count", 0)
    output_tokens = response.get("eval_count", 0)
    total_tokens = input_tokens + output_tokens

    metadata = InferenceMetadata(
        provider="ollama",
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        inference_time_seconds=inference_time,
        cost_usd=0.0,
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

    contents = [
        genai_types.Content(
            role="user",
            parts=[genai_types.Part.from_text(text=prompt)],
        ),
    ]

    config_kwargs = {
        "temperature": options.temperature,
        "top_p": options.top_p,
        "max_output_tokens": options.num_predict,
    }
    if options.top_k is not None:
        config_kwargs["top_k"] = options.top_k

    if model.startswith("gemini-3"):
        config_kwargs["thinking_config"] = genai_types.ThinkingConfig(
            thinking_level="HIGH",
        )
    elif model.startswith("gemini-2.5"):
        config_kwargs["thinking_config"] = genai_types.ThinkingConfig(
            thinking_budget=8192,
        )

    if system_prompt:
        config_kwargs["system_instruction"] = system_prompt

    generate_content_config = genai_types.GenerateContentConfig(**config_kwargs)

    start_time = time.perf_counter()

    full_text = ""
    raw_response = None
    for chunk in client.models.generate_content_stream(
        model=model,
        contents=contents,
        config=generate_content_config,
    ):
        if chunk.text:
            full_text += chunk.text
        raw_response = chunk

    end_time = time.perf_counter()
    inference_time = end_time - start_time

    input_tokens = 0
    output_tokens = 0
    if raw_response and hasattr(raw_response, "usage_metadata") and raw_response.usage_metadata:
        usage = raw_response.usage_metadata
        input_tokens = getattr(usage, "prompt_token_count", 0) or 0
        output_tokens = getattr(usage, "candidates_token_count", 0) or 0
    total_tokens = input_tokens + output_tokens

    metadata = InferenceMetadata(
        provider="google",
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        inference_time_seconds=inference_time,
        cost_usd=0.0,
    )

    return LLMResponse(
        content=full_text,
        metadata=metadata,
        raw_response=None,
    )


def _openrouter_inference(
    prompt: str,
    model: str,
    system_prompt: Optional[str],
    options: LLMOptions,
    format_schema: Optional[Dict[str, Any]] = None,
) -> LLMResponse:
    """Internal function for OpenRouter inference."""
    return _openai_compatible_inference(
        prompt=prompt,
        model=model,
        system_prompt=system_prompt,
        options=options,
        format_schema=format_schema,
        provider_name="openrouter",
        api_key_env="OPENROUTER_API_KEY",
        base_url=OPENROUTER_BASE_URL,
        timeout_seconds=OPENROUTER_TIMEOUT_SECONDS,
        add_repetition_penalty=True,
        extra_headers=_build_openrouter_headers(),
    )


def _openai_inference(
    prompt: str,
    model: str,
    system_prompt: Optional[str],
    options: LLMOptions,
    format_schema: Optional[Dict[str, Any]] = None,
) -> LLMResponse:
    """Internal function for OpenAI inference."""
    return _openai_compatible_inference(
        prompt=prompt,
        model=model,
        system_prompt=system_prompt,
        options=options,
        format_schema=format_schema,
        provider_name="openai",
        api_key_env="OPENAI_API_KEY",
        base_url=OPENAI_BASE_URL,
        timeout_seconds=OPENAI_TIMEOUT_SECONDS,
        add_repetition_penalty=False,  # avoid passing unsupported params
        max_tokens_key="max_completion_tokens",  # newer OpenAI models require this
        strip_sampling_params=_is_openai_reasoning_model(model),
    )


def _together_inference(
    prompt: str,
    model: str,
    system_prompt: Optional[str],
    options: LLMOptions,
    format_schema: Optional[Dict[str, Any]] = None,
) -> LLMResponse:
    """Internal function for Together inference."""
    return _openai_compatible_inference(
        prompt=prompt,
        model=model,
        system_prompt=system_prompt,
        options=options,
        format_schema=format_schema,
        provider_name="together",
        api_key_env="TOGETHER_API_KEY",
        base_url=TOGETHER_BASE_URL,
        timeout_seconds=TOGETHER_TIMEOUT_SECONDS,
        add_repetition_penalty=False,
    )


def _openai_compatible_inference(
    prompt: str,
    model: str,
    system_prompt: Optional[str],
    options: LLMOptions,
    format_schema: Optional[Dict[str, Any]],
    provider_name: str,
    api_key_env: str,
    base_url: str,
    timeout_seconds: float,
    add_repetition_penalty: bool = False,
    extra_headers: Optional[Dict[str, str]] = None,
    max_tokens_key: str = "max_tokens",
    strip_sampling_params: bool = False,
) -> LLMResponse:
    """
    Shared implementation for OpenAI-compatible chat/completions APIs.

    Used by:
    - OpenAI
    - OpenRouter
    - Together
    """
    api_key = os.environ.get(api_key_env)
    if not api_key:
        raise ValueError(
            f"{api_key_env} not found. Set it in .env or as an environment variable."
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
    params = options.to_openai_compatible_params()
    # Rename max_tokens key if needed (e.g. max_completion_tokens for OpenAI)
    if max_tokens_key != "max_tokens" and "max_tokens" in params:
        params[max_tokens_key] = params.pop("max_tokens")
    # Reasoning models (o1, o3, o4, gpt-5-mini, …) reject non-default
    # sampling parameters.  Strip them to avoid HTTP 400 errors.
    if strip_sampling_params:
        for key in ("temperature", "top_p", "top_k"):
            params.pop(key, None)
    payload.update(params)

    if add_repetition_penalty and options.repeat_penalty is not None:
        payload["repetition_penalty"] = options.repeat_penalty

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
    if extra_headers:
        headers.update(extra_headers)

    url = f"{base_url.rstrip('/')}/chat/completions"
    body = json.dumps(payload).encode("utf-8")
    request = urllib_request.Request(url=url, data=body, headers=headers, method="POST")

    start_time = time.perf_counter()

    try:
        with urllib_request.urlopen(request, timeout=timeout_seconds) as response:
            response_bytes = response.read()
    except urllib_error.HTTPError as exc:
        error_text = exc.read().decode("utf-8", errors="replace")
        try:
            error_json = json.loads(error_text)
            message = (
                error_json.get("error", {}).get("message")
                or error_json.get("message")
                or error_text
            )
        except json.JSONDecodeError:
            message = error_text or str(exc)
        raise RuntimeError(f"{provider_name.capitalize()} HTTP {exc.code}: {message}") from exc
    except urllib_error.URLError as exc:
        raise RuntimeError(f"{provider_name.capitalize()} request failed: {exc}") from exc

    end_time = time.perf_counter()
    inference_time = end_time - start_time

    try:
        response_json = json.loads(response_bytes.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{provider_name.capitalize()} returned non-JSON response") from exc

    content = _extract_openai_compatible_content(response_json)

    usage = response_json.get("usage") or {}
    input_tokens = int(usage.get("prompt_tokens") or 0)
    output_tokens = int(usage.get("completion_tokens") or 0)
    total_tokens = int(usage.get("total_tokens") or (input_tokens + output_tokens))

    # Only OpenRouter reliably returns cost in usage.
    cost_value = usage.get("cost", 0.0)
    try:
        cost_usd = float(cost_value or 0.0)
    except (TypeError, ValueError):
        cost_usd = 0.0

    metadata = InferenceMetadata(
        provider=provider_name,
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


def _anthropic_inference(
    prompt: str,
    model: str,
    system_prompt: Optional[str],
    options: LLMOptions,
    format_schema: Optional[Dict[str, Any]] = None,
) -> LLMResponse:
    """Internal function for Anthropic Claude inference via Messages API."""

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY not found. Set it in .env or as an environment variable."
        )

    # Anthropic structured output is not wired here yet to keep this addition minimal
    # and avoid changing current behavior unexpectedly.
    _ = format_schema

    payload: Dict[str, Any] = {
        "model": model,
        "max_tokens": options.num_predict,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "temperature": options.temperature,
        "top_p": options.top_p,
    }
    if options.top_k is not None:
        payload["top_k"] = options.top_k

    if system_prompt:
        payload["system"] = system_prompt

    headers = {
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }

    url = f"{ANTHROPIC_BASE_URL.rstrip('/')}/v1/messages"
    body = json.dumps(payload).encode("utf-8")
    request = urllib_request.Request(url=url, data=body, headers=headers, method="POST")

    start_time = time.perf_counter()

    try:
        with urllib_request.urlopen(request, timeout=ANTHROPIC_TIMEOUT_SECONDS) as response:
            response_bytes = response.read()
    except urllib_error.HTTPError as exc:
        error_text = exc.read().decode("utf-8", errors="replace")
        try:
            error_json = json.loads(error_text)
            message = (
                error_json.get("error", {}).get("message")
                or error_json.get("message")
                or error_text
            )
        except json.JSONDecodeError:
            message = error_text or str(exc)
        raise RuntimeError(f"Anthropic HTTP {exc.code}: {message}") from exc
    except urllib_error.URLError as exc:
        raise RuntimeError(f"Anthropic request failed: {exc}") from exc

    end_time = time.perf_counter()
    inference_time = end_time - start_time

    try:
        response_json = json.loads(response_bytes.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError("Anthropic returned non-JSON response") from exc

    content = _extract_anthropic_content(response_json)

    usage = response_json.get("usage") or {}
    input_tokens = int(usage.get("input_tokens") or 0)
    output_tokens = int(usage.get("output_tokens") or 0)
    total_tokens = input_tokens + output_tokens

    metadata = InferenceMetadata(
        provider="anthropic",
        model=response_json.get("model", model),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        inference_time_seconds=inference_time,
        cost_usd=0.0,  # TODO: calculate if you want pricing estimates
    )

    return LLMResponse(
        content=content,
        metadata=metadata,
        raw_response=response_json,
    )


def _extract_openai_compatible_content(response_json: Dict[str, Any]) -> str:
    """
    Extract assistant content from an OpenAI-compatible chat completion response.

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


def _extract_anthropic_content(response_json: Dict[str, Any]) -> str:
    """
    Extract assistant text from an Anthropic Messages API response.
    """
    content = response_json.get("content") or []
    if not isinstance(content, list):
        return str(content)

    parts: List[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text" and isinstance(block.get("text"), str):
            parts.append(block["text"])

    return "".join(parts)


def _build_openrouter_headers() -> Dict[str, str]:
    """
    Optional OpenRouter attribution headers.
    """
    headers: Dict[str, str] = {}

    referer = os.environ.get("OPENROUTER_SITE_URL") or os.environ.get("OPENROUTER_HTTP_REFERER")
    title = os.environ.get("OPENROUTER_APP_NAME") or os.environ.get("OPENROUTER_TITLE")

    if referer:
        headers["HTTP-Referer"] = referer
    if title:
        headers["X-Title"] = title

    return headers


# Convenience function with simpler signature
def quick_inference(
    prompt: str,
    model: str = "qwen2.5:3b-instruct",
    system_prompt: Optional[str] = None,
) -> str:
    """
    Quick inference with sensible defaults. Returns just the content string.
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