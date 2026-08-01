import json
import os

from google.cloud import tasks_v2
from google.api_core.exceptions import AlreadyExists
from dotenv import load_dotenv

load_dotenv()

PROJECT = "scarceph"
QUEUE = "email-queue"
LOCATION = "asia-southeast1"


def enqueue_email(payload: dict, task_id=None):
    worker_url = os.environ.get("EMAIL_WORKER_URL")
    if not worker_url:
        raise RuntimeError("EMAIL_WORKER_URL is required to enqueue email tasks")

    client = tasks_v2.CloudTasksClient()
    parent = client.queue_path(PROJECT, LOCATION, QUEUE)

    task = {
        "http_request": {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": worker_url,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(payload).encode(),
        }
    }

    if task_id:
        task["name"] = f"{parent}/tasks/{task_id}"

    try:
        response = client.create_task(
            parent=parent,
            task=task
        )
    except AlreadyExists:
        if not task_id:
            raise
        return task["name"]

    return response.name
