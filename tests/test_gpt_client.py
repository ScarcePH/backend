import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch


os.environ.setdefault("OPENAI_API_KEY", "test-key")

from bot.utils import gpt_client


class GPTClientTestCase(unittest.TestCase):
    def test_gpt_uses_no_reasoning_effort(self):
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"intent": "smalltalk"}'))]
        )
        with patch.object(
            gpt_client.client.chat.completions,
            "create",
            return_value=response,
        ) as create:
            gpt_client.call_gpt("system", "message")

        self.assertEqual("none", create.call_args.kwargs["reasoning_effort"])


if __name__ == "__main__":
    unittest.main()
