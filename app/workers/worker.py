import queue
import threading
import logging
import traceback
import time
from typing import Dict, Any, Optional
from app.agent.graph import agent_graph
from app.agent.contract_graph import contract_agent_graph
from app.agent.memory import save_long_term_memory
from app.services.job_service import update_job, add_event

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

job_queue = queue.Queue()
contract_queue = queue.Queue()

# Thread synchronization primitives to prevent race conditions
_job_locks: Dict[str, threading.RLock] = {}
_lock_dict_lock = threading.RLock()
_processing_jobs: set = set()
_processing_lock = threading.RLock()

MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds

def _get_job_lock(job_id: str) -> threading.RLock:
    """Get or create a lock for a specific job to prevent concurrent processing."""
    with _lock_dict_lock:
        if job_id not in _job_locks:
            _job_locks[job_id] = threading.RLock()
        return _job_locks[job_id]

def _mark_job_processing(job_id: str) -> bool:
    """Mark a job as being processed. Returns False if already processing."""
    with _processing_lock:
        if job_id in _processing_jobs:
            return False
        _processing_jobs.add(job_id)
        return True

def _mark_job_done(job_id: str) -> None:
    """Mark a job as done processing."""
    with _processing_lock:
        _processing_jobs.discard(job_id)

def enqueue_job(initial_state: dict) -> bool:
    """Enqueue a job for processing. Returns False if state is invalid."""
    if not initial_state or "job_id" not in initial_state:
        logger.error("Cannot enqueue job: missing job_id in state")
        return False
    
    # Validate state contains required fields
    required_fields = ["job_id", "user_id", "issue_type"]
    for field in required_fields:
        if field not in initial_state:
            logger.error(f"Cannot enqueue job: missing required field '{field}'")
            return False
    
    job_queue.put(initial_state)
    return True

def enqueue_contract_job(initial_state: dict) -> bool:
    """Enqueue a contract job for processing. Returns False if state is invalid."""
    if not initial_state or "job_id" not in initial_state:
        logger.error("Cannot enqueue contract job: missing job_id in state")
        return False
    
    # Validate state contains required fields
    required_fields = ["job_id", "user_id", "tenant_name"]
    for field in required_fields:
        if field not in initial_state:
            logger.error(f"Cannot enqueue contract job: missing required field '{field}'")
            return False
    
    contract_queue.put(initial_state)
    return True

def worker_loop():
    """Main worker loop for processing support ticket jobs with race condition protection."""
    while True:
        state = job_queue.get()
        job_id = state.get("job_id")
        
        if not job_id:
            logger.error("Received job with missing job_id, skipping")
            job_queue.task_done()
            continue
        
        # Prevent duplicate processing of the same job
        if not _mark_job_processing(job_id):
            logger.warning(f"Job {job_id} is already being processed, re-queueing")
            job_queue.put(state)
            job_queue.task_done()
            continue
        
        job_lock = _get_job_lock(job_id)
        
        try:
            with job_lock:
                # Validate state before processing
                if not all(k in state for k in ["job_id", "user_id", "issue_type"]):
                    raise ValueError("Job state missing required fields")
                
                update_job(job_id, "processing")
                add_event(job_id, "job_started", {"job_id": job_id})

                # Execute with retry logic
                result = None
                last_error = None
                
                for attempt in range(MAX_RETRIES):
                    try:
                        result = agent_graph.invoke(state)
                        break
                    except Exception as e:
                        last_error = e
                        if attempt < MAX_RETRIES - 1:
                            logger.warning(f"Job {job_id} attempt {attempt + 1} failed: {str(e)}, retrying...")
                            time.sleep(RETRY_DELAY)
                        else:
                            raise
                
                if result is None:
                    result = state
                
                # Process events
                for event in result.get("event_log", []):
                    add_event(job_id, event.get("type", "unknown"), event)

                # Update job with result
                update_job(job_id, "completed", result)

                # Save memory with proper error handling
                try:
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
                except Exception as mem_error:
                    logger.error(f"Failed to save memory for job {job_id}: {str(mem_error)}")
                    # Don't fail the entire job due to memory save failure

                add_event(job_id, "job_completed", {
                    "job_id": job_id,
                    "case_id": result.get("case_id")
                })
                logger.info(f"Job {job_id} completed successfully")

        except Exception as e:
            error_details = traceback.format_exc()
            logger.error(f"Job {job_id} failed with error: {str(e)}\n{error_details}")
            
            # Record failure with atomic operation
            try:
                update_job(job_id, "failed", {
                    "error": str(e),
                    "traceback": error_details,
                    "attempts": MAX_RETRIES
                })
                add_event(job_id, "job_failed", {
                    "error": str(e),
                    "traceback": error_details
                })
            except Exception as update_error:
                logger.error(f"Failed to update job {job_id} status to failed: {str(update_error)}")

        finally:
            _mark_job_done(job_id)
            job_queue.task_done()



def contract_worker_loop():
    """Worker loop for contract creation jobs with race condition protection."""
    while True:
        state = contract_queue.get()
        job_id = state.get("job_id")
        
        if not job_id:
            logger.error("Received contract job with missing job_id, skipping")
            contract_queue.task_done()
            continue
        
        # Prevent duplicate processing of the same job
        if not _mark_job_processing(job_id):
            logger.warning(f"Contract job {job_id} is already being processed, re-queueing")
            contract_queue.put(state)
            contract_queue.task_done()
            continue
        
        job_lock = _get_job_lock(job_id)
        
        try:
            with job_lock:
                # Validate state before processing
                required_fields = ["job_id", "user_id", "tenant_name"]
                if not all(k in state for k in required_fields):
                    raise ValueError(f"Contract job state missing required fields: {required_fields}")
                
                update_job(job_id, "processing")
                add_event(job_id, "contract_job_started", {"job_id": job_id})

                # Execute with retry logic
                result = None
                last_error = None
                
                for attempt in range(MAX_RETRIES):
                    try:
                        result = contract_agent_graph.invoke(state)
                        break
                    except Exception as e:
                        last_error = e
                        if attempt < MAX_RETRIES - 1:
                            logger.warning(f"Contract job {job_id} attempt {attempt + 1} failed: {str(e)}, retrying...")
                            time.sleep(RETRY_DELAY)
                        else:
                            raise

                # Ensure result is a dict
                if result is None:
                    result = state

                # Log all events
                for event in result.get("event_log", []):
                    add_event(job_id, event.get("type", "unknown"), event)

                # Update job with result
                update_job(job_id, "completed", result)

                # Save memory of contract creation with error handling
                try:
                    final_answer = result.get("final_answer", {})
                    if final_answer is None:
                        final_answer = {}
                    
                    save_long_term_memory(
                        user_id=state["user_id"],
                        memory_type="contract_creation",
                        payload={
                            "tenant_name": state.get("tenant_name"),
                            "property_address": state.get("property_address"),
                            "move_in_date": state.get("move_in_date"),
                            "move_out_date": state.get("move_out_date"),
                            "rent_amount": state.get("rent_amount"),
                            "contract_id": result.get("contract_id"),
                            "status": final_answer.get("status") if isinstance(final_answer, dict) else "unknown"
                        }
                    )
                except Exception as mem_error:
                    logger.error(f"Failed to save memory for contract job {job_id}: {str(mem_error)}")
                    # Don't fail the entire job due to memory save failure

                add_event(job_id, "contract_job_completed", {
                    "job_id": job_id,
                    "contract_id": result.get("contract_id"),
                    "status": final_answer.get("status") if isinstance(final_answer, dict) else "unknown"
                })
                logger.info(f"Contract job {job_id} completed successfully")

        except Exception as e:
            error_details = traceback.format_exc()
            logger.error(f"Contract job {job_id} failed with error: {str(e)}\n{error_details}")
            
            # Record failure with atomic operation
            try:
                update_job(job_id, "failed", {
                    "error": str(e),
                    "traceback": error_details,
                    "attempts": MAX_RETRIES
                })
                add_event(job_id, "contract_job_failed", {
                    "error": str(e),
                    "traceback": error_details
                })
            except Exception as update_error:
                logger.error(f"Failed to update contract job {job_id} status to failed: {str(update_error)}")

        finally:
            _mark_job_done(job_id)
            contract_queue.task_done()



def start_worker():
    thread = threading.Thread(target=worker_loop, daemon=True)
    thread.start()
    
    contract_thread = threading.Thread(target=contract_worker_loop, daemon=True)
    contract_thread.start()