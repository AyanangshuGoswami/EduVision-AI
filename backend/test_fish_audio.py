from app.services.fish_audio_service import generate_audio

generate_audio(
    "Hello students! Welcome to EduVision AI. Today, we are going to learn something exciting together.",
    "test_voice.mp3"
)

print("Voice generated successfully!")