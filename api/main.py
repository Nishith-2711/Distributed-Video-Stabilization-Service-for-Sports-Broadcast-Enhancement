from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import shutil
import uuid
import subprocess
from datetime import datetime
from api.redis_queue import video_queue, save_job, get_job

app = FastAPI(title="Video Stabilization API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# In-memory job store (temporary fallback cache)
jobs = {}

@app.post("/api/v1/stabilize")
async def stabilize_video(file: UploadFile = File(...)):
    if not file.filename.endswith((".mp4", ".avi", ".mov")):
        raise HTTPException(status_code=400, detail="Invalid file type")

    job_id = str(uuid.uuid4())

    input_filename = f"{job_id}_{file.filename}"
    input_path = os.path.join(UPLOAD_DIR, input_filename)

    output_filename = f"{job_id}_stabilized.mp4"
    output_path = os.path.join(OUTPUT_DIR, output_filename)

    temp_input_path = input_path + "_temp"

    # Save uploaded file
    with open(temp_input_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Normalize to H264
    try:
        subprocess.run([
            "ffmpeg", "-y", "-i", temp_input_path,
            "-vcodec", "libx264", input_path
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        os.remove(temp_input_path)

    except Exception as e:
        print(f"FFmpeg failed: {e}")
        shutil.move(temp_input_path, input_path)

    # Save job metadata
    job_payload = {
        "job_id": job_id,
        "status": "queued",
        "input_video": input_filename,
        "output_video": output_filename,
        "created_at": str(datetime.utcnow()),
    }
    jobs[job_id] = job_payload
    save_job(job_id, job_payload)

    video_queue.enqueue(
        "api.worker.process_video",
        job_id,
        input_path,
        output_path
    )

    return {
        "job_id": job_id,
        "status": "queued"
    }

@app.get("/api/v1/status/{job_id}")
def get_status(job_id: str):
    redis_job = get_job(job_id)
    if redis_job is not None:
        jobs[job_id] = redis_job
        return redis_job

    if job_id in jobs:
        return jobs[job_id]

    raise HTTPException(status_code=404, detail="Job not found")


@app.get("/api/v1/video/raw/{filename}")
def get_raw_video(filename: str):
    file_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Video not found")
    return FileResponse(file_path, media_type="video/mp4")


@app.get("/api/v1/video/processed/{filename}")
def get_processed_video(filename: str):
    file_path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Video not found")
    return FileResponse(file_path, media_type="video/mp4")

@app.get("/")
def test():
    return {"status": "ok"}

# app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")