"""
Agentic Issue Resolution — FastAPI entry point

Architecture
────────────
  API layer  (FastAPI + Pydantic)
       │
  Agent layer (LangGraph StateGraph)
       │
       ├── Node: fetch_account   → CRM / DB lookup
       ├── Node: analyze_issue   → LLM (GPT-4o-mini) via LangChain
       ├── Node: execute_actions → Salesforce REST API + Billing API
       └── Node: summarize       → compile final response

Run
───
  uvicorn main:app --reload --port 8000

Then open http://localhost:8000/docs for the interactive Swagger UI.
"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(
    title="Agentic Issue Resolution",
    description=(
        "LangGraph + LangChain powered agentic workflow that receives an account issue, "
        "uses an LLM to decide whether to create a Salesforce case, call the billing API, "
        "or both — then executes those actions automatically."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1", tags=["Issue Resolution"])


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "service": "agentic-issue-resolution", "version": "1.0.0"}
