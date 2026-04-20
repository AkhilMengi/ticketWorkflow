"""
LIVE EXECUTION PROCESSOR
Read requests from file and execute through routing system in real-time.

Usage:
    1. Edit requests.json (add your test requests)
    2. Run: python live_executor.py
    3. Watch real-time execution with actual SF case creation / Billing responses
"""

import json
import os
from datetime import datetime
from app.agent.routing_graph import routing_graph
from app.agent.routing_state import create_enhanced_state


def print_header(text, char="="):
    """Print formatted header"""
    width = 100
    print(f"\n{char * width}")
    print(f"{text.center(width)}")
    print(f"{char * width}\n")


def print_step(step_num, title, content=""):
    """Print a step in the process"""
    print(f"[Step {step_num}] {title}")
    if content:
        print(f"              {content}")
    print()


def print_result(system, success, details):
    """Print execution result"""
    if success:
        print(f"✅ SUCCESS")
        print(f"   System: {system.upper()}")
        for key, value in details.items():
            if value:
                print(f"   {key}: {value}")
    else:
        print(f"❌ FAILED")
        print(f"   Error: {details.get('error', 'Unknown error')}")
    print()


def execute_single_request(request_data):
    """Execute a single request through the entire routing graph"""
    
    print_header(f"PROCESSING REQUEST #{request_data.get('id', '?')}")
    
    # Step 1: Show input
    print_step(1, "INPUT REQUEST")
    print(f"   Customer ID:  {request_data.get('user_id', 'N/A')}")
    print(f"   Message:      {request_data.get('message', 'N/A')}")
    print(f"   Issue Type:   {request_data.get('issue_type', 'N/A')}")
    print()
    
    try:
        # Step 2: Create enhanced state
        print_step(2, "PREPARING STATE")
        
        state = {
            "job_id": request_data.get('id', f"job_{datetime.now().timestamp()}"),
            "user_id": request_data.get('user_id', 'unknown'),
            "issue_type": request_data.get('issue_type', 'general'),
            "message": request_data.get('message', ''),
            "backend_context": request_data.get('backend_context', {}),
            "customer_profile": None,
            "logs": [],
            "summary": None,
            "category": request_data.get('category', None),
            "priority": None,
            "next_action": None,
            "final_answer": None,
            "case_id": None,
            "retries": 0,
            "event_log": []
        }
        
        enhanced_state = create_enhanced_state(state)
        print(f"   State created with job_id: {enhanced_state['job_id']}")
        print()
        
        # Step 3: Execute through routing graph
        print_step(3, "ROUTING ANALYSIS")
        result = routing_graph.invoke(enhanced_state)
        
        # Show routing decision
        target_system = result.get('target_system', 'unknown')
        routing_confidence = result.get('routing_confidence', 0)
        routing_rationale = result.get('routing_rationale', '')
        
        print(f"   Decision:     {target_system.upper()}")
        print(f"   Confidence:   {routing_confidence:.0%}")
        print(f"   Rationale:    {routing_rationale}")
        print()
        
        # Step 4: Show execution system
        print_step(4, "EXECUTION PATH")
        execution_system = result.get('execution_system')
        
        if execution_system == 'salesforce':
            print(f"   ✓ Routed to:  SALESFORCE")
            print(f"   Action:       CREATE_CASE")
            print(f"   Case ID:      {result.get('sf_case_id', 'N/A')}")
            print(f"   Status:       {result.get('sf_status', 'N/A')}")
            
        elif execution_system == 'billing':
            print(f"   ✓ Routed to:  BILLING SYSTEM")
            print(f"   Action:       {result.get('billing_action_taken', 'N/A').upper()}")
            print(f"   Transaction:  {result.get('billing_transaction_id', 'N/A')}")
            print(f"   Status:       {result.get('billing_status', 'N/A')}")
            
        else:
            print(f"   ⚠️  Status:    MANUAL REVIEW REQUIRED")
            print(f"   Reason:       Low confidence or escalation triggered")
        
        print()
        
        # Step 5: Show final response
        print_step(5, "RESPONSE TO CUSTOMER")
        aggregated_response = result.get('aggregated_response', {})
        
        if aggregated_response:
            print(f"   Status:   {aggregated_response.get('status', 'unknown').upper()}")
            print(f"   System:   {aggregated_response.get('system', 'N/A')}")
            print(f"   Message:  {aggregated_response.get('message', 'N/A')}")
            
            if aggregated_response.get('case_id'):
                print(f"   Case ID:  {aggregated_response['case_id']}")
            if aggregated_response.get('transaction_id'):
                print(f"   Txn ID:   {aggregated_response['transaction_id']}")
        print()
        
        # Step 6: Show event trail
        print_step(6, "EXECUTION TRAIL")
        event_log = result.get('event_log', [])
        
        for i, event in enumerate(event_log, 1):
            event_type = event.get('type', 'unknown')
            print(f"   {i}. {event_type.upper()}", end="")
            
            if event_type == 'routing_decision':
                print(f" → {event.get('target_system', '?')}")
            elif event_type == 'sf_execution':
                print(f" → {event.get('action', '?')} - {event.get('status', '?')}")
            elif event_type == 'billing_execution':
                print(f" → {event.get('action', '?')} - {event.get('status', '?')}")
            elif event_type == 'aggregation':
                print(f" → {event.get('aggregated_status', '?')}")
            else:
                print()
        print()
        
        # Summary
        print_header("EXECUTION SUMMARY", "=")
        
        print("✅ REQUEST PROCESSED SUCCESSFULLY\n")
        
        print("Summary:")
        print(f"  • Routing:     {target_system.upper()} ({routing_confidence:.0%} confidence)")
        print(f"  • System:      {execution_system.upper() if execution_system else 'MANUAL_REVIEW'}")
        print(f"  • Final Status: {result.get('aggregated_status', 'unknown').upper()}")
        
        if execution_system == 'salesforce' and result.get('sf_case_id'):
            print(f"  • Case Created: {result['sf_case_id']}")
        elif execution_system == 'billing' and result.get('billing_transaction_id'):
            print(f"  • Transaction: {result['billing_transaction_id']}")
        elif not execution_system:
            print(f"  • Status: ESCALATED FOR MANUAL REVIEW")
        
        print()
        
        return {
            "id": request_data.get('id'),
            "success": True,
            "routing": target_system,
            "execution": execution_system,
            "result": result.get('aggregated_response', {}),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}\n")
        import traceback
        traceback.print_exc()
        
        return {
            "id": request_data.get('id'),
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


def load_requests():
    """Load requests from requests.json in parent directory"""
    requests_file = os.path.join('..', 'requests.json')
    
    if not os.path.exists(requests_file):
        print("\n❌ requests.json not found in parent directory!")
        print("\nCreate it with sample requests:")
        
        sample = [
            {
                "id": "req_1",
                "user_id": "customer_001",
                "issue_type": "billing_issue",
                "message": "I was charged $150 twice for my subscription",
                "backend_context": {"amount": 150},
                "category": "billing"
            },
            {
                "id": "req_2",
                "user_id": "customer_002",
                "issue_type": "technical_support",
                "message": "I'm getting a 403 error when trying to access the dashboard",
                "backend_context": {},
                "category": "technical"
            },
            {
                "id": "req_3",
                "user_id": "customer_003",
                "issue_type": "general",
                "message": "I have some concerns about my account",
                "backend_context": {},
                "category": None
            }
        ]
        
        with open(requests_file, 'w') as f:
            json.dump(sample, f, indent=2)
        
        print(f"\nCreated {requests_file} with 3 sample requests.")
        print("Edit it and run again!")
        return None
    
    with open(requests_file, 'r') as f:
        requests = json.load(f)
    
    return requests


def save_results(results):
    """Save execution results"""
    output_file = f"execution_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    return output_file


def main():
    """Main execution"""
    print_header("LIVE ROUTING SYSTEM EXECUTOR", "╔")
    
    # Load requests
    requests = load_requests()
    
    if not requests:
        return
    
    print(f"\nLoaded {len(requests)} requests from requests.json\n")
    
    # Process each request
    all_results = []
    
    for i, request in enumerate(requests, 1):
        result = execute_single_request(request)
        all_results.append(result)
        
        if i < len(requests):
            input("\nPress Enter to process next request...")
    
    # Save results
    output_file = save_results(all_results)
    
    # Final summary
    print_header("OVERALL SUMMARY")
    
    successful = sum(1 for r in all_results if r.get('success', False))
    failed = len(all_results) - successful
    
    print(f"Total Requests:  {len(all_results)}")
    print(f"Successful:      {successful}")
    print(f"Failed:          {failed}")
    print(f"\nResults saved to: {output_file}")
    
    # Breakdown by system
    sf_count = sum(1 for r in all_results if r.get('execution') == 'salesforce')
    billing_count = sum(1 for r in all_results if r.get('execution') == 'billing')
    manual_count = sum(1 for r in all_results if r.get('execution') is None)
    
    print(f"\nRouting Breakdown:")
    print(f"  Salesforce: {sf_count} cases")
    print(f"  Billing:    {billing_count} transactions")
    print(f"  Manual:     {manual_count} escalations")
    
    print("\n" + "="*100 + "\n")


if __name__ == "__main__":
    try:
        main()
    except ImportError as e:
        print(f"\n❌ Import Error: {e}")
        print("\nMake sure you're in the project directory:")
        print("  cd c:\\Users\\akhil\\Downloads\\ticketWorkflow")
        print("  python live_executor.py")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
