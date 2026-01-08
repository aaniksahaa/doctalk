from google import genai
from google.genai import types

from dotenv import load_dotenv
import os 

load_dotenv()

# WARNING, this is very expensive

client = genai.Client(
        api_key=os.environ.get("GEMINI_API_KEY"),
    )

# VIDEO_ID = "AMmnqVIp8k0"
# VIDEO_ID = "kvXkyAIyjZw"

YOUTUBE_URL = f"https://www.youtube.com/watch?v={VIDEO_ID}"

def main():
  prompt = """
    Process the audio file and generate a detailed transcription.

    Requirements:
    1. Identify distinct speakers (e.g., Speaker 1, Speaker 2, or names if context allows).
    2. Provide accurate timestamps for each segment (Format: MM:SS).
    3. Detect the primary language of each segment.
    4. If the segment is in a language different than English, also provide the English translation.
    5. Identify the primary emotion of the speaker in this segment. You MUST choose exactly one of the following: Happy, Sad, Angry, Neutral.
    6. Provide a brief summary of the entire audio at the beginning.
  """

  response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=[
      types.Content(
        parts=[
          types.Part(
            file_data=types.FileData(
              file_uri=YOUTUBE_URL
            )
          ),
          types.Part(
            text=prompt
          )
        ]
      )
    ],
    config=types.GenerateContentConfig(
      response_mime_type="application/json",
      response_schema=types.Schema(
        type=types.Type.OBJECT,
        properties={
          "summary": types.Schema(
            type=types.Type.STRING,
            description="A concise summary of the audio content.",
          ),
          "segments": types.Schema(
            type=types.Type.ARRAY,
            description="List of transcribed segments with speaker and timestamp.",
            items=types.Schema(
              type=types.Type.OBJECT,
              properties={
                "speaker": types.Schema(type=types.Type.STRING),
                "timestamp": types.Schema(type=types.Type.STRING),
                "content": types.Schema(type=types.Type.STRING),
                "language": types.Schema(type=types.Type.STRING),
                "language_code": types.Schema(type=types.Type.STRING),
                "translation": types.Schema(type=types.Type.STRING),
                "emotion": types.Schema(
                  type=types.Type.STRING,
                  enum=["happy", "sad", "angry", "neutral"]
                ),
              },
              required=["speaker", "timestamp", "content", "language", "language_code", "emotion"],
            ),
          ),
        },
        required=["summary", "segments"],
      ),
    ),
  )

  print(response.text)
  # save the repose as txt and json
  with open("transcription.txt", "w") as txt_file:
    txt_file.write(response.text)
  with open("transcription.json", "w") as json_file:
    json_file.write(response.text)

  um = getattr(response, "usage_metadata", None)
  print(um)
  if um:
    print("prompt_token_count:", um.prompt_token_count)
    print("candidates_token_count:", um.candidates_token_count)
    print("total_token_count:", um.total_token_count)
    # optional fields that may exist depending on features used:
    for k in ["cached_content_token_count", "thoughts_token_count",
            "tool_use_prompt_token_count", "audio_input_duration", "audio_output_duration"]:
        if hasattr(um, k):
            print(f"{k}:", getattr(um, k))
  else:
    print("No usage_metadata on response")


if __name__ == "__main__":
  main()
