from datetime import datetime, timezone

from api.redis_queue import update_job
from api.stabilizer import TranslationStabilizer


def process_video(job_id, input_path, output_path):
    try:
        update_job(job_id, {
            "status": "processing",
            "progress": 0,
            "started_at": str(datetime.now(timezone.utc))
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
            "completed_at": str(datetime.now(timezone.utc))
        })

    except Exception as e:  # noqa: BLE001
        update_job(job_id, {
            "status": "failed",
            "error": str(e),
            "failed_at": str(datetime.now(timezone.utc))
        })