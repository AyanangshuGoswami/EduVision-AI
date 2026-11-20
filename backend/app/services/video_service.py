
import json
import math
import os
import subprocess
import tempfile
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from google import genai

from app.core.config import settings
from app.services.gemini_service import (
    _generate_with_retry,
    _clean_json_response,
)


# --------------------------------------------------
# FFMPEG CONFIGURATION
# --------------------------------------------------

FFMPEG_BIN = (
    Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    / "Microsoft"
    / "WinGet"
    / "Packages"
    / "Gyan.FFmpeg.Shared_Microsoft.Winget.Source_8wekyb3d8bbwe"
    / "ffmpeg-9.1-full_build-shared"
    / "bin"
)

FFMPEG_EXE = FFMPEG_BIN / "ffmpeg.exe"
FFPROBE_EXE = FFMPEG_BIN / "ffprobe.exe"


def check_ffmpeg():
    if not FFMPEG_EXE.exists():
        raise FileNotFoundError(f"FFmpeg not found: {FFMPEG_EXE}")

    if not FFPROBE_EXE.exists():
        raise FileNotFoundError(f"FFprobe not found: {FFPROBE_EXE}")


# --------------------------------------------------
# STORYBOARD GENERATION
# --------------------------------------------------


def generate_storyboard(topic: dict, lesson: dict) -> dict:
    """Create a storyboard synchronized with the exact teacher narration."""

    if not settings.gemini_api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured in backend/.env"
        )

    teacher_script = str(lesson.get("teacher_script", "")).strip()

    if not teacher_script:
        raise RuntimeError(
            "The lesson does not contain a teacher_script."
        )

    client = genai.Client(api_key=settings.gemini_api_key)

    lesson_context = {
        "topic_title": lesson.get("topic_title", ""),
        "introduction": lesson.get("introduction", ""),
        "explanation": lesson.get("explanation", ""),
        "examples": lesson.get("examples", []),
        "key_points": lesson.get("key_points", []),
        "recap": lesson.get("recap", ""),
    }

    prompt = f"""
You are the professional educational animation director
for EduVision AI.

Your task is to transform a teacher's EXISTING spoken lesson
into a beautiful, meaningful educational motion-graphics video.

The teacher's narration is already written.

YOUR MOST IMPORTANT RESPONSIBILITY:
Preserve the teacher's exact words and synchronize
the animations with those words.

==================================================
1. ORIGINAL TEACHER NARRATION
==================================================

TOPIC:
{json.dumps(topic, indent=2, default=str)}

ADDITIONAL LESSON CONTEXT:
{json.dumps(lesson_context, indent=2, default=str)}

COMPLETE ORIGINAL TEACHER SCRIPT:
{teacher_script}

==================================================
2. STRICT NARRATION PRESERVATION
==================================================

Divide the original teacher script into approximately
6-12 logical scenes.

Each scene must contain a continuous portion of the
original teacher script.

CRITICAL RULES:

- Copy the original narration word for word.
- Do not paraphrase anything.
- Do not summarize anything.
- Do not remove sentences.
- Do not add new spoken sentences.
- Do not change technical terms.
- Do not rearrange sentences.
- Preserve the original order.
- Do not repeat sentences in different scenes.

When all scene narration fields are joined in scene order,
they must reproduce the complete original teacher script.

You may divide the narration at natural sentence boundaries.
Preserve punctuation and the original wording.

If a scene contains several sentences, keep them together
when they explain the same concept.

==================================================
3. VISUAL TEACHING
==================================================

Every scene must visually explain the narration
belonging to that scene.

Think like a professional educational animator.

Do not create decorative animations that teach nothing.

Examples of meaningful visual storytelling:

- When a teacher introduces an object, make it appear.
- When a teacher describes movement, animate its movement.
- When two components interact, show them connecting.
- When a process changes something, show the transformation.
- When comparing two concepts, display both clearly.
- When explaining a cycle, show the stages and connections.
- When describing a result, reveal that result at the correct moment.

Use topic-specific visual explanations.

Do not use generic diagrams repeated across scenes.

Do not use cartoon characters, robots, mascots,
or unrelated decorative pictures.

==================================================
4. SCENE DESIGN
==================================================

Each scene should teach one main idea.

Create a logical visual progression.

For example, a process explanation should visually progress
from its starting point through its intermediate steps
to its final result.

Use approximately 3-8 meaningful objects per scene.

Use approximately 2-6 meaningful animation actions per scene.

Keep diagrams readable and avoid unnecessary objects.

Keep all objects inside the safe video area.

Reserve the upper area for the scene title
and the lower area for captions or supporting labels.

Use object coordinates as percentages:

- x and y are the object's center.
- width and height are percentages of the video frame.
- All coordinates must be between 0 and 100.
- Keep important objects away from the extreme edges.

Avoid overlapping objects unless overlap is intentional.

Keep labels short and readable.

==================================================
5. ANIMATION ACTIONS
==================================================

Allowed object types:

rectangle, circle, arrow, line, text,
image_placeholder, triangle.

Allowed animation actions:

appear, disappear, move, highlight,
connect, transform, pulse.

Every object must contain:

id, type, label, x, y, width, height, color.

Every animation action must contain:

object_id, action, start_seconds, duration_seconds.

Move actions must also contain:

target_x, target_y.

Use only valid hexadecimal colors.

Every action object_id must refer to an object
in the same scene.

Animation timings are relative to the beginning
of the scene.

Use sensible timings and keep actions within
the approximate scene duration.

Important:
The animation should illustrate the meaning of the narration,
not merely make objects move randomly.

==================================================
6. SCENE PACING
==================================================

Create scenes of a reasonable length based on the narration.

A scene should contain enough time to explain its concept.

Do not split every sentence into a separate scene.

Do not combine unrelated concepts into one scene.

Estimate scene duration based on the amount of narration.
The actual final duration will be adjusted using generated audio.

Create an appropriate visual transition between scenes.

Finish with a meaningful visual recap of the topic.

==================================================
7. OUTPUT FORMAT
==================================================

Return ONLY valid JSON.

Use exactly this structure:

{{
  "topic_title": "Lesson title",
  "video_style": "Professional educational motion graphics",
  "scenes": [
    {{
      "scene_number": 1,
      "scene_title": "Scene title",
      "visual_type": "diagram",
      "narration": "Exact continuous text copied from the original teacher script.",
      "visual_description": "Explain what the student sees and how it illustrates the narration.",
      "visual_objects": [
        {{
          "id": "object_1",
          "type": "rectangle",
          "label": "Example",
          "x": 30,
          "y": 40,
          "width": 20,
          "height": 15,
          "color": "#3478F6"
        }}
      ],
      "animation_actions": [
        {{
          "object_id": "object_1",
          "action": "appear",
          "start_seconds": 0,
          "duration_seconds": 1
        }}
      ],
      "on_screen_text": ["Example"],
      "duration_seconds": 15,
      "transition": "fade"
    }}
  ]
}}

The narration fields must cover the entire original script
in exactly the same order and wording.

Return valid JSON only.
Do not use Markdown fences.
"""

    response = _generate_with_retry(client, prompt)

    if not response.text:
        raise RuntimeError(
            "Gemini returned an empty storyboard response."
        )

    storyboard = _clean_json_response(response.text)

    if not isinstance(storyboard, dict):
        raise RuntimeError("Invalid storyboard format.")

    scenes = storyboard.get("scenes", [])

    if not isinstance(scenes, list) or not scenes:
        raise RuntimeError("Gemini generated no storyboard scenes.")

    # Normalize whitespace only. Do not alter actual words.
    def normalize_script(value):
        return " ".join(str(value).split())

    combined_narration = " ".join(
        str(scene.get("narration", "")).strip()
        for scene in scenes
        if isinstance(scene, dict)
    )

    if normalize_script(combined_narration) != normalize_script(
        teacher_script
    ):
        raise RuntimeError(
            "Storyboard narration does not exactly match the "
            "original teacher script. Please regenerate the storyboard."
        )

    # Validate all scene objects and animation references.
    for index, scene in enumerate(scenes, start=1):

        if not isinstance(scene, dict):
            raise RuntimeError(
                f"Invalid scene format in scene {index}."
            )

        scene["scene_number"] = index

        objects = scene.get("visual_objects", [])
        actions = scene.get("animation_actions", [])

        if not isinstance(objects, list) or not isinstance(actions, list):
            raise RuntimeError(
                f"Invalid animation data in scene {index}."
            )

        object_ids = set()

        for obj in objects:
            if not isinstance(obj, dict):
                raise RuntimeError(
                    f"Invalid visual object in scene {index}."
                )

            object_id = obj.get("id")

            if not object_id or object_id in object_ids:
                raise RuntimeError(
                    f"Missing or duplicate object ID in scene {index}."
                )

            object_ids.add(object_id)

            for field in ("x", "y", "width", "height"):
                try:
                    value = float(obj.get(field))
                except (TypeError, ValueError):
                    raise RuntimeError(
                        f"Invalid {field} in scene {index}."
                    )

                if not 0 <= value <= 100:
                    raise RuntimeError(
                        f"Object {field} must be between 0 and 100 "
                        f"in scene {index}."
                    )

        for action in actions:
            if (
                not isinstance(action, dict)
                or action.get("object_id") not in object_ids
            ):
                raise RuntimeError(
                    f"Scene {index} contains an action referencing "
                    "an unknown object."
                )

            if action.get("action") not in {
                "appear",
                "disappear",
                "move",
                "highlight",
                "connect",
                "transform",
                "pulse",
            }:
                raise RuntimeError(
                    f"Unsupported animation action in scene {index}."
                )

    return storyboard

    


# --------------------------------------------------
# VIDEO DESIGN
# --------------------------------------------------

WIDTH = 1280
HEIGHT = 720
FPS = 12


def get_font(size, bold=False):
    font_name = "arialbd.ttf" if bold else "arial.ttf"
    font_path = Path("C:/Windows/Fonts") / font_name

    try:
        return ImageFont.truetype(str(font_path), size)
    except OSError:
        return ImageFont.load_default()


def get_color(value, fallback=(75, 145, 245)):
    try:
        value = str(value).lstrip("#")

        if len(value) == 6:
            return tuple(
                int(value[i:i + 2], 16)
                for i in (0, 2, 4)
            )
    except (ValueError, TypeError):
        pass

    return fallback


def ease(value):
    """Smooth animation interpolation."""
    value = max(0.0, min(1.0, value))
    return value * value * (3 - 2 * value)



def get_object_position(obj, scene_time, actions):
    # Starting position of the object.
    current_x = float(obj.get("x", 50))
    current_y = float(obj.get("y", 50))

    # Find and sort movement actions for this object.
    matching = sorted(
        [
            action for action in actions
            if action.get("object_id") == obj.get("id")
            and action.get("action") == "move"
        ],
        key=lambda action: float(action.get("start_seconds", 0))
    )

    for action in matching:
        start = float(action.get("start_seconds", 0))
        duration = max(
            float(action.get("duration_seconds", 1)),
            0.01
        )

        target_x = float(action.get("target_x", current_x))
        target_y = float(action.get("target_y", current_y))

        # Movement has not started yet.
        if scene_time < start:
            break

        # Calculate movement progress between 0 and 1.
        progress = (scene_time - start) / duration
        progress = max(0.0, min(1.0, progress))

        # Smoothly move toward the destination.
        smooth_progress = ease(progress)

        x = current_x + (target_x - current_x) * smooth_progress
        y = current_y + (target_y - current_y) * smooth_progress

        # If movement is still happening, return its current position.
        if progress < 1.0:
            return x, y

        # Movement finished. Prepare for the next movement.
        current_x = target_x
        current_y = target_y

    return current_x, current_y


def get_object_scale(obj, scene_time, actions):
    scale = 1.0
    object_id = obj.get("id")

    for action in actions:
        if action.get("object_id") != object_id:
            continue

        start = float(action.get("start_seconds", 0))
        duration = max(float(action.get("duration_seconds", 1)), 0.01)
        elapsed = scene_time - start

        if action.get("action") == "appear":
            if elapsed < 0:
                return 0.0
            scale = 0.25 + 0.75 * ease(elapsed / duration)

        elif action.get("action") == "disappear":
            if elapsed >= duration:
                return 0.0
            if elapsed >= 0:
                scale *= 1.0 - ease(elapsed / duration)

        elif action.get("action") == "pulse" and 0 <= elapsed <= duration:
            scale *= 1.0 + 0.16 * math.sin(
                (elapsed / duration) * math.pi * 4
            )

        elif action.get("action") == "transform" and 0 <= elapsed <= duration:
            scale *= 0.75 + 0.25 * ease(elapsed / duration)

    return scale


def is_highlighted(object_id, scene_time, actions):
    for action in actions:
        if (
            action.get("object_id") == object_id
            and action.get("action") == "highlight"
        ):
            start = float(action.get("start_seconds", 0))
            duration = float(action.get("duration_seconds", 1))

            if start <= scene_time <= start + duration:
                return True

    return False



def get_object_boxes(scene, scene_time):
    actions = scene.get("animation_actions", [])
    boxes = {}

    # Keep objects inside the safe video area.
    margin_x = 50
    top_limit = 145
    bottom_limit = 630

    for obj in scene.get("visual_objects", []):
        if not isinstance(obj, dict):
            continue

        x, y = get_object_position(obj, scene_time, actions)
        scale = get_object_scale(obj, scene_time, actions)

        if scale <= 0:
            continue

        width = WIDTH * float(obj.get("width", 15)) / 100 * scale
        height = HEIGHT * float(obj.get("height", 10)) / 100 * scale

        # Prevent objects from becoming larger than the safe area.
        width = min(width, WIDTH - (2 * margin_x))
        height = min(height, bottom_limit - top_limit)

        # Calculate object center.
        center_x = WIDTH * x / 100
        center_y = HEIGHT * y / 100

        # Keep the complete object inside the frame.
        center_x = max(
            margin_x + width / 2,
            min(WIDTH - margin_x - width / 2, center_x)
        )

        center_y = max(
            top_limit + height / 2,
            min(bottom_limit - height / 2, center_y)
        )

        boxes[obj.get("id")] = (
            center_x,
            center_y,
            width,
            height,
        )

    return boxes



# --------------------------------------------------
# DRAW INDIVIDUAL OBJECTS
# --------------------------------------------------

def draw_arrow(draw, x1, y1, x2, y2, color, width=6):
    draw.line(
        (x1, y1, x2, y2),
        fill=color,
        width=width,
    )

    angle = math.atan2(y2 - y1, x2 - x1)
    arrow_length = 22
    arrow_angle = math.pi / 6

    left = (
        x2 - arrow_length * math.cos(angle - arrow_angle),
        y2 - arrow_length * math.sin(angle - arrow_angle),
    )

    right = (
        x2 - arrow_length * math.cos(angle + arrow_angle),
        y2 - arrow_length * math.sin(angle + arrow_angle),
    )

    draw.polygon(
        [(x2, y2), left, right],
        fill=color,
    )



def draw_visual_object(
    draw,
    obj,
    box,
    highlighted=False,
):
    center_x, center_y, width, height = box

    # Keep drawing coordinates inside the video frame.
    left = max(8, center_x - width / 2)
    top = max(135, center_y - height / 2)
    right = min(WIDTH - 8, center_x + width / 2)
    bottom = min(HEIGHT - 75, center_y + height / 2)

    if right <= left or bottom <= top:
        return

    color = get_color(obj.get("color"))
    outline = (255, 220, 100) if highlighted else (225, 237, 255)
    outline_width = 6 if highlighted else 3

    object_type = obj.get("type", "rectangle")
    label = str(obj.get("label", ""))[:55]

    if object_type == "circle":
        draw.ellipse(
            (left, top, right, bottom),
            fill=color,
            outline=outline,
            width=outline_width,
        )

    elif object_type == "triangle":
        draw.polygon(
            [
                ((left + right) / 2, top),
                (right, bottom),
                (left, bottom),
            ],
            fill=color,
            outline=outline,
        )

    elif object_type == "arrow":
        draw_arrow(
            draw,
            left,
            center_y,
            right,
            center_y,
            color,
            8,
        )

    elif object_type == "line":
        draw.line(
            (left, center_y, right, center_y),
            fill=color,
            width=6,
        )

    elif object_type == "text":
        font_size = max(14, min(30, int(height * 0.45)))
        font = get_font(font_size, True)

        draw.text(
            (left, top),
            label,
            font=font,
            fill=(245, 248, 255),
            stroke_width=1,
            stroke_fill=(15, 25, 48),
        )
        return

    elif object_type == "image_placeholder":
        draw.rounded_rectangle(
            (left, top, right, bottom),
            radius=20,
            fill=(38, 55, 88),
            outline=outline,
            width=outline_width,
        )

        draw.ellipse(
            (
                center_x - width * 0.1,
                center_y - height * 0.25,
                center_x + width * 0.1,
                center_y - height * 0.05,
            ),
            fill=(255, 205, 105),
        )

        draw.polygon(
            [
                (left + width * 0.12, bottom - height * 0.15),
                (center_x, center_y),
                (right - width * 0.12, bottom - height * 0.15),
            ],
            fill=(100, 190, 155),
        )

    else:
        draw.rounded_rectangle(
            (left, top, right, bottom),
            radius=20,
            fill=color,
            outline=outline,
            width=outline_width,
        )

    if not label or object_type in ("arrow", "line"):
        return

    # Automatically choose a font that fits the object.
    available_width = max(20, right - left - 24)
    available_height = max(20, bottom - top - 16)

    font = None
    wrapped_lines = []

    for font_size in range(25, 11, -1):
        candidate_font = get_font(font_size, True)

        wrapped_lines = textwrap.wrap(
            label,
            width=max(5, int(available_width / (font_size * 0.58))),
        )

        wrapped_lines = wrapped_lines[:3]

        text_box = draw.multiline_textbbox(
            (0, 0),
            "\n".join(wrapped_lines),
            font=candidate_font,
            spacing=4,
            align="center",
        )

        text_width = text_box[2] - text_box[0]
        text_height = text_box[3] - text_box[1]

        if (
            text_width <= available_width
            and text_height <= available_height
        ):
            font = candidate_font
            break

    if font is None:
        font = get_font(12, True)
        wrapped_lines = textwrap.wrap(
            label,
            width=max(5, int(available_width / 8)),
        )[:2]

    final_text = "\n".join(wrapped_lines)

    text_box = draw.multiline_textbbox(
        (0, 0),
        final_text,
        font=font,
        spacing=4,
        align="center",
    )

    text_width = text_box[2] - text_box[0]
    text_height = text_box[3] - text_box[1]

    text_x = center_x - text_width / 2
    text_y = center_y - text_height / 2

    draw.multiline_text(
        (text_x, text_y),
        final_text,
        font=font,
        fill=(255, 255, 255),
        spacing=4,
        align="center",
        stroke_width=1,
        stroke_fill=(20, 30, 50),
    )

# --------------------------------------------------
# DRAW COMPLETE ANIMATION FRAME
# --------------------------------------------------

def create_animation_frame(
    scene,
    scene_number,
    total_scenes,
    scene_time,
    output_path,
):
    image = Image.new(
        "RGB",
        (WIDTH, HEIGHT),
        (13, 21, 43),
    )

    draw = ImageDraw.Draw(image)

    title_font = get_font(36, True)
    small_font = get_font(18, True)
    label_font = get_font(20, True)

    # Background decoration
    draw.ellipse(
        (970, -220, 1450, 250),
        fill=(25, 38, 75),
    )

    draw.ellipse(
        (-200, 540, 270, 990),
        fill=(22, 35, 68),
    )

    # Header
    draw.text(
        (65, 25),
        "EDUVISION AI",
        font=small_font,
        fill=(105, 190, 255),
    )

    draw.text(
        (65, 65),
        str(scene.get("scene_title", f"Scene {scene_number}"))[:55],
        font=title_font,
        fill=(245, 248, 255),
    )

    draw.line(
        (65, 125, 1215, 125),
        fill=(65, 90, 140),
        width=2,
    )

    # Get current positions and sizes
    boxes = get_object_boxes(scene, scene_time)
    actions = scene.get("animation_actions", [])

    # Draw connectors first so objects appear above them
    for action in actions:
        if action.get("action") != "connect":
            continue

        start = float(action.get("start_seconds", 0))
        duration = max(float(action.get("duration_seconds", 1)), 0.01)

        if not start <= scene_time <= start + duration:
            continue

        source_box = boxes.get(action.get("object_id"))

        if not source_box or len(boxes) < 2:
            continue

        source_x, source_y = source_box[:2]

        other_boxes = [
            box for key, box in boxes.items()
            if key != action.get("object_id")
        ]

        target_box = min(
            other_boxes,
            key=lambda box: (
                (box[0] - source_x) ** 2
                + (box[1] - source_y) ** 2
            ),
        )

        progress = ease((scene_time - start) / duration)

        target_x = source_x + (target_box[0] - source_x) * progress
        target_y = source_y + (target_box[1] - source_y) * progress

        draw_arrow(
            draw,
            source_x,
            source_y,
            target_x,
            target_y,
            (100, 205, 235),
            5,
        )

    # Draw the actual educational objects
    for obj in scene.get("visual_objects", []):
        if not isinstance(obj, dict):
            continue

        box = boxes.get(obj.get("id"))

        if box is None:
            continue

        highlighted = is_highlighted(
            obj.get("id"),
            scene_time,
            actions,
        )

        draw_visual_object(
            draw,
            obj,
            box,
            highlighted,
        )

    # Short on-screen labels
    labels = scene.get("on_screen_text", [])

    if isinstance(labels, str):
        labels = [labels]

    labels = [str(label)[:25] for label in labels[:4]]

    x_position = 65
    y_position = 585

    for label in labels:
        text_box = draw.textbbox(
            (0, 0),
            label,
            font=label_font,
        )

        label_width = text_box[2] - text_box[0] + 32

        if x_position + label_width > 1215:
            break

        draw.rounded_rectangle(
            (
                x_position,
                y_position,
                x_position + label_width,
                y_position + 45,
            ),
            radius=15,
            fill=(39, 62, 105),
            outline=(85, 135, 210),
            width=2,
        )

        draw.text(
            (x_position + 16, y_position + 10),
            label,
            font=label_font,
            fill=(235, 245, 255),
        )

        x_position += label_width + 12

    # Footer
    draw.text(
        (65, 660),
        f"LESSON SCENE {scene_number} / {total_scenes}",
        font=small_font,
        fill=(135, 165, 210),
    )

    draw.text(
        (1000, 660),
        "LEARN  •  EXPLORE  •  GROW",
        font=small_font,
        fill=(100, 160, 210),
    )

    image.save(output_path)


# --------------------------------------------------
# AUDIO HELPERS
# --------------------------------------------------

def get_audio_duration(audio_path):
    command = [
        str(FFPROBE_EXE),
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(audio_path),
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=True,
    )

    return float(result.stdout.strip())


# --------------------------------------------------
# RENDER ANIMATED SCENE
# --------------------------------------------------

def render_animated_scene(
    scene,
    scene_number,
    total_scenes,
    temp_folder,
    audio_generator,
):
    narration = str(scene.get("narration", "")).strip()

    if not narration:
        return None

    audio_path = temp_folder / f"scene_{scene_number:03d}.mp3"
    video_path = temp_folder / f"segment_{scene_number:03d}.mp4"

    frames_folder = temp_folder / f"frames_{scene_number:03d}"
    frames_folder.mkdir(parents=True, exist_ok=True)

    print(f"Generating narration for scene {scene_number}...")

    audio_generator(
        narration,
        str(audio_path),
    )

    if not audio_path.exists():
        raise RuntimeError(
            f"Audio was not created for scene {scene_number}."
        )

    duration = get_audio_duration(audio_path)

    if duration <= 0:
        raise RuntimeError(
            f"Invalid audio duration for scene {scene_number}."
        )

    total_frames = max(1, math.ceil(duration * FPS))

    print(
        f"Drawing {total_frames} animation frames "
        f"for scene {scene_number}..."
    )

    for frame_number in range(total_frames):
        scene_time = frame_number / FPS

        frame_path = (
            frames_folder / f"frame_{frame_number:05d}.png"
        )

        create_animation_frame(
            scene,
            scene_number,
            total_scenes,
            scene_time,
            frame_path,
        )

    command = [
        str(FFMPEG_EXE),
        "-y",
        "-framerate", str(FPS),
        "-i", str(frames_folder / "frame_%05d.png"),
        "-i", str(audio_path),
        "-vf", "scale=1280:720,format=yuv420p",
        "-r", "24",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "21",
        "-c:a", "aac",
        "-b:a", "192k",
        "-t", str(duration),
        "-shortest",
        "-movflags", "+faststart",
        str(video_path),
    ]

    subprocess.run(
        command,
        check=True,
    )

    return video_path


# --------------------------------------------------
# COMPLETE VIDEO RENDERING
# --------------------------------------------------

def render_storyboard_video(
    storyboard: dict,
    output_path: str,
    audio_generator,
):
    """
    Render all storyboard scenes and combine them
    with smooth visual crossfade transitions.
    Keep narration continuous and synchronized.
    """

    check_ffmpeg()

    scenes = storyboard.get("scenes", [])

    if not scenes:
        raise RuntimeError(
            "The storyboard contains no scenes."
        )

    output = Path(output_path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as temp_folder:

        temp = Path(temp_folder)
        video_segments = []

        # Render all scenes.
        for index, scene in enumerate(scenes, start=1):
            print(
                f"Processing scene {index}/{len(scenes)}..."
            )

            segment = render_animated_scene(
                scene,
                index,
                len(scenes),
                temp,
                audio_generator,
            )

            if segment is not None:
                video_segments.append(segment)

        if not video_segments:
            raise RuntimeError(
                "No scenes with narration were available to render."
            )

        # Read the actual duration of every scene.
        durations = []

        for segment in video_segments:
            probe_command = [
                str(FFPROBE_EXE),
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(segment),
            ]

            result = subprocess.run(
                probe_command,
                capture_output=True,
                text=True,
                check=True,
            )

            duration = float(result.stdout.strip())

            if duration <= 0:
                raise RuntimeError(
                    f"Invalid video duration: {segment.name}"
                )

            durations.append(duration)

        filter_parts = []

        # Normalize all video streams.
        for index in range(len(video_segments)):
            filter_parts.append(
                f"[{index}:v]"
                "fps=24,"
                "scale=1280:720,"
                "setsar=1,"
                "format=yuv420p,"
                "settb=AVTB,"
                "setpts=PTS-STARTPTS"
                f"[v{index}]"
            )

        # Normalize all audio streams.
        for index in range(len(video_segments)):
            filter_parts.append(
                f"[{index}:a]"
                "aresample=48000,"
                "aformat=sample_fmts=fltp:"
                "sample_rates=48000:"
                "channel_layouts=stereo,"
                "asetpts=PTS-STARTPTS"
                f"[a{index}]"
            )

        if len(video_segments) == 1:

            filter_parts.append(
                "[v0]null[vout]"
            )

            filter_parts.append(
                "[a0]anull[aout]"
            )

        else:

            # Calculate a safe transition duration.
            transition_duration = min(
                0.5,
                min(durations) * 0.25,
            )

            current_duration = durations[0]
            previous_video = "v0"

            # Create crossfade transitions.
            for index in range(1, len(video_segments)):

                offset = (
                    current_duration - transition_duration
                )

                next_video = f"v{index}"

                if index == len(video_segments) - 1:
                    output_label = "vxfade"
                else:
                    output_label = f"blend{index}"

                filter_parts.append(
                    f"[{previous_video}][{next_video}]"
                    f"xfade=transition=fade:"
                    f"duration={transition_duration:.3f}:"
                    f"offset={offset:.3f}"
                    f"[{output_label}]"
                )

                current_duration += (
                    durations[index] - transition_duration
                )

                previous_video = output_label

            # Join narration sequentially without crossfading speech.
            audio_inputs = "".join(
                f"[a{index}]"
                for index in range(len(video_segments))
            )

            filter_parts.append(
                f"{audio_inputs}"
                f"concat=n={len(video_segments)}:v=0:a=1[aout]"
            )

            # Restore the video duration lost during crossfades.
            total_padding = (
                transition_duration
                * (len(video_segments) - 1)
            )

            filter_parts.append(
                f"[vxfade]"
                f"tpad=stop_mode=clone:"
                f"stop_duration={total_padding:.3f}"
                f"[vout]"
            )

        filter_complex = ";".join(filter_parts)

        # Build the final FFmpeg command.
        command = [
            str(FFMPEG_EXE),
            "-y",
        ]

        for segment in video_segments:
            command.extend([
                "-i",
                str(segment),
            ])

        command.extend([
            "-filter_complex",
            filter_complex,
            "-map", "[vout]",
            "-map", "[aout]",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "21",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            str(output),
        ])

        print(
            "Combining scenes with smooth transitions..."
        )

        subprocess.run(
            command,
            check=True,
        )

    print("Final video created successfully!")

    return str(output)
