"""
Standalone mock billing server — run this separately to receive and inspect
real HTTP POST requests from the agent when MOCK_BILLING=false.

Run it with:
    python mock_billing_server.py

It listens on port 9000. All received tasks are:
  1. Printed to the console (visible immediately)
  2. Stored in memory and accessible via GET http://localhost:9000/tasks
  3. Saved to billing_tasks_log.json on disk for persistence

Set in .env:
  MOCK_BILLING=false
  BILLING_API_URL=http://localhost:9000
"""
import json
import uuid
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [BILLING-SERVER] %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Mock Billing Server", version="1.0.0")

# In-memory store of all received tasks
_received_tasks: List[Dict[str, Any]] = []
LOG_FILE = Path("billing_tasks_log.json")


def _save_to_disk():
    LOG_FILE.write_text(json.dumps(_received_tasks, indent=2))


# ── POST /api/v1/billing/tasks ────────────────────────────────────────────────

@app.post("/api/v1/billing/tasks")
async def receive_billing_task(request: Request):
    body = await request.json()

    transaction_id = body.get("transaction_id", f"TXN-MOCK-{uuid.uuid4().hex[:8].upper()}")
    body["received_at"] = datetime.now(timezone.utc).isoformat()
    body["status"] = "processed"

    _received_tasks.append(body)
    _save_to_disk()

    # Print clearly so you can see it instantly in the terminal
    logger.info("=" * 60)
    logger.info("✅ BILLING TASK RECEIVED")
    logger.info("   transaction_id   : %s", transaction_id)
    logger.info("   account_id       : %s", body.get("account_id"))
    logger.info("   action_type      : %s", body.get("action_type"))
    logger.info("   amount           : %s %s", body.get("amount"), body.get("currency", "USD"))
    logger.info("   reason           : %s", body.get("reason"))
    logger.info("   change_suggested : %s", str(body.get("notes", ""))[:120])
    logger.info("   initiated_by     : %s", body.get("initiated_by"))
    logger.info("=" * 60)

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "transaction_id": transaction_id,
            "status": "processed",
            "message": f"Billing task '{body.get('action_type')}' accepted for account {body.get('account_id')}.",
        },
    )


# ── GET /tasks ────────────────────────────────────────────────────────────────

@app.get("/tasks")
async def list_tasks():
    """Return all billing tasks received in this session."""
    return {
        "total": len(_received_tasks),
        "tasks": _received_tasks,
    }


@app.get("/tasks/{transaction_id}")
async def get_task(transaction_id: str):
    """Look up a specific task by transaction_id."""
    match = next((t for t in _received_tasks if t.get("transaction_id") == transaction_id), None)
    if not match:
        return JSONResponse(status_code=404, content={"error": "Task not found"})
    return match


@app.delete("/tasks")
async def clear_tasks():
    """Clear all stored tasks (useful between test runs)."""
    _received_tasks.clear()
    if LOG_FILE.exists():
        LOG_FILE.unlink()
    return {"message": "All tasks cleared."}


@app.get("/health")
async def health():
    return {"status": "ok", "tasks_received": len(_received_tasks)}


if __name__ == "__main__":
    logger.info("Mock Billing Server starting on http://localhost:9000")
    logger.info("Agent should have: MOCK_BILLING=false  BILLING_API_URL=http://localhost:9000")
    uvicorn.run(app, host="0.0.0.0", port=9000, log_level="warning")
