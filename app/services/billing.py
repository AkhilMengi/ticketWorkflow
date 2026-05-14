"""
Billing service — creates structured billing tasks and posts them to the billing API.

The billing task payload is a rich document that contains every piece of
information the billing tool needs to process the request without any
additional lookups:
  - transaction_id   : unique ID for this billing operation
  - account_id       : the customer account being acted on
  - change_suggested : the LLM's plain-English recommendation
  - action_type      : rebill | credit | refund | adjustment
  - amount / currency
  - reason code
  - full notes
  - initiated_by     : who/what triggered the task ("agent" in our case)
  - created_at       : ISO timestamp

MOCK_BILLING=true returns realistic mock responses for local development.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List

import requests

from app.config import BILLING_API_URL, MOCK_BILLING

logger = logging.getLogger(__name__)

# In-memory store — holds every billing task created this session
# (reset on server restart; swap for DB when ready)
_task_store: List[Dict[str, Any]] = []


def get_all_tasks() -> List[Dict[str, Any]]:
    """Return all billing tasks created in this session."""
    return _task_store


def get_task_by_id(transaction_id: str) -> Dict[str, Any] | None:
    """Look up a task by its transaction_id."""
    return next((t for t in _task_store if t.get("transaction_id") == transaction_id), None)


def _build_task_payload(payload: Dict[str, Any], transaction_id: str) -> Dict[str, Any]:
    """
    Assemble the full structured billing task that will be sent to the
    billing micro-service and returned to the UI.
    """
    return {
        # ── Identity ──────────────────────────────────────────────────────────
        "transaction_id":    transaction_id,
        "account_id":        payload.get("account_id", "UNKNOWN"),

        # ── What the agent decided ────────────────────────────────────────────
        "change_suggested":  payload.get("notes", ""),        # LLM's full recommendation
        "action_type":       payload.get("action_type", "adjustment"),
        "reason":            payload.get("reason", ""),       # short code e.g. DUPLICATE_CHARGE

        # ── Financial details ─────────────────────────────────────────────────
        "amount":            payload.get("amount", 0.0),
        "currency":          payload.get("currency", "USD"),

        # ── Context ───────────────────────────────────────────────────────────
        "notes":             payload.get("notes", ""),
        "initiated_by":      "intelligent-agent",
        "initiated_for":     payload.get("initiated_for", ""),
        "created_at":        datetime.now(timezone.utc).isoformat(),
        "status":            "pending",
    }


def call_billing_api(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a billing task and post it to the billing API.

    payload keys (from LLM):
      account_id, action_type, amount, currency, reason, notes
    """
    account_id     = payload.get("account_id", "UNKNOWN")
    transaction_id = f"TXN-{account_id}-{uuid.uuid4().hex[:8].upper()}"
    task           = _build_task_payload(payload, transaction_id)

    if MOCK_BILLING:
        task["status"] = "processed"
        _task_store.append(task)
        logger.info(
            "[MOCK BILLING] task created | txn=%s account=%s action=%s amount=%s",
            transaction_id, account_id, task["action_type"], task["amount"],
        )
        return {
            "success":      True,
            "message":      f"Billing task '{task['action_type']}' created for account {account_id}.",
            "billing_task": task,
        }

    try:
        resp = requests.post(
            f"{BILLING_API_URL}/api/v1/billing/tasks",
            json=task,
            timeout=20,
        )
        resp.raise_for_status()
        result = resp.json()

        task["transaction_id"] = result.get("transaction_id", transaction_id)
        task["status"]         = result.get("status", "processed")
        _task_store.append(task)

        logger.info("Billing task submitted: txn=%s", task["transaction_id"])
        return {
            "success":      True,
            "message":      result.get("message", "Billing task created."),
            "billing_task": task,
        }

    except requests.HTTPError as exc:
        logger.error("Billing HTTP error: %s – %s", exc.response.status_code, exc.response.text)
        return {"success": False, "error": str(exc), "detail": exc.response.text}
    except Exception as exc:
        logger.error("Billing unexpected error: %s", exc)
        return {"success": False, "error": str(exc)}
