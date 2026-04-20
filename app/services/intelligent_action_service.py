import json
import os
from typing import List, Dict, Any
from openai import OpenAI
from app.config import settings
from app.services.action_service import parse_actions_from_file

client = OpenAI(api_key=settings.OPENAI_API_KEY)

ISSUE_ANALYSIS_PROMPT = """You are an intelligent support agent that analyzes customer issues and recommends appropriate actions.

Given a customer issue, you will:
1. Analyze the issue to understand its severity and type
2. Review available actions
3. Recommend which actions should be taken

Available actions in the system:
- salesforce_case: Create a support ticket in Salesforce
- billing: Apply credits or process refunds
- human_in_loop: Escalate to human support team for manual review

For each action, provide:
- should_execute: true/false - whether this action should be taken
- reason: why or why not this action is needed
- priority: low/medium/high for actions that should be executed

Respond in JSON format:
{{
  "issue_analysis": "Brief analysis of the issue",
  "severity": "low/medium/high/critical",
  "actions": [
    {{
      "action_type": "salesforce_case",
      "should_execute": true/false,
      "reason": "explanation",
      "priority": "low/medium/high"
    }},
    ...
  ]
}}"""

def analyze_issue_and_recommend_actions(
    issue_description: str,
    user_id: str
) -> Dict[str, Any]:
    """
    Use AI to analyze the issue and recommend which actions to take
    Returns analysis and recommended actions
    """
    try:
        # Get available actions from file
        current_file = os.path.abspath(__file__)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
        file_path = os.path.join(project_root, "recommended_actions_sample.txt")
        
        all_actions = parse_actions_from_file(file_path)
        
        # Format available actions for the prompt
        actions_list = "\n".join([
            f"- {action['action_type']}: {action['description']}"
            for action in all_actions
        ])
        
        # Use LLM to analyze issue and recommend actions
        prompt = f"""
{ISSUE_ANALYSIS_PROMPT}

Customer Issue:
{issue_description}

Available Actions:
{actions_list}

Analyze this issue and recommend which actions should be taken for user {user_id}.
"""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a support AI that analyzes issues and recommends actions. Always respond with valid JSON."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
        )
        
        # Parse the response
        response_text = response.choices[0].message.content
        
        # Try to extract JSON from the response
        try:
            analysis = json.loads(response_text)
        except json.JSONDecodeError:
            # If response is not pure JSON, try to extract it
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                analysis = json.loads(json_match.group())
            else:
                analysis = {
                    "issue_analysis": response_text,
                    "severity": "medium",
                    "actions": []
                }
        
        return analysis
        
    except Exception as e:
        print(f"Error analyzing issue: {str(e)}")
        return {
            "issue_analysis": f"Error: {str(e)}",
            "severity": "unknown",
            "actions": []
        }


def execute_intelligent_recommended_actions(
    issue_description: str,
    user_id: str,
    job_id: str
) -> Dict[str, Any]:
    """
    Intelligent action execution:
    1. Analyze the issue using AI
    2. Recommend appropriate actions
    3. Execute only the recommended actions
    4. Return results
    """
    
    # Step 1: Analyze issue and get recommendations
    print(f"[AI Analysis] Analyzing issue for user {user_id}...")
    analysis = analyze_issue_and_recommend_actions(issue_description, user_id)
    
    print(f"[AI Analysis] Severity: {analysis.get('severity')}")
    print(f"[AI Analysis] Analysis: {analysis.get('issue_analysis')}")
    
    # Step 2: Filter actions based on AI recommendations
    recommended_actions = []
    
    get_all_actions_path = os.path.abspath(__file__)
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(get_all_actions_path)))
    file_path = os.path.join(project_root, "recommended_actions_sample.txt")
    all_actions = parse_actions_from_file(file_path)
    
    for ai_action_rec in analysis.get("actions", []):
        if ai_action_rec.get("should_execute"):
            action_type = ai_action_rec.get("action_type")
            
            # Find matching action from file
            matching_action = next(
                (act for act in all_actions if act["action_type"] == action_type),
                None
            )
            
            if matching_action:
                recommended_actions.append(matching_action)
                priority_val = ai_action_rec.get('priority', 'normal')
                print(f"[Action Queue] Selected: {action_type} - Priority: {priority_val}")
    
    # If no actions were selected, create a case anyway for visibility
    if not recommended_actions and analysis.get("severity") in ["high", "critical"]:
        print("[Action Queue] No specific actions, creating support case for visibility...")
        recommended_actions = [
            next(
                (act for act in all_actions if act["action_type"] == "salesforce_case"),
                None
            )
        ]
        recommended_actions = [a for a in recommended_actions if a is not None]
    
    # Step 3: Execute recommended actions
    print(f"[Execution] Executing {len(recommended_actions)} recommended actions...")
    
    context = {
        "user_id": user_id,
        "issue_description": issue_description,
        "ai_severity": analysis.get("severity"),
        "ai_analysis": analysis.get("issue_analysis"),
        "request_type": "intelligent_actions",
        "source": "ai_analysis"
    }
    
    execution_result = process_recommended_actions(
        user_id=user_id,
        job_id=job_id,
        actions=recommended_actions,
        context=context
    )
    
    # Enrich response with AI analysis
    execution_result["ai_analysis"] = analysis
    execution_result["recommended_action_count"] = len(recommended_actions)
    execution_result["issue_severity"] = analysis.get("severity")
    
    return execution_result
