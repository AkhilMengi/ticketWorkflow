import queue
import threading
import logging
import traceback
from app.agent.graph import agent_graph
from app.agent.contract_graph import contract_agent_graph
from app.agent.memory import save_long_term_memory
from app.services.job_service import update_job, add_event

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

job_queue = queue.Queue()
contract_queue = queue.Queue()

def enqueue_job(initial_state: dict):
    job_queue.put(initial_state)

def enqueue_contract_job(initial_state: dict):
    contract_queue.put(initial_state)

def worker_loop():
    while True:
        state = job_queue.get()
        job_id = state["job_id"]

        try:
            update_job(job_id, "processing")
            add_event(job_id, "job_started", {"job_id": job_id})

            result = agent_graph.invoke(state)

            for event in result.get("event_log", []):
                add_event(job_id, event["type"], event)

            update_job(job_id, "completed", result)

            save_long_term_memory(
                user_id=state["user_id"],
                memory_type="support_issue",
                payload={
                    "issue_type": state["issue_type"],
                    "summary": result.get("summary"),
                    "category": result.get("category"),
                    "priority": result.get("priority"),
                    "case_id": result.get("case_id")
                }
            )

            add_event(job_id, "job_completed", {"job_id": job_id, "case_id": result.get("case_id")})
            logger.info(f"Job {job_id} completed successfully")

        except Exception as e:
            error_details = traceback.format_exc()
            logger.error(f"Job {job_id} failed with error: {str(e)}\n{error_details}")
            update_job(job_id, "failed", {"error": str(e), "traceback": error_details})
            add_event(job_id, "job_failed", {"error": str(e), "traceback": error_details})

        finally:
            job_queue.task_done()


def contract_worker_loop():
    """Worker loop for contract creation jobs"""
    while True:
        state = contract_queue.get()
        job_id = state["job_id"]

        try:
            update_job(job_id, "processing")
            add_event(job_id, "contract_job_started", {"job_id": job_id})

            # Execute contract workflow
            result = contract_agent_graph.invoke(state)

            # Ensure result is a dict
            if result is None:
                result = state

            # Log all events
            for event in result.get("event_log", []):
                add_event(job_id, event["type"], event)

            update_job(job_id, "completed", result)

            # Save memory of contract creation
            final_answer = result.get("final_answer", {})
            if final_answer is None:
                final_answer = {}
            
            save_long_term_memory(
                user_id=state["user_id"],
                memory_type="contract_creation",
                payload={
                    "tenant_name": state["tenant_name"],
                    "property_address": state["property_address"],
                    "move_in_date": state["move_in_date"],
                    "move_out_date": state["move_out_date"],
                    "rent_amount": state["rent_amount"],
                    "contract_id": result.get("contract_id"),
                    "status": final_answer.get("status") if isinstance(final_answer, dict) else "unknown"
                }
            )

            add_event(job_id, "contract_job_completed", {
                "job_id": job_id,
                "contract_id": result.get("contract_id"),
                "status": final_answer.get("status") if isinstance(final_answer, dict) else "unknown"
            })
            logger.info(f"Contract job {job_id} completed successfully")

        except Exception as e:
            error_details = traceback.format_exc()
            logger.error(f"Contract job {job_id} failed with error: {str(e)}\n{error_details}")
            update_job(job_id, "failed", {"error": str(e), "traceback": error_details})
            add_event(job_id, "contract_job_failed", {"error": str(e), "traceback": error_details})

        finally:
            contract_queue.task_done()


def start_worker():
    thread = threading.Thread(target=worker_loop, daemon=True)
    thread.start()
    
    contract_thread = threading.Thread(target=contract_worker_loop, daemon=True)
    contract_thread.start()