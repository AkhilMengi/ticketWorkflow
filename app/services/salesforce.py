"""
Salesforce service — creates Cases via the SF REST API.

Authentication: OAuth 2.0 Client Credentials flow
  POST /services/oauth2/token  (client_id + client_secret)

When MOCK_SALESFORCE=true the real API is skipped and a deterministic
mock response is returned, which is useful for local development.
"""
import logging
from typing import Dict, Any

import requests

from app.config import SF_CLIENT_ID, SF_CLIENT_SECRET, SF_LOGIN_URL, MOCK_SALESFORCE

logger = logging.getLogger(__name__)

SF_API_VERSION = "v59.0"


# ── Auth ─────────────────────────────────────────────────────────────────────

def _get_access_token() -> tuple[str, str]:
    """Return (access_token, instance_url) using client-credentials flow."""
    url = f"{SF_LOGIN_URL}/services/oauth2/token"
    resp = requests.post(
        url,
        data={
            "grant_type": "client_credentials",
            "client_id": SF_CLIENT_ID,
            "client_secret": SF_CLIENT_SECRET,
        },
        timeout=15,
    )
    resp.raise_for_status()
    body = resp.json()
    return body["access_token"], body["instance_url"]


# ── Case creation ─────────────────────────────────────────────────────────────

def create_sf_case(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a Salesforce Case.

    payload keys (from LLM):
      subject, description, priority, status, origin, account_id
    """
    if MOCK_SALESFORCE:
        mock_id = f"MOCK-{payload.get('account_id', 'UNK')}-001"
        logger.info("[MOCK SF] Case created: %s", mock_id)
        return {
            "success": True,
            "id": mock_id,
            "case_number": "00001001",
            "message": "Mock Salesforce case created successfully.",
        }

    try:
        access_token, instance_url = _get_access_token()

        case_body: Dict[str, Any] = {
            "Subject": payload.get("subject", "Support Request"),
            "Description": (
                f"[Account: {payload.get('account_id', 'N/A')}]\n\n"
                + payload.get("description", "")
            ),
            "Priority": payload.get("priority", "Medium"),
            "Status": payload.get("status", "New"),
            "Origin": payload.get("origin", "Web"),
        }

        resp = requests.post(
            f"{instance_url}/services/data/{SF_API_VERSION}/sobjects/Case",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json=case_body,
            timeout=20,
        )
        resp.raise_for_status()
        result = resp.json()

        logger.info("SF case created: id=%s", result.get("id"))
        return {
            "success": True,
            "id": result.get("id"),
            "case_number": result.get("id"),   # SF returns id; case number needs a separate query
            "message": "Salesforce case created successfully.",
        }

    except requests.HTTPError as exc:
        logger.error("SF HTTP error: %s – %s", exc.response.status_code, exc.response.text)
        return {"success": False, "error": str(exc), "detail": exc.response.text}
    except Exception as exc:
        logger.error("SF unexpected error: %s", exc)
        return {"success": False, "error": str(exc)}
