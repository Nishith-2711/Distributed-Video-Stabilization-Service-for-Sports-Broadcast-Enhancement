from api.stabilizer import TranslationStabilizer
from datetime import datetime
from api.redis_queue import update_job

def process_video(job_id, input_path, output_path):
    try:
        update_job(job_id, {
            "status": "processing",
            "started_at": str(datetime.utcnow())
        })
        print(f"[JOB {job_id}] started")

        stabilizer = TranslationStabilizer(smoothing_window=30, max_features=300)
        stabilizer.stabilize(input_path, output_path)

        update_job(job_id, {
            "status": "completed",
            "completed_at": str(datetime.utcnow())
        })
        print(f"[JOB {job_id}] completed")

    except Exception as e:
        update_job(job_id, {
            "status": "failed",
            "error": str(e),
            "failed_at": str(datetime.utcnow())
        })
        print(f"[JOB {job_id}] failed: {e}")