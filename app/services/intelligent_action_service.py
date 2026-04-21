import json
import os
import time
import logging
from typing import List, Dict, Any
from openai import OpenAI
from app.config import settings

logger = logging.getLogger(__name__)
client = OpenAI(api_key=settings.OPENAI_API_KEY)

SEMANTIC_ACTION_SELECTION_PROMPT = """You are an intelligent support action router for a customer support system.

Your job:
1. Read the customer issue description
2. Review the suggested actions/recommendations provided (these are GENERIC suggestions, not specific system actions)
3. INTELLIGENTLY INFER what SYSTEM ACTIONS are needed based on the issue AND suggestions
4. SELECT 2-3 MOST RELEVANT ACTIONS when applicable (prioritized by relevance)
5. Return the inferred action types, reasoning, and confidence scores for EACH action

=== HOW TO MAP SUGGESTIONS TO SYSTEM ACTIONS ===

Suggestions you might see:
- "Check customer details" → May need: create_case (for investigation)
- "Rebill the account" → May need: apply_billing_adjustment (to credit/refund)
- "Close the case" → May infer: All actions completed
- "Reach out to team" → May need: escalate_to_team (human intervention)
- "Verify payment" → May need: apply_billing_adjustment + escalate_to_team
- "Investigate issue" → May need: create_case + escalate_to_team
- "Send customer update" → May need: send_notification + create_case

YOUR INTELLIGENCE:
- You decide WHICH suggestion requires WHICH action
- Not all suggestions require actions (some are informational)
- Some suggestions map to MULTIPLE actions
- Understand the CONTEXT and ISSUE TYPE to decide actions

Available System Actions You Can Choose From:
- create_case: Create a support case in Salesforce for tracking/investigation
- apply_billing_adjustment: Apply credits, refunds, rebill, or process reimbursements
- escalate_to_team: Escalate to human support team for manual review
- send_notification: Send customer notification about status update
- do_nothing: No immediate action needed

IMPORTANT RULES:
- You must INTELLIGENTLY map suggestions to system actions
- Not all suggestions map to actions (ignore if not actionable)
- Execute MULTIPLE complementary actions when needed
- Prioritize by relevance: primary (main fix), secondary (supporting), tertiary (optional)
- Must have CONFIDENCE > 0.6 to recommend an action

Analyze the issue and suggestions carefully, then INFER the best 2-3 system actions.

Return ONLY valid JSON in this format:
{{
  "issue_summary": "Brief summary of the customer issue",
  "suggestions_analyzed": ["suggestion_1", "suggestion_2", ...],
  "suggestion_mapping": {{
    "suggestion_1": "Mapped to create_case because...",
    "suggestion_2": "Mapped to apply_billing_adjustment because...",
    "suggestion_3": "Not applicable/informational only"
  }},
  "selected_actions": [
    {{
      "action_type": "create_case|apply_billing_adjustment|escalate_to_team|send_notification",
      "priority": "primary|secondary|tertiary",
      "reasoning": "Why this action addresses the issue based on suggestion(s)",
      "confidence": 0.0 to 1.0,
      "triggered_by_suggestion": "Which suggestion(s) triggered this action",
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
        
        # Log suggestion mapping (how generic suggestions were interpreted as system actions)
        suggestion_mapping = action_selection.get("suggestion_mapping", {})
        if suggestion_mapping:
            logger.info(f"[ACTION_SELECTION] Suggestion Mapping:")
            for suggestion, mapping in suggestion_mapping.items():
                logger.info(f"  - {suggestion}: {mapping}")
        
        # Log actions
        actions_count = len(action_selection.get("selected_actions", []))
        logger.info(f"[ACTION_SELECTION] Completed in {func_elapsed:.2f}s - Selected {actions_count} action(s) (overall confidence: {action_selection.get('overall_confidence', 0):.2f})")
        
        for idx, action in enumerate(action_selection.get("selected_actions", []), 1):
            triggered_by = action.get("triggered_by_suggestion", "unknown")
            logger.info(f"[ACTION_SELECTION] Action {idx}: {action.get('action_type')} (priority: {action.get('priority')}, confidence: {action.get('confidence', 0):.2f}, triggered by: {triggered_by})")
        
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



