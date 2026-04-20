import json
import logging
import requests
from tenacity import retry, stop_after_attempt, wait_exponential
from app.config import settings
from app.security_utils import (
    escape_soql_string, validate_soql_user_id, validate_soql_status,
    validate_string_field
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class SalesforceClient:
    def __init__(self):
        self.access_token = None
        self.instance_url = None
        self.api_version = getattr(settings, 'SF_API_VERSION', 'v61.0')

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def login(self):
        """Authenticate with Salesforce using OAuth2 client credentials flow"""
        url = f"{settings.SF_LOGIN_URL}/services/oauth2/token"

        payload = {
            "grant_type": "client_credentials",
            "client_id": settings.SF_CLIENT_ID,
            "client_secret": settings.SF_CLIENT_SECRET
        }

        logger.info(f"Attempting Salesforce login at {url}")
        try:
            response = requests.post(url, data=payload, timeout=20)
            logger.info(f"Salesforce response status: {response.status_code}")
            # SECURITY: Do NOT log response body - contains access tokens!
            
            response.raise_for_status()
            data = response.json()
            self.access_token = data.get("access_token")
            self.instance_url = data.get("instance_url")
            
            if not self.access_token or not self.instance_url:
                raise ValueError("Missing access_token or instance_url in Salesforce response")
            
            logger.info(f"Successfully authenticated with Salesforce instance")
            
        except requests.exceptions.Timeout:
            logger.error("Salesforce login timeout after 20 seconds")
            raise
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Failed to connect to Salesforce: {type(e).__name__}")
            raise
        except requests.exceptions.HTTPError as e:
            logger.error(f"Salesforce authentication failed with status {e.response.status_code}")
            # SECURITY: Don't log response body
            raise
        except (ValueError, KeyError) as e:
            logger.error(f"Invalid Salesforce response format: {type(e).__name__}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during Salesforce login: {type(e).__name__}")
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def create_case(self, subject, description, user_id=None, backend_context=None, agent_result=None):
        """
        Create a new Salesforce case with input validation
        
        Args:
            subject: Case subject (required, max 255 chars)
            description: Case description (required, max 4000 chars)
            user_id: External user identifier (optional, validated)
            backend_context: Additional context data (optional)
            agent_result: Agent processing result (optional)
        """
        # INPUT VALIDATION ✅
        try:
            subject = validate_string_field(subject, "subject", min_length=1, max_length=255)
            description = validate_string_field(description, "description", min_length=1, max_length=4000)
            
            if user_id:
                user_id = validate_string_field(user_id, "user_id", min_length=1, max_length=255)
                if not validate_soql_user_id(user_id):
                    raise ValueError("Invalid user_id format")
        except ValueError as e:
            logger.error(f"Invalid case creation parameters: {str(e)}")
            raise
        
        if not self.access_token:
            self.login()

        url = f"{self.instance_url}/services/data/{self.api_version}/sobjects/Case"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        # Safely serialize backend_context
        backend_context_value = ""
        if backend_context:
            try:
                backend_context_value = json.dumps(backend_context, indent=2)[:4000]  # Limit to 4000 chars
            except (TypeError, ValueError) as e:
                logger.warning(f"Could not serialize backend_context: {e}")
                backend_context_value = ""
        
        # Safely handle agent_result
        agent_result = agent_result or {}

        payload = {
            "Subject": subject,
            "Description": description,
            "Origin": "Web",
            "Status": "New",
            "External_User_Id__c": user_id,
            "Source_App__c": "Agentic",
            "Backend_Context__c": backend_context_value,
            "Agent_Status__c": str(agent_result.get("status", "New"))[:50],
            "Agent_Summary__c": str(agent_result.get("summary", ""))[:4000],
            "Agent_Category__c": str(agent_result.get("category", ""))[:50],
            "Agent_Priority__c": str(agent_result.get("priority", "Medium"))[:20]
        }

        logger.info(f"Creating Salesforce case with subject: {subject[:50]}")
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=20)
            response.raise_for_status()
            result = response.json()
            logger.info(f"Case created successfully: {result.get('id')}")
            return result
        except requests.exceptions.Timeout:
            logger.error("Salesforce create_case timeout")
            raise
        except requests.exceptions.HTTPError as e:
            logger.error(f"Failed to create case with status {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating case: {type(e).__name__}")
            raise


    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def update_case(self, case_id, subject=None, description=None, status=None, priority=None, agent_result=None):
        """Update an existing Salesforce case"""
        # INPUT VALIDATION ✅
        try:
            case_id = validate_string_field(case_id, "case_id", min_length=15, max_length=18)
        except ValueError as e:
            logger.error(f"Invalid case_id: {str(e)}")
            raise
        
        if not self.access_token:
            self.login()

        url = f"{self.instance_url}/services/data/{self.api_version}/sobjects/Case/{case_id}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        payload = {}
        
        if subject:
            try:
                payload["Subject"] = validate_string_field(subject, "subject", max_length=255)
            except ValueError:
                pass
        
        if description:
            try:
                payload["Description"] = validate_string_field(description, "description", max_length=4000)
            except ValueError:
                pass
        
        if status:
            payload["Status"] = status
        
        if priority:
            payload["Priority"] = priority
        
        # Update custom fields if agent_result provided
        if agent_result and isinstance(agent_result, dict):
            if agent_result.get("status"):
                payload["Agent_Status__c"] = str(agent_result.get("status"))[:50]
            if agent_result.get("summary"):
                payload["Agent_Summary__c"] = str(agent_result.get("summary"))[:4000]
            if agent_result.get("category"):
                payload["Agent_Category__c"] = str(agent_result.get("category"))[:50]
            if agent_result.get("priority"):
                payload["Agent_Priority__c"] = str(agent_result.get("priority"))[:20]

        logger.info(f"Updating Salesforce case {case_id}")
        
        try:
            response = requests.patch(url, headers=headers, json=payload, timeout=20)
            response.raise_for_status()
            logger.info(f"Case {case_id} updated successfully")
            return {"id": case_id, "success": True}
        except requests.exceptions.Timeout:
            logger.error(f"Timeout updating case {case_id}")
            raise
        except requests.exceptions.HTTPError as e:
            logger.error(f"Failed to update case {case_id} with status {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error updating case {case_id}: {type(e).__name__}")
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def add_comment_to_case(self, case_id, comment_text):
        """Add a comment/note to an existing Salesforce case"""
        # INPUT VALIDATION ✅
        try:
            case_id = validate_string_field(case_id, "case_id", min_length=15, max_length=18)
            comment_text = validate_string_field(comment_text, "comment_text", min_length=1, max_length=4000)
        except ValueError as e:
            logger.error(f"Invalid parameters: {str(e)}")
            raise
        
        if not self.access_token:
            self.login()

        url = f"{self.instance_url}/services/data/{self.api_version}/sobjects/CaseComment"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        payload = {
            "ParentId": case_id,
            "CommentBody": comment_text
        }

        logger.info(f"Adding comment to case {case_id}")
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=20)
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"Comment added to case {case_id}: {result.get('id')}")
            return result
        except requests.exceptions.Timeout:
            logger.error(f"Timeout adding comment to case {case_id}")
            raise
        except requests.exceptions.HTTPError as e:
            logger.error(f"Failed to add comment to case {case_id} with status {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error adding comment: {type(e).__name__}")
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def close_case(self, case_id, subject=None, summary=None, resolution_notes=None):
        """Close an existing Salesforce case"""
        # INPUT VALIDATION ✅
        try:
            case_id = validate_string_field(case_id, "case_id", min_length=15, max_length=18)
        except ValueError as e:
            logger.error(f"Invalid case_id: {str(e)}")
            raise
        
        if not self.access_token:
            self.login()

        url = f"{self.instance_url}/services/data/{self.api_version}/sobjects/Case/{case_id}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        payload = {
            "Status": "Closed",
            "Agent_Status__c": "Closed"
        }
        
        if subject:
            try:
                payload["Subject"] = validate_string_field(subject, "subject", max_length=255)
            except ValueError:
                pass
        
        if summary or resolution_notes:
            summary_text = summary or resolution_notes
            try:
                payload["Agent_Summary__c"] = validate_string_field(summary_text, "summary", max_length=4000)
            except ValueError:
                pass

        logger.info(f"Closing Salesforce case {case_id}")
        
        try:
            response = requests.patch(url, headers=headers, json=payload, timeout=20)
            response.raise_for_status()
            logger.info(f"Case {case_id} closed successfully")
            return {"id": case_id, "status": "Closed", "success": True}
        except requests.exceptions.Timeout:
            logger.error(f"Timeout closing case {case_id}")
            raise
        except requests.exceptions.HTTPError as e:
            logger.error(f"Failed to close case {case_id} with status {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error closing case: {type(e).__name__}")
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def lookup_cases_by_user(self, user_id, status="New"):
        """
        Query Salesforce for existing cases by user
        
        SECURITY: Uses SOQL string escaping to prevent injection attacks ✅
        """
        # INPUT VALIDATION ✅
        try:
            user_id = validate_string_field(user_id, "user_id", min_length=1, max_length=255)
            if not validate_soql_user_id(user_id):
                raise ValueError("Invalid user_id format")
            
            if not validate_soql_status(status):
                raise ValueError(f"Invalid status: {status}")
        except ValueError as e:
            logger.error(f"Invalid lookup parameters: {str(e)}")
            raise
        
        if not self.access_token:
            self.login()

        # SECURITY: Escape SOQL strings to prevent injection ✅
        escaped_user_id = escape_soql_string(user_id)
        escaped_status = escape_soql_string(status)
        
        query = f"SELECT Id, CaseNumber, Subject, Status, CreatedDate FROM Case WHERE External_User_Id__c = '{escaped_user_id}' AND Status = '{escaped_status}' ORDER BY CreatedDate DESC LIMIT 5"
        
        url = f"{self.instance_url}/services/data/{self.api_version}/query"
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        params = {"q": query}
        
        logger.debug(f"Looking up cases for user (SOQL query executed safely)")
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=20)
            response.raise_for_status()
            result = response.json()
            records = result.get("records", [])
            logger.info(f"Found {len(records)} cases")
            return records
        except requests.exceptions.Timeout:
            logger.error("Timeout looking up cases")
            return []
        except requests.exceptions.HTTPError as e:
            logger.error(f"Failed to lookup cases with status {e.response.status_code}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error looking up cases: {type(e).__name__}")
            return []

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def create_contract(self, account_id, tenant_name, property_address, move_in_date, move_out_date, rent_amount, user_id=None, backend_context=None):
        """Create a new Salesforce Contract for a rental property"""
        # INPUT VALIDATION ✅
        try:
            account_id = validate_string_field(account_id, "account_id", min_length=15, max_length=18)
            tenant_name = validate_string_field(tenant_name, "tenant_name", max_length=255)
            property_address = validate_string_field(property_address, "property_address", max_length=255)
            
            if user_id:
                user_id = validate_string_field(user_id, "user_id", max_length=255)
                if not validate_soql_user_id(user_id):
                    raise ValueError("Invalid user_id format")
        except ValueError as e:
            logger.error(f"Invalid contract creation parameters: {str(e)}")
            raise
        
        if not self.access_token:
            self.login()

        url = f"{self.instance_url}/services/data/{self.api_version}/sobjects/Contract"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        # Safely serialize backend_context
        backend_context_value = ""
        if backend_context:
            try:
                backend_context_value = json.dumps(backend_context, indent=2)[:4000]
            except (TypeError, ValueError):
                backend_context_value = ""

        payload = {
            "AccountId": account_id,
            "ContractTerm": 12,
            "Status": "Draft",
            "External_User_Id__c": user_id,
            "Tenant_Name__c": tenant_name,
            "Property_Address__c": property_address,
            "Move_In_Date__c": move_in_date,
            "Move_Out_Date__c": move_out_date,
            "Monthly_Rent__c": rent_amount,
            "Source_App__c": "Agentic",
            "Backend_Context__c": backend_context_value
        }

        logger.info(f"Creating Salesforce contract for tenant at {property_address[:30]}")
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=20)
            response.raise_for_status()
            result = response.json()
            logger.info(f"Contract created successfully: {result.get('id')}")
            return result
        except requests.exceptions.Timeout:
            logger.error("Timeout creating contract")
            raise
        except requests.exceptions.HTTPError as e:
            logger.error(f"Failed to create contract with status {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating contract: {type(e).__name__}")
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def update_contract(self, contract_id, status=None, move_out_date=None, rent_amount=None):
        """Update an existing Salesforce contract"""
        if not self.access_token:
            self.login()

        url = f"{self.instance_url}/services/data/{self.api_version}/sobjects/Contract/{contract_id}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        payload = {}
        
        if status:
            payload["Status"] = status
        if move_out_date:
            payload["Move_Out_Date__c"] = move_out_date
        if rent_amount:
            payload["Monthly_Rent__c"] = rent_amount

        logger.info(f"Updating Salesforce contract {contract_id}")
        
        try:
            response = requests.patch(url, headers=headers, json=payload, timeout=20)
            response.raise_for_status()
            logger.info(f"Contract {contract_id} updated successfully")
            return {"id": contract_id, "success": True}
        except requests.exceptions.Timeout:
            logger.error(f"Timeout updating contract {contract_id}")
            raise
        except requests.exceptions.HTTPError as e:
            logger.error(f"Failed to update contract {contract_id} with status {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error updating contract: {type(e).__name__}")
            raise