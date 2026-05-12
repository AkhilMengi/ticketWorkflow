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
            "External_User_Id__c": payload.get("account_id", ""),  # Store internal account_id
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


# ── Add comment to case ───────────────────────────────────────────────────────

def add_comment_to_case(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Add a comment to an existing Salesforce Case.

    payload keys:
      case_id (required), comment_body (required), account_id
    """
    case_id = payload.get("case_id", "").strip()
    comment_body = payload.get("comment_body", "").strip()
    account_id = payload.get("account_id", "")

    # Validation
    if not case_id:
        logger.warning("add_comment_to_case: case_id is empty or missing")
        return {"success": False, "error": "case_id is required for add_comment_to_case"}
    
    if not comment_body:
        logger.warning("add_comment_to_case: comment_body is empty or missing")
        return {"success": False, "error": "comment_body is required for add_comment_to_case"}

    if MOCK_SALESFORCE:
        mock_result = {
            "success": True,
            "case_id": case_id,
            "comment_id": f"MOCK-{case_id}-COMMENT-001",
            "account_id": account_id,
            "message": "Mock comment added successfully.",
        }
        logger.info("[MOCK SF] Comment added: %s", mock_result["comment_id"])
        return mock_result

    try:
        access_token, instance_url = _get_access_token()

        # Create a CaseComment object in Salesforce
        comment_payload: Dict[str, Any] = {
            "ParentId": case_id,
            "CommentBody": comment_body,
            "IsPublished": True,
        }

        resp = requests.post(
            f"{instance_url}/services/data/{SF_API_VERSION}/sobjects/CaseComment",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json=comment_payload,
            timeout=20,
        )
        resp.raise_for_status()
        result = resp.json()

        logger.info("SF comment added: case_id=%s, comment_id=%s", case_id, result.get("id"))
        return {
            "success": True,
            "case_id": case_id,
            "comment_id": result.get("id"),
            "account_id": account_id,
            "message": "Comment added to case successfully.",
        }

    except requests.HTTPError as exc:
        logger.error("SF HTTP error: %s – %s", exc.response.status_code, exc.response.text)
        return {"success": False, "error": str(exc), "detail": exc.response.text}
    except Exception as exc:
        logger.error("SF unexpected error: %s", exc)
        return {"success": False, "error": str(exc)}


# ── Close case ───────────────────────────────────────────────────────────────

def close_case(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Close an existing Salesforce Case by updating its status to "Closed".

    payload keys:
      case_id (required), reason (optional), account_id
    """
    case_id = payload.get("case_id", "").strip()
    reason = payload.get("reason", "").strip()
    account_id = payload.get("account_id", "")

    # Validation
    if not case_id:
        logger.warning("close_case: case_id is empty or missing")
        return {"success": False, "error": "case_id is required for close_case"}

    if MOCK_SALESFORCE:
        mock_result = {
            "success": True,
            "case_id": case_id,
            "status": "Closed",
            "account_id": account_id,
            "message": f"Mock case closed. Reason: {reason or 'N/A'}",
        }
        logger.info("[MOCK SF] Case closed: %s", case_id)
        return mock_result

    try:
        access_token, instance_url = _get_access_token()

        # Update Case record with status = Closed
        update_payload: Dict[str, Any] = {
            "Status": "Closed",
        }
        
        if reason:
            update_payload["Description"] = (
                f"Case closed. Reason: {reason}"
            )

        resp = requests.patch(
            f"{instance_url}/services/data/{SF_API_VERSION}/sobjects/Case/{case_id}",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json=update_payload,
            timeout=20,
        )
        resp.raise_for_status()

        logger.info("SF case closed: case_id=%s", case_id)
        return {
            "success": True,
            "case_id": case_id,
            "status": "Closed",
            "account_id": account_id,
            "message": "Case closed successfully.",
        }

    except requests.HTTPError as exc:
        logger.error("SF HTTP error: %s – %s", exc.response.status_code, exc.response.text)
        return {"success": False, "error": str(exc), "detail": exc.response.text}
    except Exception as exc:
        logger.error("SF unexpected error: %s", exc)
        return {"success": False, "error": str(exc)}


# ── Edit case (update fields) ─────────────────────────────────────────────────

def edit_case(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update specific fields of an existing Salesforce Case.

    payload keys:
      case_id (required), field_updates (required dict), account_id
    
    field_updates example: {"Priority": "High", "Subject": "Updated Subject"}
    """
    case_id = payload.get("case_id", "").strip()
    field_updates = payload.get("field_updates", {})
    account_id = payload.get("account_id", "")

    # Validation
    if not case_id:
        logger.warning("edit_case: case_id is empty or missing")
        return {"success": False, "error": "case_id is required for edit_case"}
    
    if not field_updates or not isinstance(field_updates, dict):
        logger.warning("edit_case: field_updates is empty or not a dict")
        return {"success": False, "error": "field_updates dict is required for edit_case"}

    if MOCK_SALESFORCE:
        mock_result = {
            "success": True,
            "case_id": case_id,
            "updated_fields": list(field_updates.keys()),
            "account_id": account_id,
            "message": f"Mock case updated with fields: {', '.join(field_updates.keys())}",
        }
        logger.info("[MOCK SF] Case updated: %s with fields %s", case_id, list(field_updates.keys()))
        return mock_result

    try:
        access_token, instance_url = _get_access_token()

        # Only send valid Salesforce Case fields
        # Common editable fields: Priority, Subject, Status, Description, Type, Reason, SLA__c, etc.
        update_payload: Dict[str, Any] = {}
        for field_name, field_value in field_updates.items():
            # Basic validation: only allow alphanumeric field names to avoid injection
            if field_name.replace("_", "").isalnum():
                update_payload[field_name] = field_value
            else:
                logger.warning("edit_case: skipping invalid field name '%s'", field_name)

        if not update_payload:
            logger.warning("edit_case: no valid fields to update")
            return {"success": False, "error": "no valid fields to update"}

        resp = requests.patch(
            f"{instance_url}/services/data/{SF_API_VERSION}/sobjects/Case/{case_id}",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json=update_payload,
            timeout=20,
        )
        resp.raise_for_status()

        logger.info("SF case updated: case_id=%s, fields=%s", case_id, list(update_payload.keys()))
        return {
            "success": True,
            "case_id": case_id,
            "updated_fields": list(update_payload.keys()),
            "account_id": account_id,
            "message": f"Case updated successfully with fields: {', '.join(update_payload.keys())}",
        }

    except requests.HTTPError as exc:
        logger.error("SF HTTP error: %s – %s", exc.response.status_code, exc.response.text)
        return {"success": False, "error": str(exc), "detail": exc.response.text}
    except Exception as exc:
        logger.error("SF unexpected error: %s", exc)
        return {"success": False, "error": str(exc)}


# ── Fetch recent open cases ───────────────────────────────────────────────────

def fetch_recent_cases(account_id: str, limit: int = 5) -> Dict[str, Any]:
    """
    Fetch recent OPEN cases for an account from Salesforce.
    
    Uses SOQL query to retrieve case details by External_User_Id__c (internal account_id).
    When MOCK_SALESFORCE=true, returns mock data. Otherwise queries the real Salesforce API.
    
    Args:
      account_id: Internal account ID (e.g., 'ACC-001', '557923')
                  Matched against Case.External_User_Id__c custom field
      limit: Max number of cases to return (default 5)
    
    Returns:
      {
        "success": bool,
        "cases": [
          {
            "id": "case_id",
            "case_number": "00001234",
            "subject": "...",
            "description": "...",
            "priority": "High",
            "status": "Open",
            "created_date": "2026-05-01",
            "last_modified_date": "2026-05-10"
          },
          ...
        ],
        "message": "..."
      }
    """
    if MOCK_SALESFORCE:
        # Return realistic mock open cases for testing
        mock_cases = [
            {
                "id": f"MOCK-{account_id}-CASE-001",
                "case_number": "00001001",
                "subject": "Billing discrepancy",
                "description": "Customer reports incorrect charge on invoice",
                "priority": "High",
                "status": "Open",
                "created_date": "2026-04-28",
                "last_modified_date": "2026-05-10",
            },
            {
                "id": f"MOCK-{account_id}-CASE-002",
                "case_number": "00001002",
                "subject": "Feature request",
                "description": "Customer wants API rate limit increase",
                "priority": "Medium",
                "status": "Open",
                "created_date": "2026-04-15",
                "last_modified_date": "2026-05-09",
            },
        ]
        logger.info("[MOCK SF] Fetched %d mock cases for account %s", len(mock_cases), account_id)
        return {
            "success": True,
            "cases": mock_cases,
            "message": f"Fetched {len(mock_cases)} mock open cases.",
        }

    try:
        access_token, instance_url = _get_access_token()

        # SOQL query to fetch open cases by External_User_Id__c (internal account_id)
        # Ordered by last modified date (newest first)
        soql_query = (
            f"SELECT Id, CaseNumber, Subject, Description, Priority, Status, CreatedDate, LastModifiedDate "
            f"FROM Case "
            f"WHERE External_User_Id__c = '{account_id}' "
            f"AND Status IN ('New', 'Open', 'Reopened') "
            f"ORDER BY LastModifiedDate DESC "
            f"LIMIT {limit}"
        )

        resp = requests.get(
            f"{instance_url}/services/data/{SF_API_VERSION}/query",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"q": soql_query},
            timeout=20,
        )
        resp.raise_for_status()
        result = resp.json()

        cases = []
        for record in result.get("records", []):
            cases.append({
                "id": record.get("Id"),
                "case_number": record.get("CaseNumber"),
                "subject": record.get("Subject", ""),
                "description": record.get("Description", ""),
                "priority": record.get("Priority", ""),
                "status": record.get("Status", ""),
                "created_date": record.get("CreatedDate", ""),
                "last_modified_date": record.get("LastModifiedDate", ""),
            })

        logger.info("SF fetched %d open cases for account %s", len(cases), account_id)
        return {
            "success": True,
            "cases": cases,
            "message": f"Fetched {len(cases)} open cases from Salesforce.",
        }

    except requests.HTTPError as exc:
        logger.error("SF HTTP error: %s – %s", exc.response.status_code, exc.response.text)
        return {"success": False, "cases": [], "error": str(exc), "detail": exc.response.text}
    except Exception as exc:
        logger.error("SF unexpected error: %s", exc)
        return {"success": False, "cases": [], "error": str(exc)}
