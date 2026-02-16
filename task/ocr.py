import json
from google.cloud import tasks_v2
import os
from dotenv import load_dotenv
load_dotenv()

client = tasks_v2.CloudTasksClient()

PROJECT = "scarceph"
QUEUE = "ocr-queue"
LOCATION = "asia-southeast1"
WORKER_URL = os.environ["OCR_WORKER_URL"]


def enqueue_ocr(job_id: str, image_path: str):

    parent = client.queue_path(PROJECT, LOCATION, QUEUE)

    payload = {
        "job_id": job_id,
        "image_path": image_path,
    }

    task = {
        "http_request": {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": WORKER_URL,
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
