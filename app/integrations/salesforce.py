import json
import logging
import requests
from tenacity import retry, stop_after_attempt, wait_exponential
from app.config import settings

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class SalesforceClient:
    def __init__(self):
        self.access_token = None
        self.instance_url = None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def login(self):
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
            logger.info(f"Salesforce response body: {response.text}")
            response.raise_for_status()
            data = response.json()
            self.access_token = data["access_token"]
            self.instance_url = data["instance_url"]
            logger.info(f"Successfully authenticated with Salesforce: {self.instance_url}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Salesforce login failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response status: {e.response.status_code}, body: {e.response.text}")
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def create_case(self, subject, description, user_id=None, backend_context=None, agent_result=None):
        if not self.access_token:
            self.login()

        url = f"{self.instance_url}/services/data/v61.0/sobjects/Case"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        backend_context_value = json.dumps(backend_context, indent=2) if isinstance(backend_context, (dict, list)) else backend_context or ""
        agent_result = agent_result or {}

        payload = {
            "Subject": subject,
            "Description": description,
            "Origin": "Web",
            "Status": "New",
            "External_User_Id__c": user_id,
            "Source_App__c": "Agentic",
            "Backend_Context__c": backend_context_value,
            "Agent_Status__c": agent_result.get("status", "New"),
            "Agent_Summary__c": agent_result.get("summary", ""),
            "Agent_Category__c": agent_result.get("category", ""),
            "Agent_Priority__c": agent_result.get("priority", "Medium")
        }

        response = requests.post(url, headers=headers, json=payload, timeout=20)
        response.raise_for_status()
        return response.json()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def update_case(self, case_id, subject=None, description=None, status=None, priority=None, agent_result=None):
        """Update an existing Salesforce case"""
        if not self.access_token:
            self.login()

        url = f"{self.instance_url}/services/data/v61.0/sobjects/Case/{case_id}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        payload = {}
        
        if subject:
            payload["Subject"] = subject
        if description:
            payload["Description"] = description
        if status:
            payload["Status"] = status
        if priority:
            payload["Priority"] = priority
        
        # Update custom fields if agent_result provided
        if agent_result:
            agent_result = agent_result or {}
            if agent_result.get("status"):
                payload["Agent_Status__c"] = agent_result.get("status")
            if agent_result.get("summary"):
                payload["Agent_Summary__c"] = agent_result.get("summary")
            if agent_result.get("category"):
                payload["Agent_Category__c"] = agent_result.get("category")
            if agent_result.get("priority"):
                payload["Agent_Priority__c"] = agent_result.get("priority")

        logger.info(f"Updating Salesforce case {case_id} with payload: {json.dumps(payload)}")
        
        try:
            response = requests.patch(url, headers=headers, json=payload, timeout=20)
            response.raise_for_status()
            logger.info(f"Case {case_id} updated successfully")
            return {"id": case_id, "success": True}
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to update case {case_id}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response status: {e.response.status_code}, body: {e.response.text}")
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def add_comment_to_case(self, case_id, comment_text):
        """Add a comment/note to an existing Salesforce case"""
        if not self.access_token:
            self.login()

        url = f"{self.instance_url}/services/data/v61.0/sobjects/CaseComment"
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
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to add comment to case {case_id}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response status: {e.response.status_code}, body: {e.response.text}")
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def close_case(self, case_id, subject=None, summary=None, resolution_notes=None):
        """Close an existing Salesforce case"""
        if not self.access_token:
            self.login()

        url = f"{self.instance_url}/services/data/v61.0/sobjects/Case/{case_id}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        payload = {
            "Status": "Closed",
            "Agent_Status__c": "Closed"
        }
        
        if subject:
            payload["Subject"] = subject
        if summary:
            payload["Agent_Summary__c"] = summary
        if resolution_notes:
            payload["Agent_Summary__c"] = resolution_notes

        logger.info(f"Closing Salesforce case {case_id}")
        
        try:
            response = requests.patch(url, headers=headers, json=payload, timeout=20)
            response.raise_for_status()
            logger.info(f"Case {case_id} closed successfully")
            return {"id": case_id, "status": "Closed", "success": True}
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to close case {case_id}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response status: {e.response.status_code}, body: {e.response.text}")
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def lookup_cases_by_user(self, user_id, status="New"):
        """Query Salesforce for existing cases by user"""
        if not self.access_token:
            self.login()

        # Query for recent open cases for this user
        query = f"SELECT Id, CaseNumber, Subject, Status, CreatedDate FROM Case WHERE External_User_Id__c = '{user_id}' AND Status = '{status}' ORDER BY CreatedDate DESC LIMIT 5"
        url = f"{self.instance_url}/services/data/v61.0/query"
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        params = {"q": query}
        
        logger.info(f"Looking up cases for user {user_id}")
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=20)
            response.raise_for_status()
            result = response.json()
            records = result.get("records", [])
            logger.info(f"Found {len(records)} cases for user {user_id}")
            return records
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to lookup cases for user {user_id}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response status: {e.response.status_code}, body: {e.response.text}")
            return []

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def create_contract(self, account_id, tenant_name, property_address, move_in_date, move_out_date, rent_amount, user_id=None, backend_context=None):
        """Create a new Salesforce Contract for a rental property"""
        if not self.access_token:
            self.login()

        url = f"{self.instance_url}/services/data/v61.0/sobjects/Contract"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        backend_context_value = json.dumps(backend_context, indent=2) if isinstance(backend_context, (dict, list)) else backend_context or ""

        payload = {
            "AccountId": account_id,  # Required: Parent Account
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

        logger.info(f"Creating Salesforce contract for tenant {tenant_name} at {property_address} (Account: {account_id})")
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=20)
            response.raise_for_status()
            result = response.json()
            logger.info(f"Contract created successfully: {result.get('id')}")
            return result
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to create contract: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response status: {e.response.status_code}, body: {e.response.text}")
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def update_contract(self, contract_id, status=None, move_out_date=None, rent_amount=None):
        """Update an existing Salesforce contract"""
        if not self.access_token:
            self.login()

        url = f"{self.instance_url}/services/data/v61.0/sobjects/Contract/{contract_id}"
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

        logger.info(f"Updating Salesforce contract {contract_id} with payload: {json.dumps(payload)}")
        
        try:
            response = requests.patch(url, headers=headers, json=payload, timeout=20)
            response.raise_for_status()
            logger.info(f"Contract {contract_id} updated successfully")
            return {"id": contract_id, "success": True}
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to update contract {contract_id}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response status: {e.response.status_code}, body: {e.response.text}")
            raise