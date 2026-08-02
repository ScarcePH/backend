import unittest
from unittest.mock import Mock, patch

from bot.services import messenger, send_text


class MessengerClientTestCase(unittest.TestCase):
    def test_reply_propagates_retryable_delivery_failure(self):
        failure = send_text.SendResult(
            False,
            status_code=503,
            error_class="graph_transient",
            retryable=True,
        )
        with patch.object(messenger, "send_text_message", return_value=failure):
            with self.assertRaises(send_text.MessengerTransientError):
                messenger.reply("sender", "hello")

    def setUp(self):
        self.token_patcher = patch.object(send_text, "PAGE_ACCESS_TOKEN", "test-token")
        self.sleep_patcher = patch.object(send_text.time, "sleep")
        self.token_patcher.start()
        self.sleep_patcher.start()

    def tearDown(self):
        self.sleep_patcher.stop()
        self.token_patcher.stop()

    def test_success_returns_typed_result_and_sets_timeouts(self):
        response = Mock(status_code=200)
        with patch.object(send_text.requests, "post", return_value=response) as post:
            result = send_text.send_text_message("sender", "hello")

        self.assertTrue(result.ok)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(post.call_args.kwargs["timeout"], (
            send_text.CONNECT_TIMEOUT,
            send_text.READ_TIMEOUT,
        ))
        self.assertFalse(post.call_args.kwargs["allow_redirects"])

    def test_client_error_is_not_retried(self):
        response = Mock(status_code=400)
        with patch.object(send_text.requests, "post", return_value=response) as post:
            result = send_text.send_text_message("sender", "hello")

        self.assertFalse(result.ok)
        self.assertFalse(result.retryable)
        self.assertEqual(result.error_class, "graph_rejected")
        post.assert_called_once()

    def test_transient_error_is_retried(self):
        responses = [Mock(status_code=503), Mock(status_code=200)]
        with patch.object(send_text.requests, "post", side_effect=responses) as post:
            result = send_text.send_text_message("sender", "hello")

        self.assertTrue(result.ok)
        self.assertEqual(post.call_count, 2)

    def test_quick_replies_are_limited_and_truncated(self):
        response = Mock(status_code=200)
        replies = ["x" * 30 for _ in range(20)]
        with patch.object(send_text.requests, "post", return_value=response) as post:
            send_text.send_text_message("sender", "hello", replies)

        sent = post.call_args.kwargs["json"]["message"]["quick_replies"]
        self.assertEqual(len(sent), 13)
        self.assertTrue(all(len(item["title"]) <= 20 for item in sent))

    def test_missing_token_fails_without_network_call(self):
        with patch.object(send_text, "PAGE_ACCESS_TOKEN", None), patch.object(
            send_text.requests, "post"
        ) as post:
            result = send_text.send_text_message("sender", "hello")

        self.assertFalse(result.ok)
        self.assertEqual(result.error_class, "missing_page_access_token")
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
