from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import shutil
import uuid
import time
import subprocess
from api.stabilizer import TranslationStabilizer

app = FastAPI(title="Video Stabilization API")

# Enable CORS for the frontend
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

@app.post("/api/v1/stabilize")
async def stabilize_video(file: UploadFile = File(...)):
    if not file.filename.endswith(('.mp4', '.avi', '.mov')):
        raise HTTPException(status_code=400, detail="Invalid file type. Only mp4, avi, mov allowed.")

    # Generate unique filenames
    job_id = str(uuid.uuid4())
    input_filename = f"{job_id}_{file.filename}"
    input_path = os.path.join(UPLOAD_DIR, input_filename)
    
    # We enforce .mp4 for outputs for browser compatibility
    output_filename = f"{job_id}_stabilized.mp4"
    output_path = os.path.join(OUTPUT_DIR, output_filename)

    # Save uploaded file
    temp_input_path = input_path + "_temp"
    with open(temp_input_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    print(f"Normalizing uploaded video {input_filename} to H.264...")
    try:
        subprocess.run([
            "ffmpeg", "-y", "-i", temp_input_path, 
            "-vcodec", "libx264", input_path
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(temp_input_path):
            os.remove(temp_input_path)
    except Exception as e:
        print(f"FFmpeg conversion failed for input: {e}")
        shutil.move(temp_input_path, input_path)
        
    try:
        # Run stabilization
        # Set realistic values for web demo (faster processing vs perfect quality tradeoff)
        stabilizer = TranslationStabilizer(smoothing_window=30, max_features=300)
        print(f"Starting stabilization for {input_filename}...")
        start_time = time.time()
        
        stabilizer.stabilize(input_path, output_path, crop_ratio=0.90)
        
        print(f"Stabilization completed in {time.time() - start_time:.2f} seconds.")
        
        # In a real async/microservice system this would return a job ID immediately
        # But for this simple web demo, we block and return the actual file path.
        return {
            "status": "success", 
            "original_video_url": f"/api/v1/video/raw/{input_filename}",
            "stabilized_video_url": f"/api/v1/video/processed/{output_filename}"
        }
    except Exception as e:
        print(f"Error stabilizing video: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/video/raw/{filename}")
async def get_raw_video(filename: str):
    file_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Video not found")
    return FileResponse(file_path, media_type="video/mp4")

@app.get("/api/v1/video/processed/{filename}")
async def get_processed_video(filename: str):
    file_path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Video not found")
    return FileResponse(file_path, media_type="video/mp4")

# Mount the frontend static files at the root
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
