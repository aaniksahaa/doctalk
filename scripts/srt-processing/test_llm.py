#!/usr/bin/env python3
"""
Test script for llm.py module.
Demonstrates the clean API for LLM inference.
"""

from llm import *


def test_quick_inference():
    """Test the simplest possible API."""
    print("=" * 60)
    print("TEST 1: quick_inference (simplest API)")
    print("=" * 60)
    
    answer = quick_inference(
        prompt="What is the capital of France? Answer in one word.",
        model="qwen2.5:3b-instruct",
    )
    
    print(f"Answer: {answer}")
    print()


def test_get_response_basic():
    """Test get_response with default options."""
    print("=" * 60)
    print("TEST 2: get_response with defaults")
    print("=" * 60)
    
    response = get_response(
        prompt="Explain what Python is in 2 sentences.",
        model="qwen2.5:3b-instruct",
    )
    
    print(f"Content: {response.content}")
    print()
    print("Metadata:")
    print(f"  Provider: {response.metadata.provider}")
    print(f"  Model: {response.metadata.model}")
    print(f"  Input tokens: {response.metadata.input_tokens}")
    print(f"  Output tokens: {response.metadata.output_tokens}")
    print(f"  Total tokens: {response.metadata.total_tokens}")
    print(f"  Inference time: {response.metadata.inference_time_seconds:.3f}s")
    print(f"  Cost: ${response.metadata.cost_usd}")
    print()


def test_get_response_with_system_prompt():
    """Test get_response with system prompt."""
    print("=" * 60)
    print("TEST 3: get_response with system prompt")
    print("=" * 60)
    
    response = get_response(
        prompt="What should I eat today?",
        model="qwen2.5:3b-instruct",
        system_prompt="You are a helpful nutritionist. Keep answers brief.",
    )
    
    print(f"Content: {response.content}")
    print(f"Inference time: {response.metadata.inference_time_seconds:.3f}s")
    print()


def test_get_response_with_custom_options():
    """Test get_response with custom LLMOptions."""
    print("=" * 60)
    print("TEST 4: get_response with custom options")
    print("=" * 60)
    
    custom_options = LLMOptions(
        temperature=0.7,  # More creative
        num_predict=100,  # Limit output length
    )
    
    response = get_response(
        prompt="Write a haiku about programming.",
        model="qwen2.5:3b-instruct",
        options=custom_options,
        keep_alive="10m",  # Keep model loaded longer
    )
    
    print(f"Content: {response.content}")
    print(f"Output tokens: {response.metadata.output_tokens}")
    print(f"Inference time: {response.metadata.inference_time_seconds:.3f}s")
    print()


def test_structured_output():
    """Test get_response with structured JSON output."""
    print("=" * 60)
    print("TEST 5: get_response with structured output (Pydantic)")
    print("=" * 60)
    
    from pydantic import BaseModel
    
    class SentimentResult(BaseModel):
        sentiment: str
        confidence: float
    
    response = get_response(
        prompt="Analyze the sentiment of: 'I love this product!'",
        model="qwen2.5:3b-instruct",
        format_schema=SentimentResult.model_json_schema(),
    )
    
    print(f"Raw content: {response.content}")
    
    # Parse as JSON
    import json
    parsed = json.loads(response.content)
    print(f"Parsed: {parsed}")
    print(f"Inference time: {response.metadata.inference_time_seconds:.3f}s")
    print()


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("LLM Module Test Suite")
    print("=" * 60 + "\n")
    
    test_quick_inference()
    test_get_response_basic()
    test_get_response_with_system_prompt()
    test_get_response_with_custom_options()
    test_structured_output()
    
    print("=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
