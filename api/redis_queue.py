import json
import os

import redis
from rq import Queue
from rq.worker import SimpleWorker

redis_host = os.environ.get("REDIS_HOST", "localhost")
redis_conn = redis.Redis(host=redis_host, port=6379)

video_queue = Queue(
    "video-processing",
    connection=redis_conn,
    default_worker_class=SimpleWorker
)


def _job_key(job_id: str) -> str:
    return f"video-job:{job_id}"


def save_job(job_id: str, payload: dict) -> None:
    """
    Turns the Python dictionary into a string and saves it in Redis
    """
    redis_conn.set(_job_key(job_id), json.dumps(payload))


def get_job(job_id: str):
    """
    Looks up the key in Redis. If it finds text, it converts text to a Python dictionary
    """
    raw_value = redis_conn.get(_job_key(job_id))
    if raw_value is None:
        return None
    return json.loads(raw_value)


def update_job(job_id: str, updates: dict):
    """
    Retrieves the current job data using get_job(), updates the specific fields you provide, and then saves the result back to Redis.
    """
    current = get_job(job_id)
    if current is None:
        current = {"job_id": job_id}
    current.update(updates)
    save_job(job_id, current)
    return current

def list_jobs():
    """
    Looks for any key in Redis that starts with video-job:
    """
    keys = redis_conn.keys("video-job:*")
    jobs = []

    for key in keys:
        raw = redis_conn.get(key)
        if raw:
            jobs.append(json.loads(raw))

    return jobs