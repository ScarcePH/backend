import json
import os

from google.cloud import tasks_v2
from dotenv import load_dotenv

load_dotenv()

PROJECT = "scarceph"
QUEUE = "ocr-queue"
LOCATION = "asia-southeast1"


def enqueue_ocr(job_id: str, image_path: str):
    worker_url = os.environ.get("OCR_WORKER_URL")
    if not worker_url:
        raise RuntimeError("OCR_WORKER_URL is required to enqueue OCR tasks")

    client = tasks_v2.CloudTasksClient()
    parent = client.queue_path(PROJECT, LOCATION, QUEUE)

    payload = {
        "job_id": job_id,
        "image_path": image_path,
    }

    task = {
        "http_request": {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": worker_url,
            "headers": {
                "Content-Type": "application/json"
            },
            "body": json.dumps(payload).encode(),
        }
    }

    response = client.create_task(
        parent=parent,
        task=task
    )

    return response.name
