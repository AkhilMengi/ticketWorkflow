"""
LIVE EXECUTION DEMO
Shows how the system handles different request types
"""

import json
from datetime import datetime
from typing import Dict, Any


def demo_output(request_id: str, routing: str, execution: str, confidence: float, result: Dict[str, Any]):
    """Show what live execution output looks like"""
    
    print("\n" + "="*100)
    print(f"PROCESSING REQUEST #{request_id}".center(100))
    print("="*100 + "\n")
    
    print(f"[Step 3] ROUTING ANALYSIS")
    print(f"   Decision:     {routing.upper()}")
    print(f"   Confidence:   {confidence:.0%}")
    print()
    
    print(f"[Step 4] EXECUTION PATH")
    
    if routing == "billing":
        print(f"   ✓ Routed to:  BILLING SYSTEM")
        print(f"   Action:       {result.get('action', 'N/A')}")
        print(f"   Transaction:  {result.get('transaction_id', 'N/A')}")
        print(f"   Status:       {result.get('status', 'N/A')}")
        
    elif routing == "salesforce":
        print(f"   ✓ Routed to:  SALESFORCE")
        print(f"   Action:       {result.get('action', 'N/A')}")
        print(f"   Case ID:      {result.get('case_id', 'N/A')}")
        print(f"   Status:       {result.get('status', 'N/A')}")
        
    else:
        print(f"   ⚠️  Status:    MANUAL REVIEW REQUIRED")
        print(f"   Reason:       Low confidence or ambiguous request")
    
    print()
    
    print(f"[Step 5] RESPONSE TO CUSTOMER")
    print(f"   Status:   {result.get('status', 'unknown').upper()}")
    print(f"   Message:  {result.get('message', 'N/A')}")
    
    if result.get('case_id'):
        print(f"   Case ID:  {result['case_id']}")
    if result.get('transaction_id'):
        print(f"   Txn ID:   {result['transaction_id']}")
    
    print()
    
    print(f"[Step 6] EXECUTION TRAIL")
    for i, event in enumerate(result.get('events', []), 1):
        print(f"   {i}. {event}")
    print()


def main():
    print("\n")
    print("╔" + "="*98 + "╗")
    print("║" + "LIVE EXECUTION SYSTEM - DEMONSTRATION".center(98) + "║")
    print("║" + "Watch how each request type is handled".center(98) + "║")
    print("╚" + "="*98 + "╝" + "\n")
    
    # Demo 1: Clear Billing Issue
    print("\n" + "▼"*100)
    print("DEMO 1: BILLING ISSUE (High Confidence)".center(100))
    print("▼"*100 + "\n")
    
    print("REQUEST: 'I was charged $150 twice for my subscription'")
    print("Issue Type: billing_issue")
    print("Category: billing\n")
    
    demo_output(
        request_id="req_001",
        routing="billing",
        execution="billing",
        confidence=0.95,
        result={
            "action": "APPLY_CREDIT",
            "transaction_id": "TXN-2024-12-001",
            "status": "SUCCESS",
            "message": "Credit of $150 has been applied to your account",
            "events": [
                "ROUTING_DECISION → billing (95% confidence)",
                "BILLING_EXECUTION → apply_credit - SUCCESS",
                "AGGREGATION → success"
            ]
        }
    )
    
    # Demo 2: Clear SF Issue
    print("\n" + "▼"*100)
    print("DEMO 2: TECHNICAL ISSUE (High Confidence)".center(100))
    print("▼"*100 + "\n")
    
    print("REQUEST: 'I'm getting a 403 error when accessing the dashboard'")
    print("Issue Type: technical_support")
    print("Category: technical\n")
    
    demo_output(
        request_id="req_002",
        routing="salesforce",
        execution="salesforce",
        confidence=0.92,
        result={
            "action": "CREATE_CASE",
            "case_id": "00012345678ABC",
            "status": "SUCCESS",
            "message": "We've created a support case for your 403 error. Reference: 00012345678ABC",
            "events": [
                "ROUTING_DECISION → salesforce (92% confidence)",
                "SF_EXECUTION → create_case - SUCCESS",
                "AGGREGATION → success"
            ]
        }
    )
    
    # Demo 3: Invoice Question
    print("\n" + "▼"*100)
    print("DEMO 3: BILLING QUESTION (High Confidence)".center(100))
    print("▼"*100 + "\n")
    
    print("REQUEST: 'Why was I charged for 2 months when I only used the service for 1?'")
    print("Issue Type: billing_issue")
    print("Category: billing\n")
    
    demo_output(
        request_id="req_003",
        routing="billing",
        execution="billing",
        confidence=0.88,
        result={
            "action": "UPDATE_BILLING_ACCOUNT",
            "transaction_id": "TXN-2024-12-002",
            "status": "SUCCESS",
            "message": "We've reviewed your invoice and will send you a detailed explanation within 1 hour",
            "events": [
                "ROUTING_DECISION → billing (88% confidence)",
                "BILLING_EXECUTION → update_billing_account - SUCCESS",
                "AGGREGATION → success"
            ]
        }
    )
    
    # Demo 4: Ambiguous Issue
    print("\n" + "▼"*100)
    print("DEMO 4: AMBIGUOUS REQUEST (Low Confidence → Manual Review)".center(100))
    print("▼"*100 + "\n")
    
    print("REQUEST: 'I have a question about my account'")
    print("Issue Type: general")
    print("Category: (none)\n")
    
    print("═"*100)
    print("PROCESSING REQUEST #req_004".center(100))
    print("═"*100 + "\n")
    
    print(f"[Step 3] ROUTING ANALYSIS")
    print(f"   Decision:     UNCLEAR")
    print(f"   Confidence:   45%")
    print()
    
    print(f"[Step 4] EXECUTION PATH")
    print(f"   ⚠️  Status:    MANUAL REVIEW REQUIRED")
    print(f"   Reason:       Confidence too low (45% < 60% threshold)")
    print()
    
    print(f"[Step 5] RESPONSE TO CUSTOMER")
    print(f"   Status:   ESCALATED")
    print(f"   Message:  Your request has been escalated to our support team for personalized assistance")
    print()
    
    print(f"[Step 6] EXECUTION TRAIL")
    print(f"   1. ROUTING_DECISION → unclear (45% confidence)")
    print(f"   2. MANUAL_REVIEW_ESCALATION → human review required")
    print()
    
    # Demo 5: Feature Request
    print("\n" + "▼"*100)
    print("DEMO 5: FEATURE REQUEST (Routed to SF)".center(100))
    print("▼"*100 + "\n")
    
    print("REQUEST: 'Can you add PDF export for reports?'")
    print("Issue Type: feature_request")
    print("Category: feature_request\n")
    
    demo_output(
        request_id="req_005",
        routing="salesforce",
        execution="salesforce",
        confidence=0.87,
        result={
            "action": "CREATE_CASE",
            "case_id": "00012345678DEF",
            "status": "SUCCESS",
            "message": "Thank you for the feature request! We've logged it as case 00012345678DEF. Our team will review it.",
            "events": [
                "ROUTING_DECISION → salesforce (87% confidence)",
                "SF_EXECUTION → create_case - SUCCESS",
                "AGGREGATION → success"
            ]
        }
    )
    
    # Summary
    print("\n" + "="*100)
    print("EXECUTION SUMMARY".center(100))
    print("="*100 + "\n")
    
    print("5 REQUESTS PROCESSED:\n")
    
    print("✅ req_001 → BILLING    [95% confidence] TXN-2024-12-001")
    print("✅ req_002 → SALESFORCE [92% confidence] Case 00012345678ABC")
    print("✅ req_003 → BILLING    [88% confidence] TXN-2024-12-002")
    print("⚠️  req_004 → MANUAL    [45% confidence] Human review needed")
    print("✅ req_005 → SALESFORCE [87% confidence] Case 00012345678DEF")
    
    print("\n" + "-"*100)
    print("Routing Breakdown:")
    print("  • Salesforce: 2 cases (req_002, req_005)")
    print("  • Billing:    2 transactions (req_001, req_003)")
    print("  • Manual:     1 escalation (req_004)")
    print("\n" + "="*100 + "\n")
    
    # Save demo requests
    demo_requests = [
        {
            "id": "req_001",
            "user_id": "cust_001",
            "issue_type": "billing_issue",
            "message": "I was charged $150 twice for my subscription",
            "backend_context": {"amount": 150},
            "category": "billing"
        },
        {
            "id": "req_002",
            "user_id": "cust_002",
            "issue_type": "technical_support",
            "message": "I'm getting a 403 error when accessing the dashboard",
            "backend_context": {"error_code": 403},
            "category": "technical"
        },
        {
            "id": "req_003",
            "user_id": "cust_003",
            "issue_type": "billing_issue",
            "message": "Why was I charged for 2 months when I only used the service for 1?",
            "backend_context": {"months_used": 1, "months_charged": 2},
            "category": "billing"
        },
        {
            "id": "req_004",
            "user_id": "cust_004",
            "issue_type": "general",
            "message": "I have a question about my account",
            "backend_context": {},
            "category": None
        },
        {
            "id": "req_005",
            "user_id": "cust_005",
            "issue_type": "feature_request",
            "message": "Can you add PDF export for reports?",
            "backend_context": {},
            "category": "feature_request"
        }
    ]
    
    with open('demo_requests.json', 'w') as f:
        json.dump(demo_requests, f, indent=2)
    
    print("✅ Saved demo_requests.json (ready to test with live_executor.py)")
    print("\nNext Steps:")
    print("  1. Review these examples above")
    print("  2. Run: python live_executor.py")
    print("  3. Add your requests to requests.json")
    print("  4. Watch real-time execution!\n")


if __name__ == "__main__":
    main()
