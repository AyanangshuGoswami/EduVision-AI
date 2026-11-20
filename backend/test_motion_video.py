
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1280, 720
FPS = 24
DURATION = 5
TOTAL_FRAMES = FPS * DURATION

OUTPUT_DIR = Path("generated_videos")
OUTPUT_DIR.mkdir(exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / "first_motion_test.mp4"


def font(size, bold=False):
    name = "arialbd.ttf" if bold else "arial.ttf"
    return ImageFont.truetype(f"C:/Windows/Fonts/{name}", size)


def centered(draw, position, text, selected_font, color):
    bounds = draw.textbbox((0, 0), text, font=selected_font)
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    draw.text(
        (position[0] - width / 2, position[1] - height / 2),
        text,
        font=selected_font,
        fill=color,
    )


def create_frame(frame_number):
    image = Image.new("RGB", (WIDTH, HEIGHT), (13, 21, 48))
    draw = ImageDraw.Draw(image)

    title = font(48, True)
    heading = font(29, True)
    normal = font(23)

    draw.text((70, 45), "HOW A GAN WORKS", font=title, fill="white")
    draw.text(
        (73, 110),
        "Two neural networks learn by competing",
        font=normal,
        fill=(165, 190, 225),
    )

    # Generator card
    draw.rounded_rectangle(
        (95, 250, 485, 490),
        radius=28,
        fill=(35, 52, 93),
        outline=(75, 133, 255),
        width=4,
    )

    centered(
        draw, (290, 305), "GENERATOR",
        heading, (130, 180, 255)
    )
    centered(
        draw, (290, 365), "Creates fake data",
        normal, "white"
    )

    # Discriminator card
    draw.rounded_rectangle(
        (795, 250, 1185, 490),
        radius=28,
        fill=(65, 42, 88),
        outline=(190, 110, 255),
        width=4,
    )

    centered(
        draw, (990, 305), "DISCRIMINATOR",
        heading, (215, 165, 255)
    )
    centered(
        draw, (990, 365), "Checks if it is real",
        normal, "white"
    )

    # Animated arrow
    draw.line((500, 370, 780, 370), fill=(100, 220, 190), width=7)
    draw.polygon(
        [(780, 370), (755, 355), (755, 385)],
        fill=(100, 220, 190),
    )

    # Moving data particle
    progress = (frame_number % FPS) / FPS
    x = 510 + int(progress * 245)

    draw.ellipse(
        (x - 13, 357, x + 13, 383),
        fill=(255, 220, 100),
    )

    centered(
        draw, (640, 430), "Generated sample",
        normal, (180, 240, 220)
    )

    # Bottom explanation
    draw.rounded_rectangle(
        (190, 555, 1090, 635),
        radius=20,
        fill=(25, 36, 68),
        outline=(65, 85, 130),
        width=2,
    )

    centered(
        draw,
        (640, 595),
        "The generator learns from the discriminator.",
        normal,
        (230, 238, 255),
    )

    return image


def main():
    print("Creating animated frames...")

    with tempfile.TemporaryDirectory() as folder:
        folder = Path(folder)

        for number in range(TOTAL_FRAMES):
            create_frame(number).save(
                folder / f"frame_{number:04d}.png"
            )

        print("Rendering MP4...")

        command = [
            "ffmpeg",
            "-y",
            "-framerate", str(FPS),
            "-i", str(folder / "frame_%04d.png"),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(OUTPUT_FILE.resolve()),
        ]

        subprocess.run(command, check=True)

    print("\nSUCCESS! Your video has been created.")
    print(f"Location: {OUTPUT_FILE.resolve()}")


if __name__ == "__main__":
    main()
