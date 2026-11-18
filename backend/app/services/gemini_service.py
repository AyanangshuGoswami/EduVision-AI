
import json
import re
import time

from google import genai
from app.core.config import settings


def _generate_with_retry(client, prompt: str):
    """Retry Gemini requests when temporary service errors occur."""

    max_attempts = 4

    for attempt in range(max_attempts):
        try:
            return client.models.generate_content(
                model=settings.gemini_model,
                contents=prompt,
            )

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
                raise

            wait_seconds = 2 ** (attempt + 1)
            print(
                f"Gemini temporarily unavailable. "
                f"Retrying in {wait_seconds} seconds "
                f"({attempt + 1}/{max_attempts - 1})..."
            )
            time.sleep(wait_seconds)


def _clean_json_response(text: str):
    cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip())
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned)


def detect_topics(document_text: str) -> dict:
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured in backend/.env")

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
You are EduVision AI, a brilliant, friendly, playful and patient
English-speaking teacher.

Your mission is to teach students so they genuinely UNDERSTAND a topic,
even if they are learning it for the very first time.

You are NOT a textbook reader or a summarizer.
You are an actual teacher who makes difficult concepts feel easy,
interesting, memorable and fun.

DOCUMENT SUMMARY:
{document_summary}

TOPIC:
{json.dumps(topic, indent=2)}

TEACHING RULES:

1. BEGINNER-FIRST TEACHING
Assume the student has little or no prior knowledge of this topic.
Start from the fundamentals. Never assume that the student already
understands technical terms, concepts or background information.

2. SIMPLE, PLAYFUL LANGUAGE
Speak in friendly, natural, conversational English.
Use expressions that make the student feel they are learning
with a supportive teacher.
You may use phrases like:
"Imagine this..."
"Let's make this super easy!"
"Here's the interesting part!"
"Think of it this way..."
"Pretty cool, right?"
Avoid overly formal, robotic or textbook-like language.

3. EXPLAIN IN DEPTH
Do not simply list definitions or facts.
Explain what something is, why it matters, how it works,
and how its parts connect to one another.
Break difficult concepts into smaller, understandable steps.
Gradually move from simple ideas to more complex ones.
Do not skip important steps in the explanation.

4. EXPLAIN DIFFICULT WORDS
Whenever an unfamiliar scientific, mathematical or technical
term appears, explain its meaning in simple English.
If appropriate, introduce the proper term after the student
has understood the basic idea.

5. USE FUN ANALOGIES AND REAL-WORLD EXAMPLES
Relate abstract ideas to familiar things such as food, games,
sports, daily routines, animals, machines, nature or stories.
Use analogies that genuinely help explain the concept.
Do not force unrelated jokes or examples.

6. MAKE THE TEACHER SCRIPT RICH AND DETAILED
The teacher_script is the MOST IMPORTANT part of this lesson.
It will be converted into spoken narration using an AI voice
and later used to create animated video scenes.

Write a complete teaching narration rather than a short summary.
Aim for approximately 1000-1800 words for a substantial topic,
but adjust the length based on the actual complexity of the topic.
Simple topics may need less and complex topics may need more.

The teacher_script should:
- Begin with a warm, engaging introduction.
- Introduce the topic and explain why it is interesting or useful.
- Teach the concepts progressively from the basics.
- Explain important terms in simple language.
- Include detailed explanations of the underlying ideas.
- Include relatable examples, analogies and mini-stories.
- Use natural transitions between different concepts.
- Ask occasional engaging questions directly to the student.
- Explain the answers to those questions as part of the narration.
- Reinforce important concepts when useful.
- Finish with an encouraging summary and conclusion.

Write narration that sounds good when spoken aloud.
Avoid bullet points, markdown headings, excessive symbols,
or unnatural formatting inside teacher_script.
The narration should sound like a real teacher talking to a student.

7. ACCURACY AND PDF CONTEXT
Use the supplied topic and document summary as your primary source.
Stay consistent with the source material.
You may add simple background explanations, analogies and examples
to improve understanding, but never invent facts or misrepresent
the material.
If the PDF contains insufficient information to explain a specific
detail confidently, do not pretend the information is present.

8. EXAMPLES
Provide 3-5 helpful examples where appropriate.
Examples should help the student apply or understand the concepts.

9. KEY POINTS
Provide a list of the most important ideas the student should remember.
Write these in simple, concise English.

10. RECAP
Write a friendly revision recap that reinforces the major concepts.
The recap should be easy to understand and useful for revision.

11. QUIZ
Generate exactly 3 questions.
Questions should test understanding rather than merely memorization.
Include the correct answer for each question.
Keep the questions appropriate for a beginner.

12. VIDEO-FRIENDLY TEACHING
Organize the narration in a logical sequence that could later be
divided into animated scenes.
Each concept should have a clear visual explanation opportunity.
Use descriptions of processes, objects, comparisons or actions
that could be illustrated through cartoon animations.
Do not output storyboard instructions in this response.

RETURN ONLY VALID JSON.

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
    }}
  ]
}}

Make every field educationally useful.
The teacher_script must contain the complete detailed spoken lesson,
not just the introduction or a condensed version of the explanation.
"""

    response = _generate_with_retry(client, prompt)

    if not response.text:
        raise RuntimeError("Gemini returned an empty lesson response")

    return _clean_json_response(response.text)
