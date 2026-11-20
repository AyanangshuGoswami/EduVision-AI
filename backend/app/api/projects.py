
from datetime import datetime, timezone
import asyncio
from pathlib import Path
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.core.config import settings
from app.db.mongo import get_database
from app.services.pdf_service import extract_pdf_text
from app.services.gemini_service import detect_topics, generate_topic_lesson
from app.services.fish_audio_service import generate_audio
from app.services.video_service import (
    generate_storyboard,
    render_storyboard_video,
)

router = APIRouter(prefix="/projects", tags=["projects"])


class AudioRequest(BaseModel):
    text: str


class StoryboardRequest(BaseModel):
    lesson: dict


PDF_MAGIC = b"%PDF"


def serialize_project(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]),
        "title": doc.get("title", "Untitled PDF"),
        "original_filename": doc.get("original_filename", ""),
        "status": doc.get("status", "uploaded"),
        "created_at": doc["created_at"].isoformat(),
        "page_count": doc.get("page_count"),
        "topics": doc.get("topics", []),
        "summary": doc.get("summary"),
    }


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_pdf(file: UploadFile = File(...)):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=415, detail="Please upload a PDF file.")

    contents = await file.read()

    if not contents:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    if len(contents) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"PDF exceeds {settings.max_upload_mb} MB."
        )

    if not contents.startswith(PDF_MAGIC):
        raise HTTPException(
            status_code=400,
            detail="The file does not appear to be a valid PDF."
        )

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    stored_path = upload_dir / f"{uuid4().hex}.pdf"
    stored_path.write_bytes(contents)

    try:
        page_count, _ = extract_pdf_text(stored_path)
    except Exception:
        stored_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Could not read this PDF.")

    now = datetime.now(timezone.utc)

    doc = {
        "title": Path(file.filename or "Untitled PDF").stem[:120],
        "original_filename": file.filename or "document.pdf",
        "stored_path": str(stored_path),
        "status": "uploaded",
        "page_count": page_count,
        "created_at": now,
        "updated_at": now,
        "topics": [],
    }

    result = await get_database().projects.insert_one(doc)
    doc["_id"] = result.inserted_id

    return serialize_project(doc)


@router.get("")
async def list_projects():
    cursor = get_database().projects.find({}).sort("created_at", -1).limit(50)
    return [serialize_project(doc) async for doc in cursor]


@router.get("/{project_id}")
async def get_project(project_id: str):
    if not ObjectId.is_valid(project_id):
        raise HTTPException(status_code=400, detail="Invalid project ID.")

    doc = await get_database().projects.find_one(
        {"_id": ObjectId(project_id)}
    )

    if not doc:
        raise HTTPException(status_code=404, detail="Project not found.")

    return serialize_project(doc)


@router.post("/{project_id}/analyze")
async def analyze_project(project_id: str):
    if not ObjectId.is_valid(project_id):
        raise HTTPException(status_code=400, detail="Invalid project ID.")

    db = get_database()
    doc = await db.projects.find_one({"_id": ObjectId(project_id)})

    if not doc:
        raise HTTPException(status_code=404, detail="Project not found.")

    try:
        page_count, extracted_text = extract_pdf_text(doc["stored_path"])

        if not extracted_text.strip():
            raise HTTPException(
                status_code=422,
                detail="No selectable text found. OCR for scanned PDFs is not enabled yet.",
            )

        analysis = await asyncio.to_thread(
            detect_topics,
            extracted_text[:settings.max_analysis_chars]
        )

        await db.projects.update_one(
            {"_id": ObjectId(project_id)},
            {"$set": {
                "status": "analyzed",
                "page_count": page_count,
                "summary": analysis.get("summary", ""),
                "topics": analysis.get("topics", []),
                "document_title": analysis.get("document_title", ""),
                "updated_at": datetime.now(timezone.utc),
            }},
        )

        updated = await db.projects.find_one(
            {"_id": ObjectId(project_id)}
        )

        return serialize_project(updated)

    except HTTPException:
        raise

    except Exception as exc:
        await db.projects.update_one(
            {"_id": ObjectId(project_id)},
            {"$set": {
                "status": "analysis_failed",
                "last_error": str(exc)
            }},
        )

        raise HTTPException(
            status_code=502,
            detail=f"Analysis failed: {exc}"
        )


@router.post("/{project_id}/topics/{topic_index}/lesson")
async def generate_lesson_for_topic(project_id: str, topic_index: int):
    if not ObjectId.is_valid(project_id):
        raise HTTPException(status_code=400, detail="Invalid project ID.")

    db = get_database()
    doc = await db.projects.find_one({"_id": ObjectId(project_id)})

    if not doc:
        raise HTTPException(status_code=404, detail="Project not found.")

    topics = doc.get("topics", [])

    if topic_index < 0 or topic_index >= len(topics):
        raise HTTPException(status_code=404, detail="Topic not found.")

    topic = topics[topic_index]

    try:
        lesson = await asyncio.to_thread(
            generate_topic_lesson,
            topic,
            doc.get("summary", "")
        )

        return lesson

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Lesson generation failed: {exc}"
        )


@router.post("/{project_id}/topics/{topic_index}/audio")
async def generate_audio_for_topic(
    project_id: str,
    topic_index: int,
    request: AudioRequest
):
    if not ObjectId.is_valid(project_id):
        raise HTTPException(status_code=400, detail="Invalid project ID.")

    db = get_database()
    doc = await db.projects.find_one({"_id": ObjectId(project_id)})

    if not doc:
        raise HTTPException(status_code=404, detail="Project not found.")

    topics = doc.get("topics", [])

    if topic_index < 0 or topic_index >= len(topics):
        raise HTTPException(status_code=404, detail="Topic not found.")

    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Audio text cannot be empty.")

    audio_dir = Path(settings.upload_dir) / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    audio_path = audio_dir / f"{uuid4().hex}.mp3"

    try:
        await asyncio.to_thread(
            generate_audio,
            request.text,
            str(audio_path)
        )

        return FileResponse(
            path=str(audio_path),
            media_type="audio/mpeg",
            filename="lesson.mp3"
        )

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Audio generation failed: {exc}"
        )


@router.post("/{project_id}/topics/{topic_index}/storyboard")
async def generate_storyboard_for_topic(
    project_id: str,
    topic_index: int,
    request: StoryboardRequest
):
    if not ObjectId.is_valid(project_id):
        raise HTTPException(status_code=400, detail="Invalid project ID.")

    db = get_database()
    doc = await db.projects.find_one({"_id": ObjectId(project_id)})

    if not doc:
        raise HTTPException(status_code=404, detail="Project not found.")

    topics = doc.get("topics", [])

    if topic_index < 0 or topic_index >= len(topics):
        raise HTTPException(status_code=404, detail="Topic not found.")

    if not request.lesson.get("teacher_script"):
        raise HTTPException(
            status_code=400,
            detail="A lesson with teacher narration is required."
        )

    try:
        storyboard = await asyncio.to_thread(
            generate_storyboard,
            topics[topic_index],
            request.lesson
        )

        await db.projects.update_one(
            {"_id": ObjectId(project_id)},
            {
                "$set": {
                    f"topics.{topic_index}.storyboard": storyboard,
                    "updated_at": datetime.now(timezone.utc),
                }
            }
        )

        return storyboard

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Storyboard generation failed: {exc}"
        )


@router.post("/{project_id}/topics/{topic_index}/video")
async def generate_video_for_topic(project_id: str, topic_index: int):
    if not ObjectId.is_valid(project_id):
        raise HTTPException(status_code=400, detail="Invalid project ID.")

    db = get_database()
    project_object_id = ObjectId(project_id)

    doc = await db.projects.find_one({"_id": project_object_id})

    if not doc:
        raise HTTPException(status_code=404, detail="Project not found.")

    topics = doc.get("topics", [])

    if topic_index < 0 or topic_index >= len(topics):
        raise HTTPException(status_code=404, detail="Topic not found.")

    storyboard = topics[topic_index].get("storyboard")

    if not storyboard or not storyboard.get("scenes"):
        raise HTTPException(
            status_code=400,
            detail="Please generate the storyboard before generating the video."
        )

    video_dir = Path(settings.upload_dir) / "videos"
    video_dir.mkdir(parents=True, exist_ok=True)

    video_path = video_dir / f"{uuid4().hex}.mp4"

    try:
        await asyncio.to_thread(
            render_storyboard_video,
            storyboard,
            str(video_path),
            generate_audio,
        )

        await db.projects.update_one(
            {"_id": project_object_id},
            {
                "$set": {
                    f"topics.{topic_index}.video_path": str(video_path),
                    f"topics.{topic_index}.video_generated_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
            }
        )

        return FileResponse(
            path=str(video_path),
            media_type="video/mp4",
            filename=f"eduvision_topic_{topic_index + 1}.mp4",
        )

    except Exception as exc:
        video_path.unlink(missing_ok=True)

        raise HTTPException(
            status_code=502,
            detail=f"Video generation failed: {exc}"
        )


@router.get("/{project_id}/topics/{topic_index}/video")
async def download_topic_video(project_id: str, topic_index: int):
    if not ObjectId.is_valid(project_id):
        raise HTTPException(status_code=400, detail="Invalid project ID.")

    db = get_database()
    doc = await db.projects.find_one({"_id": ObjectId(project_id)})

    if not doc:
        raise HTTPException(status_code=404, detail="Project not found.")

    topics = doc.get("topics", [])

    if topic_index < 0 or topic_index >= len(topics):
        raise HTTPException(status_code=404, detail="Topic not found.")

    video_path = topics[topic_index].get("video_path")

    if not video_path or not Path(video_path).is_file():
        raise HTTPException(status_code=404, detail="Video has not been generated yet.")

    return FileResponse(
        path=video_path,
        media_type="video/mp4",
        filename=f"eduvision_topic_{topic_index + 1}.mp4",
    )
