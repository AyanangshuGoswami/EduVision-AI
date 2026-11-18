# EduVision AI — Starter

React + Vite frontend and FastAPI backend starter.

Included:
- React dashboard, PDF upload, project list and AI topic-analysis action
- FastAPI health, upload, list, get and Gemini analysis endpoints
- MongoDB with PyMongo's async client
- PDF text extraction using PyMuPDF
- Gemini integration using Google's `google-genai` SDK
- Environment configuration and CORS

This is the foundation, not the complete video generator. HeyGen, Celery/Redis,
slide rendering, TTS and FFmpeg are planned next.

## Requirements
- Node.js 20.19+ or 22.12+
- Python 3.11+
- MongoDB local or Atlas
- Optional Gemini API key

## MongoDB
```bash
docker run --name eduvision-mongo -p 27017:27017 -d mongo:8
```

## Backend
```bash
cd backend
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
# Copy .env.example to .env and configure it
uvicorn app.main:app --reload --port 8000
```
API docs: http://localhost:8000/docs

## Frontend
```bash
cd frontend
npm install
# Copy .env.example to .env
npm run dev
```
Open http://localhost:5173

## Gemini
Set `GEMINI_API_KEY` in `backend/.env`. Upload/list work without it;
the Analyze PDF action requires it.

## API
- `GET /api/health`
- `POST /api/projects/upload` (multipart field `file`)
- `GET /api/projects`
- `GET /api/projects/{project_id}`
- `POST /api/projects/{project_id}/analyze`

## Before production
Local `uploads/` is development-only. Add authentication, per-user access
controls, private object storage, rate limits, malware scanning, retention
policies and asynchronous jobs. Large PDFs need chunked processing. This
starter limits analysis input to a configurable number of characters.
