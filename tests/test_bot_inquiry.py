import os
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from bot.services import inquiry, nlp

checkout_stub = types.ModuleType("db.repository.checkout")
checkout_stub.start_checkout = lambda *args, **kwargs: {"checkout_session_id": "test-session"}
sys.modules.setdefault("db.repository.checkout", checkout_stub)

CONFIRMATION_PATH = (
    Path(__file__).resolve().parents[1] / "bot" / "handlers" / "confirmation.py"
)
CONFIRMATION_SPEC = importlib.util.spec_from_file_location(
    "confirmation_under_test",
    CONFIRMATION_PATH,
)
confirmation = importlib.util.module_from_spec(CONFIRMATION_SPEC)
CONFIRMATION_SPEC.loader.exec_module(confirmation)


def inventory_item(name="Venom", size="10", status="onhand"):
    return {
        "id": 1,
        "name": name,
        "image": "venom.jpg",
        "variations": [
            {
                "id": 11,
                "size": size,
                "price": 6500,
                "status": status,
                "condition": "VNDS",
                "url": "https://example.com/venom",
            }
        ],
    }


class BotInquiryTestCase(unittest.TestCase):
    def setUp(self):
        self.reply_patcher = patch.object(inquiry, "reply")
        self.carousel_patcher = patch.object(inquiry, "send_carousel")
        self.push_patcher = patch.object(inquiry, "push_user_message")
        self.reply = self.reply_patcher.start()
        self.carousel = self.carousel_patcher.start()
        self.push = self.push_patcher.start()

    def tearDown(self):
        self.reply_patcher.stop()
        self.carousel_patcher.stop()
        self.push_patcher.stop()

    def test_item_and_size_exact_match_sends_carousel(self):
        with patch.object(inquiry, "get_gpt_analysis", return_value={
            "intent": "ask_availability",
            "item": "Venom",
            "size": "10",
            "confidence": "high",
            "reply": "",
        }), patch.object(inquiry, "search_inventory_matches", return_value={
            "found": True,
            "items": [inventory_item()],
        }):
            inquiry.handle_inquiry("sender-1", "venom size 10")

        self.reply.assert_called_with("sender-1", "We have Venom in US 10.")
        self.carousel.assert_called_once()

    def test_typo_item_uses_fuzzy_repository_result(self):
        with patch.object(inquiry, "get_gpt_analysis", return_value={
            "intent": "ask_availability",
            "item": "venm",
            "size": "10",
            "confidence": "medium",
            "reply": "",
        }), patch.object(inquiry, "search_inventory_matches", return_value={
            "found": True,
            "items": [inventory_item(name="Venom")],
        }) as search:
            inquiry.handle_inquiry("sender-1", "venm 10")

        search.assert_called_with(name="venm", size="10")
        self.reply.assert_called_with("sender-1", "We have Venom in US 10.")

    def test_size_only_inquiry_lists_available_pairs(self):
        with patch.object(inquiry, "get_gpt_analysis", return_value={
            "intent": "ask_availability",
            "item": "",
            "size": "",
            "confidence": "low",
            "reply": "",
        }), patch.object(inquiry, "get_item_sizes", return_value={
            "found": True,
            "items": [inventory_item(size="9")],
        }):
            inquiry.handle_inquiry("sender-1", "size 9?")

        self.reply.assert_called_with("sender-1", "Here are available pairs in US 9.")
        self.carousel.assert_called_once()

    def test_item_only_inquiry_asks_for_size(self):
        with patch.object(inquiry, "get_gpt_analysis", return_value={
            "intent": "ask_availability",
            "item": "Venom",
            "size": "",
            "confidence": "high",
            "reply": "",
        }), patch.object(inquiry, "search_inventory_matches", return_value={
            "found": True,
            "items": [inventory_item()],
        }), patch.object(inquiry, "set_state") as set_state:
            inquiry.handle_inquiry("sender-1", "venom available?")

        set_state.assert_called_with("sender-1", {
            "state": "awaiting_size",
            "item": "Venom",
        })
        self.assertIn("What US size", self.reply.call_args.args[1])

    def test_unavailable_size_suggests_alternate_sizes(self):
        with patch.object(inquiry, "get_gpt_analysis", return_value={
            "intent": "ask_availability",
            "item": "Venom",
            "size": "10",
            "confidence": "high",
            "reply": "",
        }), patch.object(inquiry, "search_inventory_matches", return_value={
            "found": False,
            "items": [],
            "alternate_sizes": [inventory_item(size="9.5")],
            "same_size_items": [],
        }), patch.object(inquiry, "set_state"):
            inquiry.handle_inquiry("sender-1", "venom 10")

        self.assertIn("These sizes are available", self.reply.call_args.args[1])
        self.carousel.assert_called_once()

    def test_unsupported_policy_routes_to_handover(self):
        with patch.object(inquiry, "get_gpt_analysis", return_value={
            "intent": "smalltalk",
            "item": "",
            "size": "",
            "confidence": "low",
            "reply": "",
        }), patch.object(inquiry, "set_handover") as handover:
            inquiry.handle_inquiry("sender-1", "do you allow refund?")

        handover.assert_called_once_with("sender-1")
        self.assertIn("real person", self.reply.call_args.args[1])


class BotAutoReplyGuardTestCase(unittest.TestCase):
    def test_checkout_state_ignores_unrelated_faq_auto_reply(self):
        result = nlp.get_auto_reply("📦 how to order", "sender-1", {
            "state": "handle_payment_method",
        })
        self.assertIsNone(result)

    def test_handover_auto_reply_is_allowed_in_checkout_state(self):
        with patch.object(nlp, "set_handover") as handover:
            result = nlp.get_auto_reply("💬 talk to human", "sender-1", {
                "state": "handle_payment_method",
            })

        self.assertIsNotNone(result)
        handover.assert_called_once_with("sender-1")


class BotStateRecoveryTestCase(unittest.TestCase):
    def test_missing_confirmation_state_recovers_without_exception(self):
        with patch.object(confirmation, "reset_state") as reset_state, patch.object(confirmation, "reply") as reply:
            confirmation.handle("sender-1", "yes", {"state": "awaiting_confirmation"})

        reset_state.assert_called_once_with("sender-1")
        self.assertIn("expired", reply.call_args.args[1])


if __name__ == "__main__":
    unittest.main()
