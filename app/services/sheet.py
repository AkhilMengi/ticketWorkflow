"""
Sheet service — updates values in Excel/Google Sheets via a new API.

This is a simple wrapper around a sheet update API that allows
quick value changes triggered by button clicks in the UI.
"""
import logging
from typing import Dict, Any
from datetime import datetime, timezone

import requests

from app.config import SHEET_API_URL, SHEET_FILE_NAME

logger = logging.getLogger(__name__)


def update_sheet(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update a value in the Excel/Sheet (file name: abc).
    
    payload keys:
      account_id      : which account/row to update
      field_name      : which column to update (e.g., "meter_config", "status", "notes")
      field_value     : new value to set
      context         : optional context about why this update is happening
    
    Returns:
        {
            "success": bool,
            "message": str,
            "updated_at": ISO timestamp,
            "account_id": str,
            "field_name": str,
            "previous_value": any,
            "new_value": any
        }
    """
    account_id = payload.get("account_id", "UNKNOWN")
    field_name = payload.get("field_name", "")
    field_value = payload.get("field_value", "")
    context = payload.get("context", "Manual update via UI button")

    if not field_name:
        logger.error("Sheet update: field_name is required")
        return {
            "success": False,
            "error": "field_name is required",
            "account_id": account_id,
        }

    logger.info(
        "Updating sheet: account=%s, field=%s, value=%s",
        account_id, field_name, field_value
    )

    try:
        # POST to the sheet API
        response = requests.post(
            f"{SHEET_API_URL}/api/v1/sheet/update",
            json={
                "sheet_file_name": SHEET_FILE_NAME,
                "account_id": account_id,
                "field_name": field_name,
                "field_value": field_value,
                "context": context,
                "updated_by": "intelligent-agent",
            },
            timeout=15,
        )
        response.raise_for_status()
        result = response.json()

        logger.info(
            "Sheet updated successfully: account=%s, field=%s",
            account_id, field_name
        )

        return {
            "success": True,
            "message": f"Sheet updated: {field_name} = {field_value}",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "account_id": account_id,
            "field_name": field_name,
            "previous_value": result.get("previous_value"),
            "new_value": result.get("new_value"),
        }

    except requests.HTTPError as exc:
        logger.error(
            "Sheet API HTTP error: %s – %s",
            exc.response.status_code, exc.response.text
        )
        return {
            "success": False,
            "error": f"HTTP {exc.response.status_code}: {exc.response.text}",
            "account_id": account_id,
        }

    except Exception as exc:
        logger.error("Sheet API error: %s", exc)
        return {
            "success": False,
            "error": str(exc),
            "account_id": account_id,
        }
