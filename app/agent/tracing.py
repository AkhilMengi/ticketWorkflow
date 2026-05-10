"""
Agent execution tracing — records all steps for dashboard visualization.

Features:
  • Stores complete trace of each agent execution
  • Captures timing, decisions, and outcomes
  • Provides filtering and analytics
"""
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class AgentTrace:
    """In-memory trace storage (replace with database in production)."""
    
    traces: List[Dict[str, Any]] = []
    
    @classmethod
    def record_execution(
        cls,
        account_id: str,
        issue_description: str,
        confidence_score: int,
        issue_analysis: str,
        recommended_actions: List[str],
        actions_executed: List[str],
        final_summary: str,
        duration_seconds: float,
        sf_case_result: Optional[Dict[str, Any]] = None,
        billing_result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record complete agent execution trace."""
        
        trace = {
            "timestamp": datetime.utcnow().isoformat(),
            "account_id": account_id,
            "issue_description": issue_description[:100],  # truncate
            "confidence_score": confidence_score,
            "issue_analysis": issue_analysis[:200],
            "recommended_actions": recommended_actions,
            "actions_executed": actions_executed,
            "final_summary": final_summary[:300],
            "duration_seconds": round(duration_seconds, 2),
            "sf_case_result": sf_case_result,
            "billing_result": billing_result,
            "error": error,
            "status": "success" if not error else "failure",
        }
        
        cls.traces.append(trace)
        logger.info(f"Trace recorded for {account_id} (confidence: {confidence_score}/10)")
        
        return trace
    
    @classmethod
    def get_all_traces(cls, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all traces (latest first)."""
        return sorted(
            cls.traces,
            key=lambda x: x["timestamp"],
            reverse=True
        )[:limit]
    
    @classmethod
    def get_traces_by_account(cls, account_id: str) -> List[Dict[str, Any]]:
        """Get all traces for a specific account."""
        return [
            t for t in sorted(
                cls.traces,
                key=lambda x: x["timestamp"],
                reverse=True
            ) if t["account_id"] == account_id
        ]
    
    @classmethod
    def get_metrics(cls) -> Dict[str, Any]:
        """Calculate metrics from all traces."""
        if not cls.traces:
            return {
                "total_executions": 0,
                "avg_confidence": 0,
                "success_count": 0,
                "failure_count": 0,
                "success_rate": 0,
                "avg_duration": 0,
                "most_common_action": None,
            }
        
        success_traces = [t for t in cls.traces if t["status"] == "success"]
        
        # Calculate average confidence
        avg_confidence = (
            sum(t.get("confidence_score", 0) for t in cls.traces) 
            / len(cls.traces)
        ) if cls.traces else 0
        
        # Calculate average duration
        avg_duration = (
            sum(t.get("duration_seconds", 0) for t in cls.traces) 
            / len(cls.traces)
        ) if cls.traces else 0
        
        # Find most common action
        all_actions = []
        for t in cls.traces:
            all_actions.extend(t.get("recommended_actions", []))
        
        most_common = None
        if all_actions:
            most_common = max(set(all_actions), key=all_actions.count)
        
        return {
            "total_executions": len(cls.traces),
            "avg_confidence": round(avg_confidence, 2),
            "success_count": len(success_traces),
            "failure_count": len(cls.traces) - len(success_traces),
            "success_rate": round(
                (len(success_traces) / len(cls.traces) * 100), 1
            ) if cls.traces else 0,
            "avg_duration": round(avg_duration, 2),
            "most_common_action": most_common,
        }
    
    @classmethod
    def clear_traces(cls):
        """Clear all traces (for testing)."""
        cls.traces = []
        logger.warning("All traces cleared!")
