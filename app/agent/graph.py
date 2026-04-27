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
    │
    ▼ (conditional edge)
    ├─ actions needed  ──► execute_actions  ← runs SF case + billing API
    │                           │
    │                           ▼
    └─ no actions  ─────────► summarize     ← builds final response
                                │
                                ▼
                              END

Why conditional routing?
  • If the LLM decides no action is needed (e.g. the issue is already resolved
    or just informational) we skip straight to summarize, avoiding unnecessary
    API calls.
  • Otherwise, execute_actions handles any combination of SF case and/or
    billing API in a single pass.
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

    Returns:
      "execute_actions" – one or more actions are queued
      "summarize"       – nothing to execute (no-op or already resolved)
    """
    if state.get("recommended_actions"):
        return "execute_actions"
    logger.info(
        "No actions recommended for account %s — routing to summarize.",
        state.get("account_id"),
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
