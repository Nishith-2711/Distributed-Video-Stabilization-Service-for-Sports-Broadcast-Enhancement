import redis
from rq import Queue
from rq.worker import SimpleWorker
import json

redis_conn = redis.Redis(host="localhost", port=6379)

video_queue = Queue(
    "video-processing",
    connection=redis_conn,
    default_worker_class=SimpleWorker
)


def _job_key(job_id: str) -> str:
    return f"video-job:{job_id}"


def save_job(job_id: str, payload: dict) -> None:
    redis_conn.set(_job_key(job_id), json.dumps(payload))


def get_job(job_id: str):
    raw_value = redis_conn.get(_job_key(job_id))
    if raw_value is None:
        return None
    return json.loads(raw_value)


def update_job(job_id: str, updates: dict):
    current = get_job(job_id)
    if current is None:
        current = {"job_id": job_id}
    current.update(updates)
    save_job(job_id, current)
    return current