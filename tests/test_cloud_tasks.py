import importlib
import json
import os
import unittest
from unittest.mock import Mock, patch

from google.api_core.exceptions import AlreadyExists
from google.cloud import tasks_v2

from task import email, ocr


class EmailTaskTestCase(unittest.TestCase):
    def test_enqueue_email_constructs_task(self):
        client = Mock()
        client.queue_path.return_value = (
            "projects/test-project/locations/asia-southeast1/queues/email-queue"
        )
        client.create_task.return_value.name = "created-email-task"

        with patch.dict(
            os.environ, {"EMAIL_WORKER_URL": "https://worker.test/email"}
        ), patch.object(email, "PROJECT", "test-project"), patch.object(
            email.tasks_v2, "CloudTasksClient", return_value=client
        ):
            result = email.enqueue_email({"order_id": 42}, task_id="order-42")

        self.assertEqual(result, "created-email-task")
        client.queue_path.assert_called_once_with(
            "test-project", "asia-southeast1", "email-queue"
        )
        task = client.create_task.call_args.kwargs["task"]
        self.assertEqual(
            task["name"],
            f"{client.queue_path.return_value}/tasks/order-42",
        )
        self.assertEqual(task["http_request"]["http_method"], tasks_v2.HttpMethod.POST)
        self.assertEqual(task["http_request"]["url"], "https://worker.test/email")
        self.assertEqual(
            task["http_request"]["headers"],
            {"Content-Type": "application/json"},
        )
        self.assertEqual(json.loads(task["http_request"]["body"]), {"order_id": 42})

    def test_duplicate_explicit_task_id_returns_existing_task_name(self):
        client = Mock()
        client.queue_path.return_value = (
            "projects/test-project/locations/asia-southeast1/queues/email-queue"
        )
        client.create_task.side_effect = AlreadyExists("duplicate")

        with patch.dict(
            os.environ, {"EMAIL_WORKER_URL": "https://worker.test/email"}
        ), patch.object(email, "PROJECT", "test-project"), patch.object(
            email.tasks_v2, "CloudTasksClient", return_value=client
        ):
            result = email.enqueue_email({}, task_id="order-42")

        self.assertEqual(
            result,
            f"{client.queue_path.return_value}/tasks/order-42",
        )

    def test_missing_worker_url_fails_only_when_enqueueing(self):
        with patch.dict(os.environ, {}, clear=True), patch(
            "dotenv.load_dotenv"
        ), patch.object(email.tasks_v2, "CloudTasksClient") as client_class:
            importlib.reload(email)
            client_class.assert_not_called()

            with self.assertRaisesRegex(RuntimeError, "EMAIL_WORKER_URL"):
                email.enqueue_email({})

            client_class.assert_not_called()


class OcrTaskTestCase(unittest.TestCase):
    def test_enqueue_ocr_constructs_task(self):
        client = Mock()
        client.queue_path.return_value = (
            "projects/test-project/locations/asia-southeast1/queues/ocr-queue"
        )
        client.create_task.return_value.name = "created-ocr-task"

        with patch.dict(
            os.environ, {"OCR_WORKER_URL": "https://worker.test/ocr"}
        ), patch.object(ocr, "PROJECT", "test-project"), patch.object(
            ocr.tasks_v2, "CloudTasksClient", return_value=client
        ):
            result = ocr.enqueue_ocr("job-7", "uploads/image.jpg")

        self.assertEqual(result, "created-ocr-task")
        client.queue_path.assert_called_once_with(
            "test-project", "asia-southeast1", "ocr-queue"
        )
        task = client.create_task.call_args.kwargs["task"]
        self.assertNotIn("name", task)
        self.assertEqual(task["http_request"]["http_method"], tasks_v2.HttpMethod.POST)
        self.assertEqual(task["http_request"]["url"], "https://worker.test/ocr")
        self.assertEqual(
            task["http_request"]["headers"],
            {"Content-Type": "application/json"},
        )
        self.assertEqual(
            json.loads(task["http_request"]["body"]),
            {"job_id": "job-7", "image_path": "uploads/image.jpg"},
        )

    def test_missing_worker_url_fails_only_when_enqueueing(self):
        with patch.dict(os.environ, {}, clear=True), patch(
            "dotenv.load_dotenv"
        ), patch.object(ocr.tasks_v2, "CloudTasksClient") as client_class:
            importlib.reload(ocr)
            client_class.assert_not_called()

            with self.assertRaisesRegex(RuntimeError, "OCR_WORKER_URL"):
                ocr.enqueue_ocr("job-7", "uploads/image.jpg")

            client_class.assert_not_called()


if __name__ == "__main__":
    unittest.main()
