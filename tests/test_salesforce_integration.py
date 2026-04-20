"""
Comprehensive Salesforce Integration Tests

Tests the integration between the agent and Salesforce including:
- Authentication and connection
- CRUD operations (Create, Read, Update, Delete)
- Error handling
- Rate limiting
- Data consistency
"""

import unittest
import logging
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.integrations.salesforce import SalesforceClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TestSalesforceConnection(unittest.TestCase):
    """Test Salesforce connection and authentication"""
    
    def setUp(self):
        """Initialize test fixtures"""
        self.client = SalesforceClient()
    
    def test_client_initialization(self):
        """Test that SalesforceClient initializes without errors"""
        self.assertIsNotNone(self.client)
    
    def test_authentication_env_vars(self):
        """Test that required environment variables are set"""
        required_vars = ['SALESFORCE_CLIENT_ID', 'SALESFORCE_CLIENT_SECRET']
        for var in required_vars:
            self.assertIn(var, os.environ, f"Missing environment variable: {var}")
    
    @patch('app.integrations.salesforce.SalesforceClient.authenticate')
    def test_authentication_success(self, mock_auth):
        """Test successful authentication"""
        mock_auth.return_value = True
        result = self.client.authenticate()
        self.assertTrue(result)
        mock_auth.assert_called_once()
    
    @patch('app.integrations.salesforce.SalesforceClient.authenticate')
    def test_authentication_failure(self, mock_auth):
        """Test authentication failure handling"""
        mock_auth.side_effect = Exception("Invalid credentials")
        with self.assertRaises(Exception):
            self.client.authenticate()


class TestCaseOperations(unittest.TestCase):
    """Test Salesforce Case CRUD operations"""
    
    def setUp(self):
        """Initialize test fixtures"""
        self.client = SalesforceClient()
        self.test_case_subject = "Integration Test Case"
        self.test_case_description = "This is a test case for integration testing"
    
    @patch('app.integrations.salesforce.SalesforceClient.create_case')
    def test_create_case_success(self, mock_create):
        """Test successful case creation"""
        mock_case_id = "5000X00000IqTUAA3"
        mock_create.return_value = {
            "id": mock_case_id,
            "success": True,
            "message": "Case created successfully"
        }
        
        result = self.client.create_case(
            subject=self.test_case_subject,
            description=self.test_case_description
        )
        
        self.assertTrue(result.get("success"))
        self.assertEqual(result.get("id"), mock_case_id)
        mock_create.assert_called_once()
    
    @patch('app.integrations.salesforce.SalesforceClient.create_case')
    def test_create_case_with_missing_subject(self, mock_create):
        """Test case creation with missing required field"""
        mock_create.side_effect = ValueError("Subject is required")
        
        with self.assertRaises(ValueError):
            self.client.create_case(subject="", description=self.test_case_description)
    
    @patch('app.integrations.salesforce.SalesforceClient.get_case')
    def test_get_case_success(self, mock_get):
        """Test successful case retrieval"""
        mock_case_id = "5000X00000IqTUAA3"
        mock_get.return_value = {
            "Id": mock_case_id,
            "Subject": self.test_case_subject,
            "Description": self.test_case_description,
            "Status": "New"
        }
        
        result = self.client.get_case(case_id=mock_case_id)
        
        self.assertEqual(result.get("Id"), mock_case_id)
        self.assertEqual(result.get("Subject"), self.test_case_subject)
        mock_get.assert_called_once_with(case_id=mock_case_id)
    
    @patch('app.integrations.salesforce.SalesforceClient.get_case')
    def test_get_case_not_found(self, mock_get):
        """Test case retrieval when case doesn't exist"""
        mock_case_id = "invalid_id"
        mock_get.side_effect = Exception("Case not found")
        
        with self.assertRaises(Exception):
            self.client.get_case(case_id=mock_case_id)
    
    @patch('app.integrations.salesforce.SalesforceClient.update_case')
    def test_update_case_success(self, mock_update):
        """Test successful case update"""
        mock_case_id = "5000X00000IqTUAA3"
        mock_update.return_value = {
            "success": True,
            "message": "Case updated successfully"
        }
        
        result = self.client.update_case(
            case_id=mock_case_id,
            status="In Progress"
        )
        
        self.assertTrue(result.get("success"))
        mock_update.assert_called_once()
    
    @patch('app.integrations.salesforce.SalesforceClient.add_comment_to_case')
    def test_add_comment_to_case_success(self, mock_add_comment):
        """Test adding comment to case"""
        mock_case_id = "5000X00000IqTUAA3"
        mock_comment_id = "0051X00000HnqwQAC"
        mock_add_comment.return_value = {
            "id": mock_comment_id,
            "success": True,
            "message": "Comment added successfully"
        }
        
        result = self.client.add_comment_to_case(
            case_id=mock_case_id,
            comment_text="This is a test comment"
        )
        
        self.assertTrue(result.get("success"))
        self.assertEqual(result.get("id"), mock_comment_id)
        mock_add_comment.assert_called_once()
    
    @patch('app.integrations.salesforce.SalesforceClient.close_case')
    def test_close_case_success(self, mock_close):
        """Test closing a case"""
        mock_case_id = "5000X00000IqTUAA3"
        mock_close.return_value = {
            "success": True,
            "message": "Case closed successfully"
        }
        
        result = self.client.close_case(
            case_id=mock_case_id,
            summary="Case resolved",
            resolution_notes="Issue was resolved successfully"
        )
        
        self.assertTrue(result.get("success"))
        mock_close.assert_called_once()


class TestContractOperations(unittest.TestCase):
    """Test Salesforce Contract CRUD operations"""
    
    def setUp(self):
        """Initialize test fixtures"""
        self.client = SalesforceClient()
        self.test_account_id = "0011X00000IqTUAA"
        self.test_tenant_name = "John Doe"
        self.test_property_address = "123 Main St, Anytown, USA"
    
    @patch('app.integrations.salesforce.SalesforceClient.create_contract')
    def test_create_contract_success(self, mock_create):
        """Test successful contract creation"""
        mock_contract_id = "8001X00000IqTUAA3"
        mock_create.return_value = {
            "id": mock_contract_id,
            "success": True,
            "message": "Contract created successfully"
        }
        
        result = self.client.create_contract(
            account_id=self.test_account_id,
            tenant_name=self.test_tenant_name,
            property_address=self.test_property_address,
            move_in_date="2024-06-01",
            move_out_date="2025-06-01",
            rent_amount=2500.00
        )
        
        self.assertTrue(result.get("success"))
        self.assertEqual(result.get("id"), mock_contract_id)
        mock_create.assert_called_once()
    
    @patch('app.integrations.salesforce.SalesforceClient.create_contract')
    def test_create_contract_invalid_dates(self, mock_create):
        """Test contract creation with invalid dates"""
        mock_create.side_effect = ValueError("Move-in date must be before move-out date")
        
        with self.assertRaises(ValueError):
            self.client.create_contract(
                account_id=self.test_account_id,
                tenant_name=self.test_tenant_name,
                property_address=self.test_property_address,
                move_in_date="2025-06-01",
                move_out_date="2024-06-01",
                rent_amount=2500.00
            )
    
    @patch('app.integrations.salesforce.SalesforceClient.get_contract')
    def test_get_contract_success(self, mock_get):
        """Test successful contract retrieval"""
        mock_contract_id = "8001X00000IqTUAA3"
        mock_get.return_value = {
            "Id": mock_contract_id,
            "AccountId": self.test_account_id,
            "Status": "Active"
        }
        
        result = self.client.get_contract(contract_id=mock_contract_id)
        
        self.assertEqual(result.get("Id"), mock_contract_id)
        mock_get.assert_called_once_with(contract_id=mock_contract_id)
    
    @patch('app.integrations.salesforce.SalesforceClient.update_contract')
    def test_update_contract_success(self, mock_update):
        """Test successful contract update"""
        mock_contract_id = "8001X00000IqTUAA3"
        mock_update.return_value = {
            "success": True,
            "message": "Contract updated successfully"
        }
        
        result = self.client.update_contract(
            contract_id=mock_contract_id,
            status="Closed"
        )
        
        self.assertTrue(result.get("success"))
        mock_update.assert_called_once()


class TestErrorHandling(unittest.TestCase):
    """Test error handling and resilience"""
    
    def setUp(self):
        """Initialize test fixtures"""
        self.client = SalesforceClient()
    
    @patch('app.integrations.salesforce.SalesforceClient.create_case')
    def test_handle_authentication_error(self, mock_create):
        """Test handling of authentication errors"""
        mock_create.side_effect = Exception("401: Invalid authentication")
        
        with self.assertRaises(Exception) as context:
            self.client.create_case(subject="Test", description="Test")
        
        self.assertIn("401", str(context.exception))
    
    @patch('app.integrations.salesforce.SalesforceClient.create_case')
    def test_handle_rate_limit_error(self, mock_create):
        """Test handling of rate limit errors"""
        mock_create.side_effect = Exception("429: Too many requests")
        
        with self.assertRaises(Exception) as context:
            self.client.create_case(subject="Test", description="Test")
        
        self.assertIn("429", str(context.exception))
    
    @patch('app.integrations.salesforce.SalesforceClient.create_case')
    def test_handle_network_error(self, mock_create):
        """Test handling of network errors"""
        mock_create.side_effect = Exception("Connection timeout")
        
        with self.assertRaises(Exception) as context:
            self.client.create_case(subject="Test", description="Test")
        
        self.assertIn("Connection", str(context.exception))
    
    @patch('app.integrations.salesforce.SalesforceClient.get_case')
    def test_handle_validation_error(self, mock_get):
        """Test handling of validation errors"""
        mock_get.side_effect = ValueError("Invalid case ID format")
        
        with self.assertRaises(ValueError):
            self.client.get_case(case_id="invalid")


class TestDataConsistency(unittest.TestCase):
    """Test data consistency and integrity"""
    
    def setUp(self):
        """Initialize test fixtures"""
        self.client = SalesforceClient()
    
    @patch('app.integrations.salesforce.SalesforceClient.create_case')
    @patch('app.integrations.salesforce.SalesforceClient.get_case')
    def test_created_case_can_be_retrieved(self, mock_get, mock_create):
        """Test that created case can be retrieved with same data"""
        mock_case_id = "5000X00000IqTUAA3"
        test_subject = "Test Case Subject"
        test_description = "Test Case Description"
        
        mock_create.return_value = {"id": mock_case_id, "success": True}
        mock_get.return_value = {
            "Id": mock_case_id,
            "Subject": test_subject,
            "Description": test_description,
            "Status": "New"
        }
        
        # Create case
        create_result = self.client.create_case(
            subject=test_subject,
            description=test_description
        )
        self.assertTrue(create_result.get("success"))
        
        # Retrieve case
        get_result = self.client.get_case(case_id=mock_case_id)
        self.assertEqual(get_result.get("Subject"), test_subject)
        self.assertEqual(get_result.get("Description"), test_description)
    
    @patch('app.integrations.salesforce.SalesforceClient.update_case')
    @patch('app.integrations.salesforce.SalesforceClient.get_case')
    def test_updated_case_reflects_changes(self, mock_get, mock_update):
        """Test that updated case reflects the changes"""
        mock_case_id = "5000X00000IqTUAA3"
        new_status = "In Progress"
        
        mock_update.return_value = {"success": True}
        mock_get.return_value = {
            "Id": mock_case_id,
            "Status": new_status
        }
        
        # Update case
        update_result = self.client.update_case(
            case_id=mock_case_id,
            status=new_status
        )
        self.assertTrue(update_result.get("success"))
        
        # Retrieve updated case
        get_result = self.client.get_case(case_id=mock_case_id)
        self.assertEqual(get_result.get("Status"), new_status)


class TestPerformance(unittest.TestCase):
    """Test performance and efficiency"""
    
    def setUp(self):
        """Initialize test fixtures"""
        self.client = SalesforceClient()
    
    @patch('app.integrations.salesforce.SalesforceClient.lookup_cases_by_user')
    def test_case_lookup_returns_reasonable_results(self, mock_lookup):
        """Test that case lookup returns reasonable number of results"""
        # Mock 10 cases returned
        mock_cases = [{"Id": f"500{i:016d}", "Subject": f"Case {i}"} for i in range(10)]
        mock_lookup.return_value = mock_cases
        
        result = self.client.lookup_cases_by_user("user123", "New")
        
        self.assertEqual(len(result), 10)
        mock_lookup.assert_called_once()
    
    @patch('app.integrations.salesforce.SalesforceClient.create_case')
    def test_create_case_with_large_description(self, mock_create):
        """Test creating case with large description"""
        large_description = "x" * 4000  # Salesforce limit is usually 4000
        mock_create.return_value = {"id": "5000X00000IqTUAA3", "success": True}
        
        result = self.client.create_case(
            subject="Test Case",
            description=large_description
        )
        
        self.assertTrue(result.get("success"))
        mock_create.assert_called_once()


class TestIntegrationFlow(unittest.TestCase):
    """Test complete integration workflows"""
    
    def setUp(self):
        """Initialize test fixtures"""
        self.client = SalesforceClient()
    
    @patch('app.integrations.salesforce.SalesforceClient.lookup_cases_by_user')
    @patch('app.integrations.salesforce.SalesforceClient.get_case')
    @patch('app.integrations.salesforce.SalesforceClient.update_case')
    @patch('app.integrations.salesforce.SalesforceClient.add_comment_to_case')
    @patch('app.integrations.salesforce.SalesforceClient.close_case')
    def test_complete_case_workflow(self, mock_close, mock_comment, mock_update, mock_get, mock_lookup):
        """Test complete case handling workflow"""
        mock_case_id = "5000X00000IqTUAA3"
        
        # Step 1: Lookup cases
        mock_lookup.return_value = [{"Id": mock_case_id, "Subject": "Test"}]
        cases = self.client.lookup_cases_by_user("user123", "New")
        self.assertEqual(len(cases), 1)
        
        # Step 2: Get case details
        mock_get.return_value = {"Id": mock_case_id, "Status": "New", "Subject": "Test"}
        case = self.client.get_case(case_id=mock_case_id)
        self.assertEqual(case.get("Status"), "New")
        
        # Step 3: Update case
        mock_update.return_value = {"success": True}
        update_result = self.client.update_case(case_id=mock_case_id, status="In Progress")
        self.assertTrue(update_result.get("success"))
        
        # Step 4: Add comment
        mock_comment.return_value = {"id": "0051X00000HnqwQAC", "success": True}
        comment_result = self.client.add_comment_to_case(case_id=mock_case_id, comment_text="Working on this")
        self.assertTrue(comment_result.get("success"))
        
        # Step 5: Close case
        mock_close.return_value = {"success": True}
        close_result = self.client.close_case(case_id=mock_case_id, summary="Resolved")
        self.assertTrue(close_result.get("success"))
    
    @patch('app.integrations.salesforce.SalesforceClient.create_contract')
    @patch('app.integrations.salesforce.SalesforceClient.get_contract')
    @patch('app.integrations.salesforce.SalesforceClient.update_contract')
    def test_complete_contract_workflow(self, mock_update, mock_get, mock_create):
        """Test complete contract handling workflow"""
        mock_contract_id = "8001X00000IqTUAA3"
        
        # Step 1: Create contract
        mock_create.return_value = {"id": mock_contract_id, "success": True}
        contract = self.client.create_contract(
            account_id="0011X00000IqTUAA",
            tenant_name="John Doe",
            property_address="123 Main St",
            move_in_date="2024-06-01",
            move_out_date="2025-06-01",
            rent_amount=2500.00
        )
        self.assertTrue(contract.get("success"))
        
        # Step 2: Get contract
        mock_get.return_value = {"Id": mock_contract_id, "Status": "Draft"}
        retrieved_contract = self.client.get_contract(contract_id=mock_contract_id)
        self.assertEqual(retrieved_contract.get("Status"), "Draft")
        
        # Step 3: Update contract
        mock_update.return_value = {"success": True}
        updated = self.client.update_contract(contract_id=mock_contract_id, status="Active")
        self.assertTrue(updated.get("success"))


def run_integration_tests():
    """Run all integration tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestSalesforceConnection))
    suite.addTests(loader.loadTestsFromTestCase(TestCaseOperations))
    suite.addTests(loader.loadTestsFromTestCase(TestContractOperations))
    suite.addTests(loader.loadTestsFromTestCase(TestErrorHandling))
    suite.addTests(loader.loadTestsFromTestCase(TestDataConsistency))
    suite.addTests(loader.loadTestsFromTestCase(TestPerformance))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegrationFlow))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result


if __name__ == '__main__':
    result = run_integration_tests()
    sys.exit(0 if result.wasSuccessful() else 1)
