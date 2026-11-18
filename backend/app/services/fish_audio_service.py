import os
from dotenv import load_dotenv
from fishaudio import FishAudio

load_dotenv()

VOICE_ID = "768927644fa54e6c9d085fac47d4c484"


def generate_audio(text: str, output_path: str):
    api_key = os.getenv("FISH_API_KEY")

    if not api_key:
        raise RuntimeError("FISH_API_KEY is missing from backend/.env")

    client = FishAudio(api_key=api_key)

    audio = client.tts.convert(
        text=text,
        reference_id=VOICE_ID,
        format="mp3",
    )

    with open(output_path, "wb") as f:
        f.write(audio)

    return output_path