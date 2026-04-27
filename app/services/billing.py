"""
Billing service — applies financial adjustments via the billing API.

In production this would call your internal billing micro-service.
MOCK_BILLING=true returns realistic mock responses for local development.
"""
import logging
import uuid
from typing import Dict, Any

import requests

from app.config import BILLING_API_URL, MOCK_BILLING

logger = logging.getLogger(__name__)


def call_billing_api(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply a billing action for the given account.

    payload keys (from LLM):
      account_id, action_type, amount, currency, reason, notes
    """
    action_type = payload.get("action_type", "adjustment")
    account_id = payload.get("account_id", "UNKNOWN")
    amount = payload.get("amount", 0.0)
    transaction_id = f"TXN-{account_id}-{uuid.uuid4().hex[:8].upper()}"

    if MOCK_BILLING:
        logger.info(
            "[MOCK BILLING] action=%s account=%s amount=%s txn=%s",
            action_type, account_id, amount, transaction_id,
        )
        return {
            "success": True,
            "transaction_id": transaction_id,
            "account_id": account_id,
            "action_type": action_type,
            "amount": amount,
            "currency": payload.get("currency", "USD"),
            "status": "processed",
            "message": (
                f"Billing action '{action_type}' applied successfully "
                f"for account {account_id}."
            ),
        }

    try:
        resp = requests.post(
            f"{BILLING_API_URL}/api/v1/billing/adjustment",
            json={
                "account_id": account_id,
                "action_type": action_type,
                "amount": amount,
                "currency": payload.get("currency", "USD"),
                "reason": payload.get("reason", ""),
                "notes": payload.get("notes", ""),
                "reference_id": transaction_id,
            },
            timeout=20,
        )
        resp.raise_for_status()
        result = resp.json()

        logger.info("Billing action completed: txn=%s", transaction_id)
        return {
            "success": True,
            "transaction_id": result.get("transaction_id", transaction_id),
            "account_id": account_id,
            "action_type": action_type,
            "amount": amount,
            "status": result.get("status", "processed"),
            "message": result.get("message", "Billing action applied."),
        }

    except requests.HTTPError as exc:
        logger.error("Billing HTTP error: %s – %s", exc.response.status_code, exc.response.text)
        return {"success": False, "error": str(exc), "detail": exc.response.text}
    except Exception as exc:
        logger.error("Billing unexpected error: %s", exc)
        return {"success": False, "error": str(exc)}
