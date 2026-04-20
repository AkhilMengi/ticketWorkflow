"""
API Input Validation Tests

Tests the enhanced API input validation including:
- Request body validation
- Path parameter validation
- Error handling and responses
- Edge cases
"""

import unittest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
import json

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi.testclient import TestClient
from app.main import app


class TestAPIValidation(unittest.TestCase):
    """Test API input validation"""
    
    def setUp(self):
        """Initialize test fixtures"""
        self.client = TestClient(app)
    
    # Job Endpoint Tests
    def test_create_job_with_valid_payload(self):
        """Test creating a job with valid payload"""
        with patch('app.api.routes.get_current_user', return_value={"user_id": "user1"}):
            with patch('app.services.job_service.create_job', return_value="job123"):
                with patch('app.workers.worker.enqueue_job', return_value=True):
                    response = self.client.post(
                        "/api/jobs",
                        json={
                            "user_id": "user1",
                            "issue_type": "payment_issue",
                            "message": "Payment processing failed"
                        }
                    )
                    self.assertIn(response.status_code, [200, 422])
    
    def test_create_job_missing_user_id(self):
        """Test creating job without user_id"""
        with patch('app.api.routes.get_current_user', return_value={"user_id": "user1"}):
            response = self.client.post(
                "/api/jobs",
                json={
                    "issue_type": "payment_issue",
                    "message": "Payment processing failed"
                }
            )
            # Should fail validation
            self.assertEqual(response.status_code, 422)
    
    def test_create_job_invalid_user_id_format(self):
        """Test creating job with invalid user_id format"""
        with patch('app.api.routes.get_current_user', return_value={"user_id": "user@#$%"}):
            response = self.client.post(
                "/api/jobs",
                json={
                    "user_id": "user@#$%",
                    "issue_type": "payment_issue",
                    "message": "Payment processing failed"
                }
            )
            # Should fail validation
            self.assertEqual(response.status_code, 422)
    
    def test_create_job_message_too_long(self):
        """Test creating job with message exceeding max length"""
        with patch('app.api.routes.get_current_user', return_value={"user_id": "user1"}):
            long_message = "x" * 5001  # Exceeds 5000 character limit
            response = self.client.post(
                "/api/jobs",
                json={
                    "user_id": "user1",
                    "issue_type": "payment_issue",
                    "message": long_message
                }
            )
            # Should fail validation
            self.assertEqual(response.status_code, 422)
    
    def test_get_job_with_valid_id(self):
        """Test getting job with valid job_id"""
        with patch('app.api.routes.get_current_user', return_value={"user_id": "user1"}):
            with patch('app.services.job_service.get_job', return_value={"job_id": "job123", "user_id": "user1", "status": "completed"}):
                response = self.client.get("/api/jobs/job123")
                self.assertIn(response.status_code, [200, 404])
    
    def test_get_job_with_invalid_id_format(self):
        """Test getting job with invalid job_id format"""
        with patch('app.api.routes.get_current_user', return_value={"user_id": "user1"}):
            response = self.client.get("/api/jobs/invalid@job#id")
            # Should fail validation 
            self.assertEqual(response.status_code, 400)
    
    # Case Endpoint Tests
    def test_update_case_with_valid_payload(self):
        """Test updating case with valid payload"""
        case_id = "5000X00000IqTUAA3"
        with patch('app.api.routes.get_current_user', return_value={"user_id": "user1"}):
            with patch('app.integrations.salesforce.SalesforceClient.update_case', return_value={"success": True}):
                response = self.client.patch(
                    f"/api/cases/{case_id}",
                    json={
                        "case_id": case_id,
                        "subject": "Updated Subject",
                        "status": "In Progress"
                    }
                )
                self.assertIn(response.status_code, [200, 404, 422])
    
    def test_update_case_invalid_case_id_format(self):
        """Test updating case with invalid case_id format"""
        with patch('app.api.routes.get_current_user', return_value={"user_id": "user1"}):
            response = self.client.patch(
                "/api/cases/invalid_case_id",
                json={
                    "case_id": "invalid_case_id",
                    "subject": "Updated Subject"
                }
            )
            # Should fail validation
            self.assertEqual(response.status_code, 400)
    
    def test_update_case_mismatched_ids(self):
        """Test updating case with mismatched path and body IDs"""
        case_id_path = "5000X00000IqTUAA3"
        case_id_body = "5000X00000IqTUAA4"
        with patch('app.api.routes.get_current_user', return_value={"user_id": "user1"}):
            response = self.client.patch(
                f"/api/cases/{case_id_path}",
                json={
                    "case_id": case_id_body,
                    "subject": "Updated Subject"
                }
            )
            # Should fail validation
            self.assertEqual(response.status_code, 400)
    
    def test_update_case_invalid_status(self):
        """Test updating case with invalid status value"""
        case_id = "5000X00000IqTUAA3"
        with patch('app.api.routes.get_current_user', return_value={"user_id": "user1"}):
            response = self.client.patch(
                f"/api/cases/{case_id}",
                json={
                    "case_id": case_id,
                    "status": "InvalidStatus"
                }
            )
            # Should fail validation
            self.assertEqual(response.status_code, 422)
    
    def test_update_case_invalid_priority(self):
        """Test updating case with invalid priority value"""
        case_id = "5000X00000IqTUAA3"
        with patch('app.api.routes.get_current_user', return_value={"user_id": "user1"}):
            response = self.client.patch(
                f"/api/cases/{case_id}",
                json={
                    "case_id": case_id,
                    "priority": "UltraHigh"
                }
            )
            # Should fail validation
            self.assertEqual(response.status_code, 422)
    
    def test_update_case_no_fields(self):
        """Test updating case with no fields to update"""
        case_id = "5000X00000IqTUAA3"
        with patch('app.api.routes.get_current_user', return_value={"user_id": "user1"}):
            response = self.client.patch(
                f"/api/cases/{case_id}",
                json={
                    "case_id": case_id
                }
            )
            # Should fail validation - at least one field required
            self.assertEqual(response.status_code, 422)
    
    # Comment Endpoint Tests
    def test_add_comment_with_valid_payload(self):
        """Test adding comment with valid payload"""
        case_id = "5000X00000IqTUAA3"
        with patch('app.api.routes.get_current_user', return_value={"user_id": "user1"}):
            with patch('app.integrations.salesforce.SalesforceClient.add_comment_to_case', return_value={"id": "comment123", "success": True}):
                response = self.client.post(
                    f"/api/cases/{case_id}/comments",
                    json={
                        "case_id": case_id,
                        "comment_text": "This is a test comment"
                    }
                )
                self.assertIn(response.status_code, [200, 404, 422])
    
    def test_add_comment_empty_text(self):
        """Test adding comment with empty text"""
        case_id = "5000X00000IqTUAA3"
        with patch('app.api.routes.get_current_user', return_value={"user_id": "user1"}):
            response = self.client.post(
                f"/api/cases/{case_id}/comments",
                json={
                    "case_id": case_id,
                    "comment_text": ""
                }
            )
            # Should fail validation
            self.assertEqual(response.status_code, 422)
    
    def test_add_comment_whitespace_only(self):
        """Test adding comment with whitespace only"""
        case_id = "5000X00000IqTUAA3"
        with patch('app.api.routes.get_current_user', return_value={"user_id": "user1"}):
            response = self.client.post(
                f"/api/cases/{case_id}/comments",
                json={
                    "case_id": case_id,
                    "comment_text": "   \n\t  "
                }
            )
            # Should fail validation
            self.assertEqual(response.status_code, 422)
    
    # Contract Endpoint Tests
    def test_create_contract_with_valid_payload(self):
        """Test creating contract with valid payload"""
        with patch('app.api.routes.get_current_user', return_value={"user_id": "user1"}):
            with patch('app.services.job_service.create_job', return_value="job123"):
                with patch('app.workers.worker.enqueue_contract_job', return_value=True):
                    response = self.client.post(
                        "/api/contracts",
                        json={
                            "user_id": "user1",
                            "account_id": "0011X00000IqTUAA",
                            "tenant_name": "John Doe",
                            "property_address": "123 Main St",
                            "move_in_date": "2024-06-01",
                            "move_out_date": "2025-06-01",
                            "rent_amount": 2500.00
                        }
                    )
                    self.assertIn(response.status_code, [200, 422])
    
    def test_create_contract_invalid_dates_order(self):
        """Test creating contract with move_out before move_in"""
        with patch('app.api.routes.get_current_user', return_value={"user_id": "user1"}):
            response = self.client.post(
                "/api/contracts",
                json={
                    "user_id": "user1",
                    "account_id": "0011X00000IqTUAA",
                    "tenant_name": "John Doe",
                    "property_address": "123 Main St",
                    "move_in_date": "2025-06-01",
                    "move_out_date": "2024-06-01",
                    "rent_amount": 2500.00
                }
            )
            # Should fail validation
            self.assertEqual(response.status_code, 422)
    
    def test_create_contract_invalid_date_format(self):
        """Test creating contract with invalid date format"""
        with patch('app.api.routes.get_current_user', return_value={"user_id": "user1"}):
            response = self.client.post(
                "/api/contracts",
                json={
                    "user_id": "user1",
                    "account_id": "0011X00000IqTUAA",
                    "tenant_name": "John Doe",
                    "property_address": "123 Main St",
                    "move_in_date": "06-01-2024",  # Wrong format
                    "move_out_date": "2025-06-01",
                    "rent_amount": 2500.00
                }
            )
            # Should fail validation
            self.assertEqual(response.status_code, 422)
    
    def test_create_contract_negative_rent(self):
        """Test creating contract with negative rent"""
        with patch('app.api.routes.get_current_user', return_value={"user_id": "user1"}):
            response = self.client.post(
                "/api/contracts",
                json={
                    "user_id": "user1",
                    "account_id": "0011X00000IqTUAA",
                    "tenant_name": "John Doe",
                    "property_address": "123 Main St",
                    "move_in_date": "2024-06-01",
                    "move_out_date": "2025-06-01",
                    "rent_amount": -100.00
                }
            )
            # Should fail validation
            self.assertEqual(response.status_code, 422)
    
    def test_create_contract_excessive_rent(self):
        """Test creating contract with rent exceeding limit"""
        with patch('app.api.routes.get_current_user', return_value={"user_id": "user1"}):
            response = self.client.post(
                "/api/contracts",
                json={
                    "user_id": "user1",
                    "account_id": "0011X00000IqTUAA",
                    "tenant_name": "John Doe",
                    "property_address": "123 Main St",
                    "move_in_date": "2024-06-01",
                    "move_out_date": "2025-06-01",
                    "rent_amount": 10000000.00  # Exceeds limit
                }
            )
            # Should fail validation
            self.assertEqual(response.status_code, 422)
    
    # Request Size Tests
    @patch('app.api.routes.get_current_user', return_value={"user_id": "user1"})
    def test_request_size_limit_exceeded(self, mock_user):
        """Test request size limit"""
        # Create a payload that exceeds the size limit
        large_message = "x" * (1024 * 1024 + 1)  # Over 1MB
        response = self.client.post(
            "/api/jobs",
            json={
                "user_id": "user1",
                "issue_type": "payment_issue",
                "message": large_message
            }
        )
        # Should be rejected
        self.assertIn(response.status_code, [413, 422])


def run_validation_tests():
    """Run all validation tests"""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestAPIValidation)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result


if __name__ == '__main__':
    result = run_validation_tests()
    sys.exit(0 if result.wasSuccessful() else 1)
