import json
import os
import time
import logging
from typing import List, Dict, Any
from openai import OpenAI
from app.config import settings
from app.services.action_service import parse_actions_from_file

logger = logging.getLogger(__name__)
client = OpenAI(api_key=settings.OPENAI_API_KEY)

SEMANTIC_ACTION_SELECTION_PROMPT = """You are an intelligent support action router for a customer support system.

Your job:
1. Read the customer issue description
2. Review the suggested actions/recommendations provided
3. Based on the issue AND the suggestions, decide what SYSTEM ACTIONS to take
4. SELECT 2-3 MOST RELEVANT ACTIONS when applicable (prioritized by relevance)
5. Return the action types, reasoning, and confidence scores for EACH action

Available System Actions You Can Choose:
- create_case: Create a support case in Salesforce for tracking/investigation
- apply_billing_adjustment: Apply credits, refunds, or rebill customer account  
- escalate_to_team: Escalate to human support team for manual review
- send_notification: Send customer notification about status
- do_nothing: No immediate action needed

IMPORTANT RULES:
- Execute MULTIPLE actions when they are independent and complementary
- Example: For "double charged" → [apply_billing_adjustment, create_case]
- Example: For "complex billing issue" → [apply_billing_adjustment, escalate_to_team, create_case]
- ONLY use do_nothing if truly no action is needed
- Prioritize actions by relevance (primary, secondary, tertiary)

Analyze the issue and suggestions carefully, then decide the BEST 2-3 system actions.

Return ONLY valid JSON in this format:
{{
  "issue_summary": "Brief summary of the customer issue",
  "recommendations_reviewed": ["suggestion_1", "suggestion_2", ...],
  "selected_actions": [
    {{
      "action_type": "create_case|apply_billing_adjustment|escalate_to_team|send_notification",
      "priority": "primary|secondary|tertiary",
      "reasoning": "Why this action addresses the issue",
      "confidence": 0.0 to 1.0,
      "action_parameters": {{
        "priority": "Low|Medium|High|Critical",
        "reason": "Specific reason for the action",
        "notes": "Any additional notes"
      }}
    }}
  ],
  "overall_confidence": 0.0 to 1.0
}}"""

def analyze_issue_and_select_action(
    issue_description: str,
    user_id: str,
    suggestions: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Analyze issue + suggestions and have LLM decide what action to take.
    
    LLM reads:
    - Issue description
    - Suggested actions from file
    
    LLM chooses:
    - What system action to execute
    - Parameters for that action
    
    Returns: {
        "selected_action": "create_case",
        "issue_summary": "...",
        "reasoning": "...",
        "action_parameters": {...},
        "confidence": 0.92
    }
    """
    func_start_time = time.time()
    logger.info(f"[ACTION_SELECTION] Starting action selection for user {user_id}")
    
    try:
        # Format suggestions for LLM
        suggestions_text = ""
        if suggestions:
            for idx, suggestion in enumerate(suggestions, 1):
                title = suggestion.get("title", f"Suggestion {idx}")
                description = suggestion.get("description", "")
                suggestions_text += f"\n- {title}: {description}"
        else:
            suggestions_text = "\n- No suggestions available"
        
        # Build the prompt
        prompt = f"""{SEMANTIC_ACTION_SELECTION_PROMPT}

Customer Issue for User {user_id}:
{issue_description}

Suggested Actions From System:
{suggestions_text}

Now analyze the issue and suggestions, then decide what system action should be taken:
"""
        
        logger.info(f"[LLM] Calling GPT-4o-mini for action selection (suggestions: {len(suggestions or [])})")
        llm_start_time = time.time()
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a support action router. Based on the customer issue and suggested actions, decide what system action to take. Always respond with ONLY valid JSON."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
        )
        
        llm_elapsed = time.time() - llm_start_time
        logger.info(f"[LLM] Response received in {llm_elapsed:.2f}s")
        
        # Parse response
        response_text = response.choices[0].message.content
        
        try:
            action_selection = json.loads(response_text)
        except json.JSONDecodeError:
            # Try to extract JSON
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                action_selection = json.loads(json_match.group())
            else:
                # Fallback
                action_selection = {
                    "issue_summary": issue_description[:100],
                    "recommendations_reviewed": [],
                    "selected_actions": [
                        {
                            "action_type": "create_case",
                            "priority": "primary",
                            "reasoning": "Could not parse AI response, defaulting to case creation",
                            "confidence": 0.3,
                            "action_parameters": {"priority": "Medium", "reason": "Unknown"}
                        }
                    ],
                    "overall_confidence": 0.3
                }
        
        func_elapsed = time.time() - func_start_time
        
        # Handle backward compatibility: convert old format to new format
        if "selected_action" in action_selection and "selected_actions" not in action_selection:
            # Convert single action to multiple actions format
            old_action = action_selection.get("selected_action", "do_nothing")
            old_params = action_selection.get("action_parameters", {})
            old_confidence = action_selection.get("confidence", 0.5)
            
            action_selection["selected_actions"] = [
                {
                    "action_type": old_action,
                    "priority": "primary",
                    "reasoning": action_selection.get("reasoning", ""),
                    "confidence": old_confidence,
                    "action_parameters": old_params
                }
            ] if old_action != "do_nothing" else []
            action_selection["overall_confidence"] = old_confidence
        
        # Log actions
        actions_count = len(action_selection.get("selected_actions", []))
        logger.info(f"[ACTION_SELECTION] Completed in {func_elapsed:.2f}s - Selected {actions_count} action(s) (overall confidence: {action_selection.get('overall_confidence', 0):.2f})")
        
        for idx, action in enumerate(action_selection.get("selected_actions", []), 1):
            logger.info(f"[ACTION_SELECTION] Action {idx}: {action.get('action_type')} (priority: {action.get('priority')}, confidence: {action.get('confidence', 0):.2f})")
        
        return action_selection
        
    except Exception as e:
        func_elapsed = time.time() - func_start_time
        logger.error(f"[ACTION_SELECTION] Error after {func_elapsed:.2f}s: {str(e)}")
        return {
            "issue_summary": issue_description[:100],
            "recommendations_reviewed": [],
            "selected_actions": [
                {
                    "action_type": "create_case",
                    "priority": "primary",
                    "reasoning": f"Error during analysis: {str(e)}",
                    "confidence": 0.2,
                    "action_parameters": {"priority": "Medium", "reason": "Error occurred"}
                }
            ],
            "overall_confidence": 0.2
        }


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
    [DEPRECATED: Use analyze_issue_and_select_action instead for semantic understanding]
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
