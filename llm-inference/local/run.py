#!/usr/bin/env python3
import sys
from datetime import datetime
import os

from ollama import chat

MODEL = "qwen2.5:1.5b-instruct"
# MODEL = "gpt-oss:20b"
# MODEL = "qwen3:30b"
# MODEL = "qwen2.5:14b-instruct"
# MODEL = "qwen2.5:32b-instruct"
# MODEL = "qwen3:30b-instruct"


def read_prompt_file(filepath: str) -> str:
    """Read prompt from markdown file."""
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def show_stats(prompt: str):
    """Display statistics about the prompt."""
    char_count = len(prompt)
    word_count = len(prompt.split())
    line_count = prompt.count("\n") + 1
    # Rough token estimate (1 token ≈ 4 characters for English; Bengali differs)
    estimated_tokens = char_count // 4

    print("=" * 60)
    print("PROMPT STATISTICS")
    print("=" * 60)
    print(f"Characters:       {char_count:,}")
    print(f"Words:            {word_count:,}")
    print(f"Lines:            {line_count:,}")
    print(f"Est. Tokens:      {estimated_tokens:,}")
    print(f"Model:            {MODEL}")
    print(f"Timestamp:        {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()


def ollama_one_prompt_streaming_to_console_and_file(prompt: str, output_file: str) -> str:
    """
    Stream response to stdout AND write incrementally to a markdown file.
    Returns the full response text as well.
    """
    print("Calling Ollama API (streaming)...\n")

    full_text_parts = []

    stream = chat(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        options={
            "num_ctx": 32768,
            "num_predict": 16384,
            "temperature": 0.1,
            "top_p": 0.9,
            "repeat_penalty": 1.1,
        },
        stream=True,
    )

    # Open file once, stream-write content as it arrives
    with open(output_file, "w", encoding="utf-8") as f:
        # Write markdown header up front
        f.write("# LLM Response\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**Model:** {MODEL}\n\n")
        f.write("---\n\n")
        f.flush()

        try:
            for chunk in stream:
                content = chunk.get("message", {}).get("content", "")
                if not content:
                    continue

                # Console streaming
                print(content, end="", flush=True)

                # File streaming
                f.write(content)
                f.flush()  # ensures it appears immediately on disk

                full_text_parts.append(content)

        except KeyboardInterrupt:
            print("\n\n[Interrupted by user]", flush=True)
            f.write("\n\n[Interrupted by user]\n")
            f.flush()

        # Ensure trailing newline
        f.write("\n")
        f.flush()

    full_text = "".join(full_text_parts).strip()
    print("\n")  # newline after streaming output
    print(f"✓ Response streamed & saved to: {output_file}")
    return full_text


def ollama_one_prompt_streaming(prompt: str) -> str:
    """
    Send prompt to Ollama and stream response to stdout,
    while accumulating full text to return.
    """
    print("Calling Ollama API (streaming)...\n")

    full_text_parts = []

    # stream=True makes chat() return an iterator of chunks
    stream = chat(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        options={
            "num_ctx": 32768,
            "num_predict": 16384,
            "temperature": 0.1,
            "top_p": 0.9,
            "repeat_penalty": 1.1,
        },
        stream=True,
        keep_alive="5m",
    )

    try:
        for chunk in stream:
            # Chunk format: {"message": {"role": "assistant", "content": "..."}, ...}
            content = chunk.get("message", {}).get("content", "")
            if content:
                # Print live to terminal without buffering
                print(content, end="", flush=True)
                full_text_parts.append(content)
    except KeyboardInterrupt:
        print("\n\n[Interrupted by user]", flush=True)

    full_text = "".join(full_text_parts).strip()
    print("\n")  # newline after streaming output
    return full_text


def save_response(response: str, output_file: str):
    """Save response to markdown file."""
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("# LLM Response\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**Model:** {MODEL}\n\n")
        f.write("---\n\n")
        f.write(response)
        f.write("\n")  # ensure trailing newline
    print(f"✓ Response saved to: {output_file}")


def main():
    prompt_file = "prompt.md"
    if not os.path.exists(prompt_file):
        print(f"Error: {prompt_file} not found!")
        sys.exit(1)

    print(f"Reading prompt from {prompt_file}...")
    prompt = read_prompt_file(prompt_file)

    show_stats(prompt)

    print("=" * 60)
    print("RESPONSE (STREAMING)")
    print("=" * 60)

    output_file = "response.md"
    answer = ollama_one_prompt_streaming_to_console_and_file(prompt, output_file)

    print("=" * 60)
    print("END OF RESPONSE")
    print("=" * 60)



if __name__ == "__main__":
    main()
