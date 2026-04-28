from api.stabilizer import TranslationStabilizer
from datetime import datetime
from api.redis_queue import update_job

def process_video(job_id, input_path, output_path):
    try:
        update_job(job_id, {
            "status": "processing",
            "progress": 0,
            "started_at": str(datetime.utcnow())
        })

        def progress_callback(p):
            update_job(job_id, {
                "progress": p
            })

        stabilizer = TranslationStabilizer(smoothing_window=30, max_features=300)
        stabilizer.stabilize(
            input_path,
            output_path,
            progress_callback=progress_callback
        )

        update_job(job_id, {
            "status": "completed",
            "progress": 100,
            "completed_at": str(datetime.utcnow())
        })

    except Exception as e:
        update_job(job_id, {
            "status": "failed",
            "error": str(e),
            "failed_at": str(datetime.utcnow())
        })