import json
import re
import time

from google import genai
from app.core.config import settings



def _generate_with_retry(client, prompt: str, config=None):
    """Retry temporary Gemini errors without making users wait too long.

    The optional config argument lets specific tasks, such as storyboard
    generation, request JSON output without changing existing callers.
    """

    max_attempts = 2

    for attempt in range(max_attempts):
        try:
            print(
                f"Sending request to Gemini "
                f"using {settings.gemini_model}..."
            )

            request_options = {
                "model": settings.gemini_model,
                "contents": prompt,
            }

            if config is not None:
                request_options["config"] = config

            response = client.models.generate_content(**request_options)

            print("Gemini response received successfully.")
            return response

        except Exception as exc:
            error_text = str(exc).upper()

            temporary_error = any(
                marker in error_text
                for marker in [
                    "503",
                    "UNAVAILABLE",
                    "429",
                    "RESOURCE_EXHAUSTED",
                    "500",
                    "INTERNAL",
                    "502",
                    "504",
                    "TIMEOUT",
                ]
            )

            if not temporary_error or attempt == max_attempts - 1:
                print(f"Gemini request failed: {exc}")
                raise

            print(
                "Gemini is temporarily unavailable. "
                "Retrying once in 5 seconds..."
            )

            time.sleep(5)




def _clean_json_response(text: str):
    """Parse a Gemini JSON response, tolerating surrounding code fences/text."""

    if not text or not text.strip():
        raise ValueError("Gemini returned an empty JSON response.")

    cleaned = text.strip()

    # Remove Markdown code fences if Gemini includes them.
    cleaned = re.sub(
        r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE
    )
    cleaned = re.sub(r"\s*```$", "", cleaned)

    # Extract the JSON object if explanatory text surrounds it.
    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start == -1 or end == -1 or end < start:
        raise ValueError(
            "Gemini did not return a complete JSON object. "
            f"Response preview: {cleaned[:500]}"
        )

    cleaned = cleaned[start:end + 1]

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "Gemini returned invalid JSON. "
            f"Error at line {exc.lineno}, column {exc.colno}. "
            f"Response preview: {cleaned[:500]}"
        ) from exc


def detect_topics(document_text: str) -> dict:
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured in backend/.env")
    print("Gemini model:", settings.gemini_model)
    print("Gemini API key configured:", bool(settings.gemini_api_key))
    client = genai.Client(api_key=settings.gemini_api_key)

    prompt = f'''
You are an instructional designer. Analyze this PDF text and identify teaching
topics in order. Do not invent unsupported topics. Return ONLY valid JSON:
{{
  "document_title": "short title",
  "summary": "2-4 sentence summary",
  "topics": [
    {{
      "title": "topic title",
      "description": "brief description",
      "source_pages": [1, 2],
      "subtopics": ["subtopic one", "subtopic two"]
    }}
  ]
}}
Use only page numbers explicitly shown in the supplied text.

PDF TEXT:
{document_text}
'''

    response = _generate_with_retry(client, prompt)

    if not response.text:
        raise RuntimeError("Gemini returned an empty response")

    return _clean_json_response(response.text)


def generate_topic_lesson(topic: dict, document_summary: str = "") -> dict:
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured in backend/.env")

    client = genai.Client(api_key=settings.gemini_api_key)

    prompt = f"""
You are EduVision AI, an excellent, friendly, patient and engaging
English-speaking teacher.

Your job is to make a beginner genuinely understand the topic,
not simply hear information about it.

Imagine you are teaching one student sitting in front of you.
Be warm, clear, encouraging and naturally conversational.

The student may be learning this subject for the first time.
Never assume they already understand technical words or concepts.

DOCUMENT SUMMARY:
{document_summary}

TOPIC:
{json.dumps(topic, indent=2, default=str)}

==================================================
PART 1: HOW TO TEACH
==================================================

Follow this teaching journey in the teacher_script.

STAGE 1 - CREATE CURIOSITY

Begin with a relatable everyday situation, a surprising question,
or a simple example connected to the topic.

Make the student curious about what they are going to learn.

Do not begin with a complicated textbook definition.

STAGE 2 - EXPLAIN THE BASIC IDEA

Introduce the main idea in very simple English.

Explain what it means, why it exists and why it matters.

If a technical term is necessary, first explain the idea in
ordinary language and then introduce the technical term.

STAGE 3 - BUILD UNDERSTANDING STEP BY STEP

Divide complex ideas into small logical steps.

Explain one new idea at a time.

After introducing an idea:
- Explain what it means.
- Explain why it happens or how it works.
- Give a concrete example.
- Connect it to what the student has already learned.

Never suddenly jump to a more advanced concept.

STAGE 4 - DEMONSTRATE WITH EXAMPLES

Use meaningful, specific examples throughout the explanation.

For example, instead of merely saying that a machine learns
patterns, demonstrate what patterns it might learn and how
those patterns help it make a decision.

Whenever possible, show examples as a sequence:

First, what do we start with?
Next, what happens?
Then, what changes?
Finally, what do we learn?

Use everyday analogies involving familiar situations,
objects, food, games, sports or machines when appropriate.

An analogy must clarify the real concept.
Always explain where the analogy connects to the actual topic.

STAGE 5 - CONNECT THE IDEAS

Explain how the different parts of the topic work together.

Use natural transitions such as:
"Now that we understand this, let's see what happens next."
"But there's one more important part."
"Let's connect these two ideas."

Avoid treating every concept as an unrelated definition.

STAGE 6 - CHECK UNDERSTANDING

Occasionally ask the student a simple question.

Give the student a moment to think, then explain the answer
naturally in the narration.

Do not ask questions that require knowledge not yet taught.

STAGE 7 - FINISH WITH CLARITY

End with a friendly explanation of the big picture.

Reinforce the most important ideas and leave the student
feeling confident about what they have learned.

==================================================
PART 2: NARRATION QUALITY
==================================================

The teacher_script is the most important field.

Write a complete, detailed spoken lesson.

For a substantial topic, aim for approximately 1000-1800 words.
Adjust the length to the real complexity of the topic.
Do not add filler just to reach a word count.

The narration must:

- Sound like a real human teacher speaking.
- Use short and understandable sentences.
- Explain unfamiliar words immediately.
- Use specific examples, not vague statements.
- Explain cause and effect.
- Move smoothly from one concept to the next.
- Avoid unnecessary repetition.
- Avoid overly formal academic language.
- Avoid robotic phrases and generic motivational filler.
- Explain mathematical or technical steps when needed.
- Never skip a step that a beginner needs to understand.

Use natural spoken transitions.

Do not include:
- Markdown headings inside teacher_script.
- Bullet points inside teacher_script.
- Stage directions such as "[show animation]".
- Camera instructions.
- Storyboard instructions.
- Unexplained abbreviations.
- Unnecessary symbols that sound awkward when read aloud.

The script will be converted into speech.
It must sound natural when read aloud by an English AI voice.

IMPORTANT:
The narration must explain the actual topic.
Do not let analogies replace the real scientific or technical explanation.

==================================================
PART 3: VIDEO-FRIENDLY EXPLANATION
==================================================

The lesson will later become an animated educational video.

Teach concepts in a way that can be illustrated visually.

Prefer explanations involving:
- Objects appearing and changing.
- Processes unfolding step by step.
- Arrows showing movement or direction.
- Diagrams showing relationships.
- Before-and-after comparisons.
- Cycles and feedback loops.
- Simple graphs when relevant.
- Components connecting to form a system.

For example, when explaining a process, describe the
starting point, the transformation and the final result.

When comparing two ideas, explain them in a way that
makes their differences easy to see.

IMPORTANT VIDEO RULE:

The spoken explanation is the source of truth.

Do not create a separate explanation for the video.
Do not invent a different example for an animation.
Each visual opportunity must directly illustrate
something the teacher has just explained or is explaining.

Keep the concepts in the same order as the narration.

==================================================
PART 4: ACCURACY
==================================================

Use the supplied topic and document summary as the primary source.

Stay faithful to the PDF.

You may add simple background explanations and familiar examples
to help a beginner understand the material.

Never invent technical facts, formulas, research findings,
or claims that contradict the source.

If the source does not provide enough information about
a specific detail, explain only what can be supported.

==================================================
PART 5: OTHER LESSON FIELDS
==================================================

INTRODUCTION:
Write a friendly introduction that makes the student curious.

EXPLANATION:
Provide a clear, detailed explanation of the main concepts.
Use simple language and meaningful examples.

EXAMPLES:
Provide 3-5 specific and useful examples where appropriate.
Avoid repeating the same example in different words.

KEY POINTS:
List the most important things the student should remember.
Keep each point short and easy to understand.

RECAP:
Write a friendly revision recap.
Explain the big picture in simple language.

QUIZ:
Create exactly 3 beginner-friendly questions.
Test understanding and application, not just memorization.
Include a correct and clear answer for each question.

==================================================
FINAL OUTPUT RULES
==================================================

Return ONLY valid JSON.

Use exactly this structure:

{{
  "topic_title": "topic title",
  "introduction": "friendly introduction",
  "explanation": "detailed beginner-friendly explanation",
  "examples": [
    "example 1",
    "example 2",
    "example 3"
  ],
  "key_points": [
    "point 1",
    "point 2"
  ],
  "teacher_script": "complete spoken teaching narration",
  "recap": "friendly revision recap",
  "quiz": [
    {{
      "question": "question",
      "answer": "correct answer"
    }},
    {{
      "question": "question",
      "answer": "correct answer"
    }},
    {{
      "question": "question",
      "answer": "correct answer"
    }}
  ]
}}

The teacher_script must contain the complete spoken lesson.
It must not be a shortened copy of the introduction or explanation.

Every field must be educationally useful.
"""


    response = _generate_with_retry(client, prompt)

    if not response.text:
        raise RuntimeError("Gemini returned an empty lesson response")

    return _clean_json_response(response.text)