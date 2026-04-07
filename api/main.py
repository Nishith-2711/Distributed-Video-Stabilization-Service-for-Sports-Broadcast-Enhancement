from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import shutil
import uuid
import subprocess
from threading import Thread
from datetime import datetime

from api.stabilizer import TranslationStabilizer

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

# In-memory job store (we will replace with MongoDB later)
jobs = {}


def process_video(job_id, input_path, output_path):
    try:
        jobs[job_id]["status"] = "processing"

        stabilizer = TranslationStabilizer(smoothing_window=30, max_features=300)
        stabilizer.stabilize(input_path, output_path)

        jobs[job_id]["status"] = "completed"
        jobs[job_id]["output"] = output_path
        jobs[job_id]["completed_at"] = str(datetime.utcnow())

    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)


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
    jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "input_video": input_filename,
        "output_video": output_filename,
        "created_at": str(datetime.utcnow()),
    }

    Thread(target=process_video, args=(job_id, input_path, output_path)).start()

    return {
        "job_id": job_id,
        "status": "queued"
    }

@app.get("/api/v1/status/{job_id}")
def get_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]


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

# ==============================
# 🌐 FRONTEND
# ==============================
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")