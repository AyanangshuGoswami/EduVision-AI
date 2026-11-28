
import os
from dotenv import load_dotenv
from fishaudio import FishAudio

load_dotenv()

VOICE_ID = "768927644fa54e6c9d085fac47d4c484"


def generate_audio(text: str, output_path: str):
    api_key = os.getenv("FISH_API_KEY")

    if not api_key:
        raise RuntimeError("FISH_API_KEY is missing from backend/.env")

    if not text or not text.strip():
        raise ValueError("Audio text cannot be empty.")

    client = FishAudio(api_key=api_key)

    expressive_text = (
        "[Warm, friendly, natural English teacher. "
        "Speak conversationally with genuine enthusiasm. "
        "Use natural pauses between thoughts and emphasize "
        "important words. Avoid a flat or monotonous delivery.] "
        + text.strip()
    )

    audio = client.tts.convert(
        text=expressive_text,
        reference_id=VOICE_ID,
        model="s2.1-pro",
        format="mp3",
        speed=1.0,
    )

    with open(output_path, "wb") as f:
        f.write(audio)

    return output_path
