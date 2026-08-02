from bot.services.messenger import reply
from bot.core.constants import WELCOME_MSG,YES_OR_NO
from bot.state.manager import clear_handover, new_checkout_state, reset_state, set_state
from bot.core.router import handle_message
from db.database import db
from db.models import Inventory, InventoryVariation
from db.repository.inventory import is_variation_sellable
import json

def handle_postback(sender_id, payload,event):
    if payload == "GET_STARTED":
        clear_handover(sender_id)
        reset_state(sender_id)
        reply(sender_id, WELCOME_MSG)
        return "ok"


    if payload in {
        "ORDER_CONFIRM", "ORDER_CANCEL", "CHECKOUT_RESTART", "TALK_TO_HUMAN",
        "PAYMENT_COD", "PAYMENT_COP", "PAYMENT_FULL", "ADDRESS_USE", "ADDRESS_CHANGE",
    }:
        handle_message(sender_id, payload)
        return "ok"

    try:
        order_payload = json.loads(payload)
    except (TypeError, ValueError, json.JSONDecodeError):
        reply(sender_id, "That option is no longer valid. Please choose an item again.")
        return "ok"

    if order_payload.get("action") == "ORDER":
        required = {"inventory_id", "variation_id"}
        if any(order_payload.get(key) is None for key in required):
            reply(sender_id, "That item option has expired. Please choose it again.")
            return "ok"
        inventory = db.session.get(Inventory, order_payload["inventory_id"])
        variation = db.session.get(InventoryVariation, order_payload["variation_id"])
        if (
            inventory is None
            or variation is None
            or variation.inventory_id != inventory.id
            or not is_variation_sellable(variation)
        ):
            reply(sender_id, "That pair is no longer available. Please choose another option.")
            return "ok"

        clear_handover(sender_id)
        set_state(sender_id, new_checkout_state(
            "awaiting_confirmation",
            expected_input="ORDER_CONFIRM",
            item=inventory.name,
            size=variation.size,
            price=str(variation.price),
            url=variation.url,
            inventory_id=inventory.id,
            variation_id=variation.id,
            status=variation.status,
        ))
        status = "📦 PREORDER \n 🔒 DP ₱1000 required to process order. the rest upon arrival" if variation.status == 'preorder' else variation.status

        msg = (
            f"{inventory.name} \n"
            f"📏 Size: {variation.size}us \n"
            f"🏷️ ₱{variation.price} only. \n"
            f"{status} \n\n"
            "Would you like to order this pair? (Yes / No)"
        )
        
        reply(sender_id,msg, YES_OR_NO)
