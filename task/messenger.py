import json
import os


class TaskEnqueueError(RuntimeError):
    pass


def cloud_tasks_configured():
    required = (
        "GOOGLE_CLOUD_PROJECT",
        "GOOGLE_CLOUD_LOCATION",
        "MESSENGER_TASK_QUEUE",
        "MESSENGER_WORKER_URL",
        "TASKS_SERVICE_ACCOUNT_EMAIL",
    )
    return all(os.environ.get(name) for name in required)


def enqueue_messenger_event(event_id):
    """Enqueue one durable event. Returns False when local sync fallback is needed."""
    if not cloud_tasks_configured():
        return False

    try:
        from google.cloud import tasks_v2
        client = tasks_v2.CloudTasksClient()
        parent = client.queue_path(
            os.environ["GOOGLE_CLOUD_PROJECT"],
            os.environ["GOOGLE_CLOUD_LOCATION"],
            os.environ["MESSENGER_TASK_QUEUE"],
        )
        body = json.dumps({"event_id": event_id}).encode("utf-8")
        task = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": os.environ["MESSENGER_WORKER_URL"],
                "headers": {"Content-Type": "application/json"},
                "body": body,
                "oidc_token": {
                    "service_account_email": os.environ[
                        "TASKS_SERVICE_ACCOUNT_EMAIL"
                    ],
                    "audience": os.environ.get(
                        "MESSENGER_TASK_AUDIENCE",
                        os.environ["MESSENGER_WORKER_URL"],
                    ),
                },
            },
        }
        client.create_task(parent=parent, task=task)
        return True
    except Exception as exc:
        raise TaskEnqueueError("could not enqueue Messenger event") from exc
