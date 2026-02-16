import json
from google.cloud import tasks_v2
from dotenv import load_dotenv
load_dotenv()
import os

PROJECT = "scarceph"
QUEUE = "email-queue"
LOCATION = "asia-southeast1"

WORKER_URL =  os.environ.get("EMAIL_WORKER_URL")

client = tasks_v2.CloudTasksClient()


def enqueue_email(payload: dict):

    parent = client.queue_path(PROJECT, LOCATION, QUEUE)

    task = {
        "http_request": {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": WORKER_URL,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(payload).encode(),
        }
    }

    response = client.create_task(
        parent=parent,
        task=task
    )

    return response.name
