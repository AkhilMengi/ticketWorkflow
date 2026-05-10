"""
LangGraph workflow — compiles the agentic graph.

Graph topology
──────────────
  START
    │
    ▼
  fetch_account          ← loads account details from CRM/DB
    │
    ▼
  analyze_issue          ← LLM reads issue + suggestions → decides actions
                            + rates confidence (0-10) in understanding
    │
    ▼ (conditional edge)
    ├─ can understand (confidence >= 5)
    │  ├─ actions needed  ──► execute_actions  ← runs SF case + billing API
    │  │                           │
    │  │                           ▼
    │  └─ no actions needed ──► summarize     ← builds final response
    │
    └─ cannot understand (confidence < 5)
       └─► summarize     ← responds "I am not able to understand the issue"
                │
                ▼
              END

Why confidence scoring?
  • Prevents agent from making wrong API calls on unclear issues
  • Forces clear decision-making: either understand the issue or admit it can't
  • No guessing - if confidence < 5, respond with "I am not able to understand"
"""
import logging
from functools import lru_cache

from langgraph.graph import StateGraph, START, END

from app.agent.state import AgentState
from app.agent.nodes import (
    fetch_account_node,
    analyze_issue_node,
    execute_actions_node,
    summarize_node,
)

logger = logging.getLogger(__name__)


# ── Routing function ──────────────────────────────────────────────────────────

def _route_after_analysis(state: AgentState) -> str:
    """
    Decide the next node after the LLM has analysed the issue.
    
    NEW: Uses confidence score to determine if we should execute actions.
    If confidence < 5, we route to summarize which will respond with
    "I am not able to understand the issue".

    Returns:
      "execute_actions" – one or more actions are queued and confidence >= 5
      "summarize"       – nothing to execute, or cannot understand the issue
    """
    confidence = state.get("confidence_score", 5)
    can_understand = state.get("can_understand_issue", True)
    account_id = state.get("account_id", "unknown")
    
    # Check confidence first
    if not can_understand:
        logger.warning(
            "Cannot understand issue for %s (confidence: %d/10) → summarizing with error message",
            account_id,
            confidence,
        )
        return "summarize"
    
    # If we can understand, check if actions are needed
    if state.get("recommended_actions"):
        logger.info(
            "Account %s: confidence %d/10 (can understand) → executing actions",
            account_id,
            confidence,
        )
        return "execute_actions"
    
    logger.info(
        "Account %s: confidence %d/10 (can understand) but no actions needed → summarizing",
        account_id,
        confidence,
    )
    return "summarize"


# ── Graph builder ─────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def build_agent_graph():
    """Build and compile the LangGraph StateGraph (cached singleton)."""
    graph = StateGraph(AgentState)

    # ── Register nodes ────────────────────────────────────────────────────────
    graph.add_node("fetch_account", fetch_account_node)
    graph.add_node("analyze_issue", analyze_issue_node)
    graph.add_node("execute_actions", execute_actions_node)
    graph.add_node("summarize", summarize_node)

    # ── Wire edges ────────────────────────────────────────────────────────────
    graph.add_edge(START, "fetch_account")
    graph.add_edge("fetch_account", "analyze_issue")

    # Conditional: does the LLM want to take action, or skip straight to summary?
    graph.add_conditional_edges(
        "analyze_issue",
        _route_after_analysis,
        {
            "execute_actions": "execute_actions",
            "summarize": "summarize",
        },
    )

    graph.add_edge("execute_actions", "summarize")
    graph.add_edge("summarize", END)

    compiled = graph.compile()
    logger.info("LangGraph agent compiled successfully.")
    return compiled


# Public handle used by API routes
agent_graph = build_agent_graph()
