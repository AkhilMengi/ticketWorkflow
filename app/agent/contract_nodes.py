import json
import logging
from openai import OpenAI
from app.config import settings
from app.agent.contract_tools import (
    validate_and_prepare_contract,
    create_salesforce_contract,
    lookup_existing_contracts
)
from app.agent.contract_prompts import (
    CONTRACT_VALIDATION_PROMPT,
    CONTRACT_CREATION_PROMPT,
    CONTRACT_RESULT_PROMPT
)

logger = logging.getLogger(__name__)
client = OpenAI(api_key=settings.OPENAI_API_KEY)


def validation_node(state):
    """Validate contract data before creation"""
    logger.info(f"Validating contract for user {state['user_id']}")
    
    # Perform local validation first
    validation_result = validate_and_prepare_contract(state)
    
    if not validation_result["valid"]:
        logger.warning(f"Contract validation failed: {validation_result['errors']}")
        return {
            "validation_status": "failed",
            "validation_errors": validation_result["errors"],
            "next_action": "reject",
            "final_answer": {
                "status": "validation_failed",
                "errors": validation_result["errors"],
                "message": f"Contract validation failed: {', '.join(validation_result['errors'])}"
            },
            "event_log": state["event_log"] + [{
                "type": "validation",
                "status": "failed",
                "errors": validation_result["errors"]
            }]
        }
    
    # Local validation passed - trust it and proceed
    logger.info("Local contract validation passed - proceeding to preparation")
    return {
        "validation_status": "passed",
        "validation_errors": [],
        "next_action": "create",
        "event_log": state["event_log"] + [{
            "type": "validation",
            "status": "passed",
            "method": "local_validation",
            "data": {
                "tenant_name": state["tenant_name"],
                "property_address": state["property_address"],
                "move_in_date": state["move_in_date"],
                "move_out_date": state["move_out_date"],
                "rent_amount": state["rent_amount"]
            }
        }]
    }


def prepare_contract_node(state):
    """Prepare and confirm contract details before creation"""
    logger.info(f"Preparing contract for creation for user {state['user_id']}")
    
    prompt_context = CONTRACT_CREATION_PROMPT.format(
        tenant_name=state["tenant_name"],
        property_address=state["property_address"],
        move_in_date=state["move_in_date"],
        move_out_date=state["move_out_date"],
        rent_amount=state["rent_amount"],
        user_id=state["user_id"]
    )
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt_context},
                {"role": "user", "content": "Prepare this contract for creation"}
            ],
            response_format={"type": "json_object"}
        )
        
        parsed = json.loads(response.choices[0].message.content)
        
        return {
            "next_action": parsed.get("action", "create"),
            "event_log": state["event_log"] + [{
                "type": "preparation",
                "status": "prepared",
                "summary": parsed.get("summary", ""),
                "next_steps": parsed.get("next_steps", [])
            }]
        }
        
    except Exception as e:
        logger.error(f"Error during contract preparation: {e}")
        return {
            "next_action": "create",
            "event_log": state["event_log"] + [{
                "type": "preparation",
                "status": "prepared",
                "note": "Preparation completed without LLM review"
            }]
        }


def create_contract_node(state):
    """Create the contract in Salesforce"""
    logger.info(f"Creating contract in Salesforce for user {state['user_id']}")
    
    try:
        result = create_salesforce_contract(state)
        contract_id = result.get("id")
        
        logger.info(f"Contract created successfully: {contract_id}")
        
        return {
            "contract_id": contract_id,
            "final_answer": {
                "status": "success",
                "contract_id": contract_id,
                "tenant_name": state["tenant_name"],
                "property_address": state["property_address"],
                "move_in_date": state["move_in_date"],
                "move_out_date": state["move_out_date"],
                "rent_amount": state["rent_amount"],
                "message": f"Contract #{contract_id} created successfully"
            },
            "event_log": state["event_log"] + [{
                "type": "contract_creation",
                "status": "success",
                "contract_id": contract_id,
                "result": result
            }]
        }
        
    except Exception as e:
        logger.error(f"Failed to create contract: {e}")
        
        return {
            "contract_id": None,
            "final_answer": {
                "status": "failed",
                "error": str(e),
                "tenant_name": state["tenant_name"],
                "property_address": state["property_address"],
                "message": f"Failed to create contract: {str(e)}"
            },
            "event_log": state["event_log"] + [{
                "type": "contract_creation",
                "status": "failed",
                "error": str(e),
                "retries": state.get("retries", 0)
            }]
        }


def summarize_contract_result_node(state):
    """Summarize the contract creation result"""
    if state.get("contract_id"):
        logger.info(f"Summarizing successful contract creation: {state['contract_id']}")
        
        prompt_context = CONTRACT_RESULT_PROMPT.format(
            contract_id=state["contract_id"],
            tenant_name=state["tenant_name"],
            property_address=state["property_address"],
            move_in_date=state["move_in_date"],
            move_out_date=state["move_out_date"]
        )
        
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": prompt_context},
                    {"role": "user", "content": f"Summarize this contract creation result"}
                ],
                response_format={"type": "json_object"}
            )
            
            parsed = json.loads(response.choices[0].message.content)
            
            return {
                "final_answer": {
                    "status": "success",
                    "contract_id": state["contract_id"],
                    "summary": parsed.get("summary", ""),
                    "details": parsed.get("contract_details", ""),
                    "next_actions": parsed.get("next_actions", [])
                },
                "event_log": state["event_log"] + [{
                    "type": "summary",
                    "status": "completed",
                    "summary": parsed.get("summary", "")
                }]
            }
        except Exception as e:
            logger.error(f"Error summarizing contract result: {e}")
    
    # Return final answer as-is if already created or fallback on error
    return {
        "event_log": state["event_log"] + [{
            "type": "summary",
            "status": "completed"
        }]
    }
