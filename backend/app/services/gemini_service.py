
import json
import re
import time
from collections import OrderedDict

from google import genai
from google.genai import types

from app.core.config import settings


# Maximum text sent to Gemini in one analysis request.
# The complete PDF is analyzed across multiple chunks.
ANALYSIS_CHUNK_CHARS = 25000


def _generate_with_retry(client, prompt, config=None):
    """Retry temporary Gemini errors without changing existing callers."""

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
    """Parse a Gemini JSON response, tolerating surrounding code fences."""

    if not text or not text.strip():
        raise ValueError("Gemini returned an empty JSON response.")

    cleaned = text.strip()

    cleaned = re.sub(
        r"^```(?:json)?\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    cleaned = re.sub(r"\s*```$", "", cleaned)

    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start == -1 or end == -1 or end < start:
        raise ValueError(
            "Gemini did not return a complete JSON object. "
            f"Response preview: {cleaned[:500]}"
        )

    cleaned = cleaned[start:end + 1]

    try:
        result = json.loads(cleaned)

        if not isinstance(result, dict):
            raise ValueError("Gemini response must be a JSON object.")

        return result

    except json.JSONDecodeError as exc:
        raise ValueError(
            "Gemini returned invalid JSON. "
            f"Error at line {exc.lineno}, column {exc.colno}. "
            f"Response preview: {cleaned[:500]}"
        ) from exc


def _split_document_into_chunks(
    document_text: str,
    max_chars: int = ANALYSIS_CHUNK_CHARS,
) -> list[str]:
    """
    Split PDF text into manageable chunks.

    Prefer page boundaries so that page references remain meaningful.
    Very large individual pages are split into smaller sections.
    """

    page_pattern = re.compile(
        r"(?m)^\[PAGE\s+(\d+)\]\s*$"
    )

    matches = list(page_pattern.finditer(document_text))

    # Fallback for text without page markers.
    if not matches:
        return [
            document_text[index:index + max_chars]
            for index in range(0, len(document_text), max_chars)
        ]

    pages = []

    for index, match in enumerate(matches):
        start = match.start()
        end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(document_text)
        )

        page_number = match.group(1)
        page_content = document_text[match.end():end].strip()

        pages.append(
            f"[PAGE {page_number}]\n{page_content}"
        )

    chunks = []
    current_chunk = ""

    for page in pages:
        # Split an unusually large page into smaller pieces.
        if len(page) > max_chars:
            if current_chunk.strip():
                chunks.append(current_chunk.strip())
                current_chunk = ""

            page_header_match = re.match(
                r"^\[PAGE\s+(\d+)\]\s*",
                page,
            )

            if page_header_match:
                page_number = page_header_match.group(1)
                page_content = page[page_header_match.end():]

                content_limit = max(
                    1,
                    max_chars - len(f"[PAGE {page_number}]\n"),
                )

                for start in range(0, len(page_content), content_limit):
                    section = page_content[start:start + content_limit]

                    chunks.append(
                        f"[PAGE {page_number}]\n{section}"
                    )
            else:
                for start in range(0, len(page), max_chars):
                    chunks.append(page[start:start + max_chars])

            continue

        proposed_chunk = (
            f"{current_chunk}\n\n{page}"
            if current_chunk
            else page
        )

        if len(proposed_chunk) > max_chars:
            if current_chunk.strip():
                chunks.append(current_chunk.strip())

            current_chunk = page
        else:
            current_chunk = proposed_chunk

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks


def _analyze_document_chunk(
    client,
    chunk_text: str,
    chunk_number: int,
    total_chunks: int,
) -> dict:
    """Analyze one section of the PDF."""

    prompt = f"""
You are an expert educational instructional designer and document analyst.

You are analyzing section {chunk_number} of {total_chunks}
of a larger educational PDF.

Your task is to identify the actual educational content in this section.

Be comprehensive. Do not identify only the biggest chapter headings.
Find the meaningful topics, smaller topics, concepts, methods,
processes, and important ideas that a student should learn.

IMPORTANT RULES:

1. Use only information supported by the supplied PDF section.
2. Do not invent topics, formulas, examples, or claims.
3. Preserve the order in which topics appear in the document.
4. Identify smaller subtopics rather than grouping everything
   into a few overly broad topics.
5. Use clear, beginner-friendly topic titles.
6. Write useful descriptions explaining what each topic teaches.
7. Include the actual page numbers shown in the supplied text.
8. If a topic continues across several pages, include all relevant
   page numbers that are visible in this section.
9. Do not confuse an example with a separate major topic.
10. Do not omit important technical concepts simply because
    they are difficult.

Return ONLY valid JSON in this structure:

{{
  "document_title": "document title if identifiable",
  "summary": "summary of this section",
  "topics": [
    {{
      "title": "specific topic title",
      "description": "clear explanation of what this topic covers",
      "source_pages": [1, 2],
      "subtopics": [
        "specific subtopic one",
        "specific subtopic two"
      ]
    }}
  ]
}}

If no meaningful topics are present in this section,
return an empty topics array.

PDF SECTION:

{chunk_text}
"""

    response = _generate_with_retry(client, prompt)

    if not response.text:
        raise RuntimeError(
            f"Gemini returned an empty response for section {chunk_number}."
        )

    return _clean_json_response(response.text)


def _normalize_title(title: str) -> str:
    """Create a comparable version of a topic title."""

    return re.sub(
        r"[^a-z0-9]+",
        " ",
        str(title).lower(),
    ).strip()


def _merge_chunk_analyses(analyses: list[dict]) -> dict:
    """
    Merge chunk results without discarding topics.

    Topics with exactly matching normalized titles are combined.
    Page numbers and subtopics are preserved.
    """

    merged_topics = OrderedDict()

    document_title = ""
    summaries = []

    for analysis in analyses:
        if not document_title:
            document_title = str(
                analysis.get("document_title", "")
            ).strip()

        summary = str(analysis.get("summary", "")).strip()

        if summary:
            summaries.append(summary)

        topics = analysis.get("topics", [])

        if not isinstance(topics, list):
            continue

        for topic in topics:
            if not isinstance(topic, dict):
                continue

            title = str(topic.get("title", "")).strip()

            if not title:
                continue

            normalized_title = _normalize_title(title)

            if not normalized_title:
                continue

            description = str(
                topic.get("description", "")
            ).strip()

            source_pages = topic.get("source_pages", [])
            subtopics = topic.get("subtopics", [])

            if not isinstance(source_pages, list):
                source_pages = []

            if not isinstance(subtopics, list):
                subtopics = []

            if normalized_title not in merged_topics:
                merged_topics[normalized_title] = {
                    "title": title,
                    "description": description,
                    "source_pages": [],
                    "subtopics": [],
                }

            existing = merged_topics[normalized_title]

            # Preserve useful descriptions from different chunks.
            if description and description not in existing["description"]:
                if not existing["description"]:
                    existing["description"] = description
                else:
                    existing["description"] += " " + description

            # Merge page numbers without duplicates.
            for page in source_pages:
                try:
                    page_number = int(page)

                    if page_number not in existing["source_pages"]:
                        existing["source_pages"].append(page_number)

                except (TypeError, ValueError):
                    continue

            # Merge subtopics without duplicates.
            existing_subtopics = {
                _normalize_title(item)
                for item in existing["subtopics"]
            }

            for subtopic in subtopics:
                if not isinstance(subtopic, str):
                    continue

                subtopic = subtopic.strip()
                normalized_subtopic = _normalize_title(subtopic)

                if (
                    subtopic
                    and normalized_subtopic
                    and normalized_subtopic not in existing_subtopics
                ):
                    existing["subtopics"].append(subtopic)
                    existing_subtopics.add(normalized_subtopic)

    final_topics = list(merged_topics.values())

    for topic in final_topics:
        topic["source_pages"].sort()

    # Keep the summaries from all sections.
    combined_summary = " ".join(summaries)

    return {
        "document_title": document_title or "Untitled Document",
        "summary": combined_summary,
        "topics": final_topics,
    }


def detect_topics(document_text: str) -> dict:
    """
    Analyze the complete PDF using multiple Gemini requests.

    The input is split into page-based chunks. Each chunk is analyzed
    separately, and the resulting topics are merged.
    """

    if not settings.gemini_api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured in backend/.env"
        )

    if not document_text or not document_text.strip():
        raise ValueError("The PDF does not contain extractable text.")

    print("Gemini model:", settings.gemini_model)
    print("Gemini API key configured:", bool(settings.gemini_api_key))

    chunks = _split_document_into_chunks(document_text)

    if not chunks:
        raise ValueError("Could not divide the PDF into analysis sections.")

    print(f"PDF analysis started: {len(chunks)} section(s).")

    client = genai.Client(api_key=settings.gemini_api_key)

    analyses = []

    for index, chunk in enumerate(chunks, start=1):
        print(
            f"Analyzing PDF section {index}/{len(chunks)} "
            f"({len(chunk)} characters)..."
        )

        analysis = _analyze_document_chunk(
            client,
            chunk,
            index,
            len(chunks),
        )

        analyses.append(analysis)

        print(
            f"Section {index}/{len(chunks)} completed. "
            f"Topics found: {len(analysis.get('topics', []))}"
        )

        if index < len(chunks):
            time.sleep(1)

    final_analysis = _merge_chunk_analyses(analyses)

    print(
        "PDF analysis completed. "
        f"Total merged topics: {len(final_analysis['topics'])}"
    )

    return final_analysis


def detect_topics_from_pages(pages: list[dict]) -> dict:
    """
    Analyze PDF pages using both extracted text and rendered images.

    Processes four pages per Gemini request.
    """

    if not settings.gemini_api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured in backend/.env"
        )

    if not pages:
        raise ValueError("No PDF pages were supplied for analysis.")

    client = genai.Client(api_key=settings.gemini_api_key)

    pages_per_group = 4
    analyses = []

    total_groups = (
        len(pages) + pages_per_group - 1
    ) // pages_per_group

    print(
        f"Starting visual PDF analysis: "
        f"{len(pages)} pages in {total_groups} groups."
    )

    for group_index in range(total_groups):
        group = pages[
            group_index * pages_per_group:
            (group_index + 1) * pages_per_group
        ]

        # IMPORTANT:
        # Prepare this text BEFORE creating the f-string.
        # This avoids the Python 3.11 f-string backslash SyntaxError.
        extracted_pages_text = "\n".join(
            [
                "[PAGE " + str(page["page_number"]) + "]\n"
                + page.get("text", "")
                for page in group
            ]
        )

        prompt = f"""
You are an expert educational document analyst.

Analyze ALL supplied PDF slides carefully, using BOTH:
1. The extracted selectable text.
2. The actual rendered slide images.

Your goal is to identify EVERY meaningful educational topic
and subtopic. Do not reduce a detailed lecture into a few
broad chapter headings.

IMPORTANT INSTRUCTIONS:

- Inspect every supplied page image.
- Read headings, subheadings, diagram labels, formulas,
  captions, examples and visible text.
- Do not ignore information merely because it appears
  inside a diagram or image.
- Identify distinct concepts as separate teachable topics.
- Preserve the original order of the PDF.
- Do not combine different concepts into one broad topic.
- A major concept can be a topic even if it occupies only
  one slide.
- Include meaningful methods, architectures, advantages,
  limitations, problems, experiments and solutions.
- Keep related details as subtopics when appropriate.
- Do not invent information.
- Include the exact PDF page numbers.
- Avoid duplicate topics within this group.

For every topic, provide:
- A specific and informative title.
- A useful description of what the student will learn.
- All relevant PDF page numbers.
- Its important subtopics.

Do not create a separate topic for every individual sentence.
However, do not merge genuinely different technical concepts.

Return ONLY valid JSON:

{{
  "document_title": "document title",
  "summary": "detailed summary of these pages",
  "topics": [
    {{
      "title": "specific educational topic",
      "description": "what the student will learn",
      "source_pages": [1, 2],
      "subtopics": [
        "specific concept",
        "another specific concept"
      ]
    }}
  ]
}}

EXTRACTED TEXT FROM THESE PAGES:

{extracted_pages_text}
"""

        # Gemini receives the text prompt followed by each page's
        # page-number label and corresponding rendered image.
        contents = [prompt]

        for page in group:
            page_number = page.get("page_number", "Unknown")

            contents.append(
                f"Rendered image of PDF page {page_number} follows."
            )

            image_data = page.get("image")

            if image_data:
                contents.append(
                    types.Part.from_bytes(
                        data=image_data,
                        mime_type="image/png",
                    )
                )

        print(
            f"Analyzing visual group "
            f"{group_index + 1}/{total_groups}..."
        )

        response = _generate_with_retry(client, contents)

        if not response.text:
            raise RuntimeError(
                f"Gemini returned an empty response "
                f"for group {group_index + 1}."
            )

        analysis = _clean_json_response(response.text)
        analyses.append(analysis)

        print(
            f"Group {group_index + 1} completed. "
            f"Topics found: {len(analysis.get('topics', []))}"
        )

        if group_index < total_groups - 1:
            time.sleep(1)

    final_analysis = _merge_chunk_analyses(analyses)

    print(
        "Visual PDF analysis completed. "
        f"Topics found: {len(final_analysis['topics'])}"
    )

    return final_analysis


def generate_topic_lesson(topic: dict, document_summary: str = "") -> dict:
    """Generate a detailed, beginner-friendly English lesson."""

    if not settings.gemini_api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured in backend/.env"
        )

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
