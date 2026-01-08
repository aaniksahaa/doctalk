# To run this code you need to install the following dependencies:
# pip install google-genai python-dotenv

import os
from dotenv import load_dotenv
from google import genai
from google.genai import types


def generate(prompt: str, model: str = "gemini-2.0-flash-exp"):
    """
    Generate content using Gemini API
    
    Args:
        prompt: The input text prompt
        model: The Gemini model to use (default: gemini-2.0-flash-exp)
    """
    # Load environment variables from .env file
    load_dotenv()
    
    # Initialize the client with API key from .env
    client = genai.Client(
        api_key=os.environ.get("GEMINI_API_KEY"),
    )

    # Prepare the content
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text=prompt),
            ],
        ),
    ]
    
    # Configure generation (simple config without tools or thinking)
    generate_content_config = types.GenerateContentConfig(
        temperature=0.7,
    )

    # Stream the response
    print("Response: ", end="")
    for chunk in client.models.generate_content_stream(
        model=model,
        contents=contents,
        config=generate_content_config,
    ):
        print(chunk.text, end="")
    print()  # New line at the end


if __name__ == "__main__":
    # Example usage
    prompt = "Explain what is machine learning in 2-3 sentences."
    generate(prompt)
