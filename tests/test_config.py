import os
import unittest
from unittest.mock import patch

from config import Config


class ConfigValidationTestCase(unittest.TestCase):
    def test_missing_production_environment_is_reported_without_values(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError) as raised:
                Config.validate_required_environment()

        message = str(raised.exception)
        self.assertIn("APP_SECRET", message)
        self.assertIn("MESSENGER_WORKER_URL", message)

    def test_complete_environment_passes(self):
        names = (
            "APP_SECRET",
            "VERIFY_TOKEN",
            "PAGE_ACCESS_TOKEN",
            "PAGE_APP_ID",
            "REDIS_URL",
            "DB_URI",
            "GOOGLE_CLOUD_PROJECT",
            "GOOGLE_CLOUD_LOCATION",
            "MESSENGER_TASK_QUEUE",
            "MESSENGER_WORKER_URL",
            "TASKS_SERVICE_ACCOUNT_EMAIL",
            "EMAIL_WORKER_URL",
            "JWT_SECRET_KEY",
        )
        with patch.dict(os.environ, {name: "configured" for name in names}, clear=True):
            Config.validate_required_environment()


if __name__ == "__main__":
    unittest.main()
