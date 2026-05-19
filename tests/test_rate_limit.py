import os
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

from flask import Flask, jsonify


RATE_LIMIT_PATH = (
    Path(__file__).resolve().parents[1] / "api" / "helpers" / "rate_limit.py"
)
RATE_LIMIT_SPEC = importlib.util.spec_from_file_location(
    "rate_limit_under_test",
    RATE_LIMIT_PATH,
)
rate_limit = importlib.util.module_from_spec(RATE_LIMIT_SPEC)
RATE_LIMIT_SPEC.loader.exec_module(rate_limit)


class ApiRateLimitTestCase(unittest.TestCase):
    def setUp(self):
        self.reset_rate_limit_state()

    def tearDown(self):
        self.reset_rate_limit_state()

    def reset_rate_limit_state(self):
        rate_limit._redis_client = None
        rate_limit._local_hits.clear()
        rate_limit._local_expiry.clear()

    def make_app(self):
        app = Flask(__name__)
        app.config["TESTING"] = True

        @app.route("/api/ping", methods=["GET", "OPTIONS"])
        def api_ping():
            return jsonify({"ok": True})

        @app.route("/api/other")
        def api_other():
            return jsonify({"ok": True})

        @app.route("/health")
        def health():
            return jsonify({"ok": True})

        rate_limit.register_api_rate_limit(app)
        return app

    def test_api_requests_are_limited_after_configured_threshold(self):
        app = self.make_app()

        with patch.dict(
            os.environ,
            {
                "API_RATE_LIMIT": "1",
                "API_RATE_LIMIT_WINDOW_SECONDS": "60",
                "REDIS_URL": "",
            },
        ):
            client = app.test_client()

            first_response = client.get("/api/ping")
            limited_response = client.get("/api/ping")

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(limited_response.status_code, 429)
        self.assertEqual(
            limited_response.get_json(),
            {
                "message": "Too many requests. Please wait before trying again.",
                "code": "RATE_LIMITED",
            },
        )
        self.assertGreaterEqual(int(limited_response.headers["Retry-After"]), 1)

    def test_rate_limit_applies_to_api_routes_only(self):
        app = self.make_app()

        with patch.dict(
            os.environ,
            {
                "API_RATE_LIMIT": "1",
                "API_RATE_LIMIT_WINDOW_SECONDS": "60",
                "REDIS_URL": "",
            },
        ):
            client = app.test_client()

            self.assertEqual(client.get("/api/ping").status_code, 200)
            self.assertEqual(client.get("/api/ping").status_code, 429)

            self.assertEqual(client.get("/health").status_code, 200)
            self.assertEqual(client.get("/health").status_code, 200)

    def test_options_requests_do_not_consume_api_rate_limit(self):
        app = self.make_app()

        with patch.dict(
            os.environ,
            {
                "API_RATE_LIMIT": "1",
                "API_RATE_LIMIT_WINDOW_SECONDS": "60",
                "REDIS_URL": "",
            },
        ):
            client = app.test_client()

            self.assertEqual(client.options("/api/ping").status_code, 200)
            self.assertEqual(client.get("/api/ping").status_code, 200)
            self.assertEqual(client.get("/api/ping").status_code, 429)

    def test_api_rate_limit_is_scoped_by_endpoint(self):
        app = self.make_app()

        with patch.dict(
            os.environ,
            {
                "API_RATE_LIMIT": "1",
                "API_RATE_LIMIT_WINDOW_SECONDS": "60",
                "REDIS_URL": "",
            },
        ):
            client = app.test_client()

            self.assertEqual(client.get("/api/ping").status_code, 200)
            self.assertEqual(client.get("/api/ping").status_code, 429)
            self.assertEqual(client.get("/api/other").status_code, 200)

    def test_local_rate_limit_fallback_resets_after_window(self):
        with patch.object(rate_limit, "_get_redis_client", return_value=None):
            with patch.object(
                rate_limit.time,
                "time",
                side_effect=[100.0, 101.0, 103.1],
            ):
                self.assertEqual(rate_limit.rate_limit_hit("direct", 1, 3), (False, 3))
                self.assertEqual(rate_limit.rate_limit_hit("direct", 1, 3), (True, 2))
                self.assertEqual(rate_limit.rate_limit_hit("direct", 1, 3), (False, 3))


if __name__ == "__main__":
    unittest.main()
