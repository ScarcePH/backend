import json
import os
import unittest
from unittest.mock import patch


os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from bot.core import router
from bot.handlers import customer_address, customer_name, customer_phone, payment, postback
import bot.handlers.confirmation as confirmation
from bot.state import manager


class FakeRedis:
    def __init__(self):
        self.values = {}

    def get(self, key):
        return self.values.get(key)

    def setex(self, key, ttl, value):
        self.values[key] = value

    def delete(self, key):
        self.values.pop(key, None)

    def exists(self, key):
        return int(key in self.values)


class VersionedStateTestCase(unittest.TestCase):
    def setUp(self):
        self.redis = FakeRedis()
        self.redis_patch = patch.object(manager, "redis_client", self.redis)
        self.redis_patch.start()

    def tearDown(self):
        self.redis_patch.stop()

    def test_new_checkout_state_contains_guidance_metadata(self):
        state = manager.new_checkout_state(expected_input="ORDER_CONFIRM", item="Venom")
        self.assertEqual(manager.STATE_VERSION, state["state_version"])
        self.assertEqual("ORDER_CONFIRM", state["expected_input"])
        self.assertTrue(state["checkout_session_id"])
        self.assertEqual(0, state["invalid_attempts"])

    def test_transition_table_rejects_out_of_order_transition(self):
        state = manager.new_checkout_state()
        with self.assertRaises(ValueError):
            manager.transition_state("sender-1", state, "awaiting_customer_phone")

    def test_second_invalid_attempt_preserves_checkout_and_handover_context(self):
        state = manager.new_checkout_state(item="Venom", invalid_attempts=0)
        first, handed_over = manager.record_invalid_attempt("sender-1", state)
        self.assertFalse(handed_over)

        second, handed_over = manager.record_invalid_attempt("sender-1", first)
        self.assertTrue(handed_over)
        self.assertEqual("Venom", manager.get_state("sender-1")["item"])
        context = manager.get_handover("sender-1")
        self.assertEqual(second["checkout_session_id"], context["checkout_session_id"])
        self.assertEqual("awaiting_confirmation", context["originating_state"])


class GuidedRouterTestCase(unittest.TestCase):
    def test_cancel_invalidates_persisted_checkout(self):
        state = manager.new_checkout_state(
            "handle_verify_payment",
            checkout_session_id="checkout-1",
        )
        with patch.object(router, "get_state", return_value=state), \
             patch("db.repository.checkout.abandon_checkout_session", return_value=({"ok": True}, 200)) as abandon, \
             patch.object(router, "reset_state"), \
             patch.object(router, "reply"):
            router.handle_message("sender-1", "ORDER_CANCEL")

        abandon.assert_called_once_with("checkout-1")

    def test_active_checkout_does_not_call_nlp(self):
        handler = unittest.mock.Mock()
        state = manager.new_checkout_state("handle_payment_method", expected_input="payment_method")
        with patch.object(router, "get_state", return_value=state), \
             patch.dict(router.STATE_HANDLERS, {"handle_payment_method": handler}), \
             patch.object(router, "get_auto_reply") as auto_reply:
            router.handle_message("sender-1", "random text")

        auto_reply.assert_not_called()
        handler.assert_called_once()

    def test_global_handover_keeps_checkout_state(self):
        state = manager.new_checkout_state("awaiting_customer_name", checkout_session_id="checkout-1")
        with patch.object(router, "get_state", return_value=state), \
             patch.object(router, "set_handover") as handover, \
             patch.object(router, "reply"):
            router.handle_message("sender-1", "TALK_TO_HUMAN")

        handover.assert_called_once()
        self.assertEqual("checkout-1", handover.call_args.kwargs["state"]["checkout_session_id"])


class InputValidationTestCase(unittest.TestCase):
    def test_order_postback_reloads_authoritative_inventory_values(self):
        inventory = type("Inventory", (), {"id": 1, "name": "Current Name"})()
        variation = type("Variation", (), {
            "id": 2,
            "inventory_id": 1,
            "size": "10",
            "price": 7000,
            "url": "https://example.com/current",
            "status": "onhand",
        })()
        event = {
            "postback": {
                "payload": json.dumps({
                    "action": "ORDER",
                    "inventory_id": 1,
                    "variation_id": 2,
                    "item": "Stale Name",
                    "price": "1",
                })
            }
        }
        with patch.object(postback.db.session, "get", side_effect=[inventory, variation]), \
             patch.object(postback, "is_variation_sellable", return_value=True), \
             patch.object(postback, "clear_handover"), \
             patch.object(postback, "set_state") as set_state, \
             patch.object(postback, "reply"):
            postback.handle_postback("sender-1", event["postback"]["payload"], event)

        saved = set_state.call_args.args[1]
        self.assertEqual("Current Name", saved["item"])
        self.assertEqual("7000", saved["price"])

    def test_confirmation_accepts_stable_action_after_router_normalization(self):
        state = manager.new_checkout_state(
            item="Venom", size="10", inventory_id=1, variation_id=2,
            price="6500", status="onhand",
        )
        customer = type("Customer", (), {"sender_id": "sender-1"})()
        with patch.object(confirmation, "get_or_create_customer", return_value=customer), \
             patch.object(confirmation, "start_checkout", return_value={"checkout_session_id": "db-checkout"}), \
             patch.object(confirmation, "transition_state") as transition, \
             patch.object(confirmation, "reply"):
            confirmation.handle("sender-1", "order_confirm", state)

        self.assertEqual("handle_payment_method", transition.call_args.args[2])

    def test_ph_phone_is_normalized(self):
        self.assertEqual("+639171234567", customer_phone.normalize_ph_phone("0917 123 4567"))
        self.assertEqual("+639171234567", customer_phone.normalize_ph_phone("+639171234567"))
        self.assertIsNone(customer_phone.normalize_ph_phone("9171234567"))

    def test_invalid_name_and_address_use_two_strike_recovery(self):
        state = manager.new_checkout_state("awaiting_customer_name")
        with patch.object(customer_name, "reject_input") as reject:
            customer_name.handle("sender-1", "x", state)
        reject.assert_called_once()

        address_state = {**state, "state": "awaiting_customer_address", "customer_name": "Juan Cruz"}
        with patch.object(customer_address, "reject_input") as reject:
            customer_address.handle("sender-1", "short", address_state)
        reject.assert_called_once()

    def test_payment_accepts_stable_action_and_records_expected_amount(self):
        state = manager.new_checkout_state(
            "handle_payment_method", checkout_session_id="checkout-1", price="6500", status="onhand",
        )
        with patch.object(payment, "transition_state") as transition, patch.object(payment, "reply"):
            payment.handle_payment_method("sender-1", "PAYMENT_FULL", state)

        self.assertEqual("handle_verify_payment", transition.call_args.args[2])
        self.assertEqual("6500", transition.call_args.kwargs["expected_payment_amount"])
        self.assertEqual("full_payment", transition.call_args.kwargs["payment_method"])


if __name__ == "__main__":
    unittest.main()
