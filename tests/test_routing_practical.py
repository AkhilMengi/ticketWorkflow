"""
PRACTICAL ROUTING TESTER
Test the routing system with real requests and see decisions in real-time.

Usage:
    python test_routing_practical.py

This will:
- Take your requests as input
- Route them to SF or Billing
- Show confidence scores
- Display what would happen
- Run ACTUAL adapters (no mocking)
"""

from app.agent.router import RoutingClassifier, RoutingSystem
from app.agent.adapters import SalesforceAdapter, BillingAdapter, ActionType
from app.integrations.salesforce import SalesforceClient
import json


def print_result(title, value, color="white"):
    """Print formatted result"""
    colors = {
        "green": "\033[92m",
        "red": "\033[91m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "white": "\033[0m"
    }
    reset = "\033[0m"
    color_code = colors.get(color, "")
    print(f"{color_code}{title}: {value}{reset}")


def visualize_confidence(confidence):
    """Show visual confidence bar"""
    bar_length = 20
    filled = int(confidence * bar_length)
    bar = "█" * filled + "░" * (bar_length - filled)
    return f"[{bar}] {confidence:.0%}"


def test_request(message, issue_type="general", show_details=True):
    """
    Test routing for a single request.
    
    Args:
        message: Customer message
        issue_type: Type of issue
        show_details: Show detailed analysis
    """
    print("\n" + "="*80)
    print(f"REQUEST: {message}")
    print(f"ISSUE TYPE: {issue_type}")
    print("="*80)
    
    classifier = RoutingClassifier()
    
    # Classify the request
    result = classifier.classify_request({
        "message": message,
        "issue_type": issue_type,
        "backend_context": {}
    })
    
    target = result["target_system"]
    confidence = result["confidence"]
    rationale = result["rationale"]
    
    # Show routing decision
    print("\n🔍 ROUTING DECISION:")
    print("-"*80)
    
    if target == RoutingSystem.BILLING:
        print_result("  System", "💰 BILLING", "green")
    elif target == RoutingSystem.SALESFORCE:
        print_result("  System", "🎫 SALESFORCE", "blue")
    else:
        print_result("  System", "❓ UNKNOWN", "yellow")
    
    print(f"  Confidence: {visualize_confidence(confidence)}")
    print(f"  Rationale:  {rationale}")
    
    # Show detailed metadata if requested
    if show_details:
        metadata = result.get("metadata", {})
        
        print("\n📊 ANALYSIS DETAILS:")
        print("-"*80)
        
        if metadata.get("classification_method"):
            print(f"  Method: {metadata['classification_method']}")
        
        if metadata.get("scores"):
            scores = metadata["scores"]
            print(f"  SF Score:      {visualize_confidence(scores.get('sf_score', 0))}")
            print(f"  Billing Score: {visualize_confidence(scores.get('billing_score', 0))}")
        
        if metadata.get("rules_triggered"):
            print(f"  Rules Found: {metadata['rules_triggered']}")
    
    # Show what action would be taken
    print("\n⚙️  ACTION TO TAKE:")
    print("-"*80)
    
    if target == RoutingSystem.BILLING:
        if "refund" in message.lower() or "duplicate" in message.lower():
            print("  Action:  APPLY_CREDIT")
            print("  Details: Credit will be applied to customer account")
        elif "invoice" in message.lower():
            print("  Action:  PROCESS_INVOICE")
            print("  Details: Invoice will be processed")
        else:
            print("  Action:  APPLY_CREDIT (default)")
            print("  Details: Credit/refund will be processed")
    
    elif target == RoutingSystem.SALESFORCE:
        print("  Action:  CREATE_CASE")
        print("  Details: Support case will be created and assigned to team")
    
    else:
        print("  Action:  MANUAL_REVIEW")
        print("  Details: Request will be escalated to human agent")
    
    print("\n" + "="*80)
    return result


def test_predefined_scenarios():
    """Test with predefined real-world scenarios"""
    print("\n╔" + "="*78 + "╗")
    print("║" + "TESTING PREDEFINED SCENARIOS".center(78) + "║")
    print("╚" + "="*78 + "╝")
    
    scenarios = [
        {
            "name": "Scenario 1: Duplicate Billing",
            "message": "I was charged $150 twice for my subscription this month!",
            "issue_type": "billing_issue",
            "expect": "BILLING"
        },
        {
            "name": "Scenario 2: Technical Error",
            "message": "I'm getting a 403 error whenever I try to log in to my dashboard",
            "issue_type": "technical_support",
            "expect": "SALESFORCE"
        },
        {
            "name": "Scenario 3: Refund Request",
            "message": "Can I get a refund? I'm not happy with the service.",
            "issue_type": "billing_issue",
            "expect": "BILLING"
        },
        {
            "name": "Scenario 4: Feature Request",
            "message": "Can you please add dark mode to the application?",
            "issue_type": "feature_request",
            "expect": "SALESFORCE"
        },
        {
            "name": "Scenario 5: Invoice Question",
            "message": "Can you resend my invoice from last month?",
            "issue_type": "billing_issue",
            "expect": "BILLING"
        },
    ]
    
    results = []
    for scenario in scenarios:
        print(f"\n\n{'='*80}")
        print(f"📌 {scenario['name']}")
        print(f"{'='*80}")
        
        result = test_request(
            scenario["message"],
            scenario["issue_type"],
            show_details=True
        )
        
        actual = result["target_system"].value.upper()
        expected = scenario["expect"]
        
        # Check if routing is correct
        if actual == expected:
            print(f"\n✅ ROUTING CORRECT: Expected {expected}, Got {actual}")
            results.append(True)
        else:
            print(f"\n❌ ROUTING INCORRECT: Expected {expected}, Got {actual}")
            results.append(False)
    
    # Summary
    print("\n\n" + "╔" + "="*78 + "╗")
    print("║" + "SCENARIO TEST SUMMARY".center(78) + "║")
    print("╚" + "="*78 + "╝")
    
    passed = sum(results)
    total = len(results)
    
    for i, (scenario, passed_test) in enumerate(zip(scenarios, results), 1):
        status = "✅ PASS" if passed_test else "❌ FAIL"
        print(f"\n  {status} - {scenario['name']}")
    
    print(f"\n  TOTAL: {passed}/{total} scenarios routed correctly")
    print("\n" + "="*80 + "\n")


def test_adapter_actions():
    """Show what actual adapters would do"""
    print("\n╔" + "="*78 + "╗")
    print("║" + "TESTING ADAPTER ACTIONS".center(78) + "║")
    print("╚" + "="*78 + "╝")
    
    print("\n🔹 BILLING ADAPTER - Apply Credit Action")
    print("-"*80)
    
    try:
        billing_adapter = BillingAdapter()
        
        # Simulate a credit action
        result = billing_adapter.execute_action(
            ActionType.APPLY_CREDIT,
            {
                "user_id": "user_123",
                "amount": 150.00,
                "reason": "Duplicate charge - refund"
            }
        )
        
        print(f"  Action:         Apply Credit")
        print(f"  Success:        {result['success']}")
        print(f"  Transaction ID: {result.get('result_id', 'N/A')}")
        print(f"  Status:         {result.get('status', 'N/A')}")
        print(f"  Amount:         $150.00")
        print(f"  Message:        Credit successfully applied to account")
        
    except Exception as e:
        print(f"  ❌ Error: {str(e)}")
    
    print("\n🔹 SALESFORCE ADAPTER - Create Case Action")
    print("-"*80)
    
    try:
        sf_client = SalesforceClient()
        sf_adapter = SalesforceAdapter(sf_client)
        
        # Check if SF client is authenticated
        if not sf_client.access_token:
            sf_client.login()
        
        print(f"  Action:      Create Case")
        print(f"  Subject:     'Customer: Getting 403 error on dashboard'")
        print(f"  Description: 'User reports 403 error when accessing dashboard'")
        print(f"  Priority:    High")
        print(f"  Status:      New")
        
        # Actually try to create a case (for demonstration)
        result = sf_adapter.execute_action(
            ActionType.CREATE_CASE,
            {
                "subject": "[TEST] Getting 403 error on dashboard",
                "description": "Test case from routing system verification",
                "user_id": "test_user_123",
                "priority": "High"
            }
        )
        
        if result["success"]:
            print(f"\n  ✅ Case Created Successfully!")
            print(f"  Case ID: {result.get('result_id', 'N/A')}")
        else:
            print(f"\n  ⚠️  Case creation result: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"  Note: {str(e)}")
        print(f"  (Adapter is ready, Salesforce connection needed to test)")


def interactive_test():
    """Interactive mode - test your own scenarios"""
    print("\n╔" + "="*78 + "╗")
    print("║" + "INTERACTIVE ROUTING TEST".center(78) + "║")
    print("╚" + "="*78 + "╝")
    
    print("\nEnter customer messages to see how they're routed.")
    print("Commands: 'exit' or 'quit' to stop, 'examples' for predefined scenarios")
    print()
    
    quick_examples = [
        "I was charged twice",
        "I'm getting an error",
        "I need a refund",
        "There's a bug in the dashboard",
        "Can I update my invoice?"
    ]
    
    while True:
        try:
            user_message = input("\n📝 Enter a request (or 'help'): ").strip()
            
            if user_message.lower() in ["exit", "quit"]:
                print("Goodbye!\n")
                break
            
            elif user_message.lower() == "help":
                print("\nAvailable commands:")
                print("  'examples'  - Show quick example scenarios")
                print("  'exit'      - Exit the tester")
                print("  Or type any customer message to test routing")
                
            elif user_message.lower() == "examples":
                print("\nQuick examples:")
                for i, example in enumerate(quick_examples, 1):
                    print(f"  {i}. {example}")
                
            elif user_message:
                test_request(user_message, show_details=True)
            
        except KeyboardInterrupt:
            print("\n\nExiting...\n")
            break


def main():
    """Main entry point"""
    print("\n")
    print("╔" + "="*78 + "╗")
    print("║" + " "*78 + "║")
    print("║" + "PRACTICAL ROUTING SYSTEM TESTER".center(78) + "║")
    print("║" + "Test how requests are routed to SF vs Billing".center(78) + "║")
    print("║" + " "*78 + "║")
    print("╚" + "="*78 + "╝")
    
    while True:
        print("\nWhat would you like to do?")
        print("  1. Test predefined scenarios (real-world examples)")
        print("  2. Test adapter actions (see what actually happens)")
        print("  3. Interactive mode (test your own requests)")
        print("  4. Quick test single request")
        print("  5. Exit")
        print()
        
        choice = input("Enter choice (1-5): ").strip()
        
        if choice == "1":
            test_predefined_scenarios()
        
        elif choice == "2":
            test_adapter_actions()
        
        elif choice == "3":
            interactive_test()
        
        elif choice == "4":
            message = input("\nEnter a customer request: ").strip()
            if message:
                test_request(message, show_details=True)
        
        elif choice == "5":
            print("\nGoodbye!\n")
            break
        
        else:
            print("Invalid choice. Please try again.")


if __name__ == "__main__":
    try:
        main()
    except ImportError as e:
        print(f"\n❌ Import Error: {e}")
        print("\nMake sure you're running from the project root:")
        print("  cd c:\\Users\\akhil\\Downloads\\ticketWorkflow")
        print("  python test_routing_practical.py")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
