# Agentic Issue Resolution System — Complete Documentation

## 📖 Documentation Library

Welcome! This project has comprehensive documentation to help you understand the system architecture and workflows. Here's how to navigate:

### 🎯 **Start Here**
- **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** — Best for: Quick answers, 5-minute overview
  - System overview
  - Key concepts
  - API endpoints
  - Running locally
  - Common questions

### 🏗️ **Architecture & Design**
- **[HLD.md](HLD.md)** — Best for: Understanding the complete system design
  - System architecture diagram
  - Component details
  - Data flow & workflow
  - Design patterns
  - Scalability considerations
  - Tech stack

### 🔄 **Workflows & Processes**
- **[WORKFLOW_DIAGRAM.md](WORKFLOW_DIAGRAM.md)** — Best for: Understanding how things work step-by-step
  - Request flow (client → response)
  - LangGraph state machine
  - Conditional routing logic
  - Detailed node operations
  - State evolution
  - Error handling
  - Execution timeline
  - Integration points

### 📊 **Visual Diagrams**
- **[ARCHITECTURE_DIAGRAMS.md](ARCHITECTURE_DIAGRAMS.md)** — Best for: Visual learners
  - Mermaid system architecture diagram
  - LangGraph workflow diagram
  - Confidence scoring diagram
  - API endpoints diagram
  - Execution sequence diagram
  - Database schema
  - Component dependencies

### 🔗 **Component Interactions**
- **[COMPONENT_INTERACTIONS.md](COMPONENT_INTERACTIONS.md)** — Best for: Understanding data flow between components
  - HTTP request → API → Agent execution
  - Agent graph execution sequence
  - Service integration details (SF, Billing, LLM)
  - State mutations through workflow
  - Tracing & metrics collection
  - Configuration flow
  - Error propagation

---

## 🚀 Quick Navigation by Use Case

### "I need to understand the system in 15 minutes"
1. Read: [System Overview](QUICK_REFERENCE.md#-quick-system-overview)
2. Read: [Architecture in One Picture](QUICK_REFERENCE.md#-system-architecture-in-one-picture)
3. Look at: [Workflow Diagram](ARCHITECTURE_DIAGRAMS.md#2-langgraph-agent-workflow) (Mermaid)
4. Done! ✅

### "I need to run the system locally"
1. Read: [Running the System](QUICK_REFERENCE.md#-running-the-system)
2. Read: [Configuration Guide](QUICK_REFERENCE.md#-configuration-configpy)
3. Follow: Try the example API call

### "I need to understand specific components"
**API Layer**: [HLD.md § 2.1](HLD.md#21-api-layer-appapi)
**Agent/LangGraph**: [HLD.md § 2.2](HLD.md#22-agent-layer-appagent)
**Services**: [HLD.md § 2.3](HLD.md#23-services-layer-appservices)
**Configuration**: [HLD.md § 2.4](HLD.md#24-configuration--entry-points)

### "I need to understand the workflow"
1. Read: [Core Workflow (Simplified)](QUICK_REFERENCE.md#-core-workflow-simplified)
2. Read: [Detailed Node Operations](WORKFLOW_DIAGRAM.md#43-execute_actions_node)
3. Look at: [Sequence Diagram](ARCHITECTURE_DIAGRAMS.md#10-execution-timeline)

### "I need to debug an issue"
1. Check: [Error Handling](QUICK_REFERENCE.md#-error-handling)
2. Review: [Error Handling Flow](WORKFLOW_DIAGRAM.md#6-error-handling-flow)
3. Read: [Error Propagation](COMPONENT_INTERACTIONS.md#7-error-handling--propagation)

### "I need to integrate with production systems"
1. Read: [Scalability & Production](HLD.md#5-scalability--production-considerations)
2. Read: [Integration Checklist](QUICK_REFERENCE.md#-integration-checklist)
3. Use: [Testing Strategy](QUICK_REFERENCE.md#-testing-strategy)

### "I need to understand data flow"
1. Read: [Data Flow & Workflow](HLD.md#3-data-flow--workflow)
2. Look at: [State Flow Diagram](WORKFLOW_DIAGRAM.md#5-state-flow-diagram)
3. Read: [Component Interactions](COMPONENT_INTERACTIONS.md#1-http-request--api-layer--agent-execution)

---

## 🗂️ Documentation Map

```
QUICK_REFERENCE.md
├── System Overview
├── Architecture (1 picture)
├── Project Structure
├── Key Technologies
├── Core Concepts
├── Running Locally
├── API Endpoints
├── Understanding 4 Nodes
├── Configuration
├── Testing Strategy
├── Observability
├── Error Handling
├── Key Patterns
├── LLM Prompt Engineering
├── Integration Checklist
├── Success Metrics
├── Future Enhancements
└── FAQ

HLD.md
├── Executive Summary
├── System Architecture (detailed)
├── Component Details
│   ├── API Layer
│   ├── Agent Layer
│   ├── Services Layer
│   └── Configuration
├── Data Flow & Workflow
├── Design Patterns
├── Scalability
├── API Specifications
├── Technology Stack
├── Deployment Instructions
└── Summary

WORKFLOW_DIAGRAM.md
├── High-Level Request Flow
├── LangGraph Agent State Machine
├── Conditional Routing Logic
├── Detailed Node Operations
├── State Flow Diagram
├── Error Handling Flow
├── API Request/Response Flow
├── Streaming Response Flow
├── Execution Timeline Example
├── Integration Points Summary
└── Summary

ARCHITECTURE_DIAGRAMS.md
├── System Architecture (Mermaid)
├── LangGraph Agent Workflow (Mermaid)
├── Confidence Scoring & Gating (Mermaid)
├── Conditional Router Logic (Mermaid)
├── Data Flow Through AgentState (Mermaid)
├── State Machine Transitions (Mermaid)
├── API Endpoints & Data Models (Mermaid)
├── External API Integration (Mermaid)
├── Error Handling Flow (Mermaid)
├── Execution Timeline (Sequence Diagram)
├── Database Schema (ER Diagram)
└── Component Dependency Graph (Mermaid)

COMPONENT_INTERACTIONS.md
├── HTTP → API → Agent Execution (detailed steps)
├── Agent Graph Execution Sequence (with state mutations)
├── Service Integration Details
│   ├── Salesforce Integration
│   └── Billing Integration
├── LLM Interaction
│   ├── Prompt Construction
│   └── Response Parsing
├── Observability (Tracing & Metrics)
├── Configuration & Environment
├── Error Handling & Propagation
└── Summary
```

---

## 🎓 Learning Paths

### Path 1: "I'm new to the project" (1-2 hours)
```
1. QUICK_REFERENCE.md (System Overview section)
2. ARCHITECTURE_DIAGRAMS.md (diagram 1 & 2)
3. QUICK_REFERENCE.md (Core Workflow section)
4. COMPONENT_INTERACTIONS.md (diagram 1 - Request Flow)
5. HLD.md (Component Details section)
```
**Outcome**: Understand overall system + key components + data flow

### Path 2: "I need to modify the code" (2-3 hours)
```
1. QUICK_REFERENCE.md (Project Structure)
2. HLD.md (Component Details - all sections)
3. QUICK_REFERENCE.md (Understanding 4 Nodes)
4. WORKFLOW_DIAGRAM.md (Detailed Node Operations)
5. COMPONENT_INTERACTIONS.md (all sections)
```
**Outcome**: Understand code structure + how to modify each part

### Path 3: "I need to debug an issue" (30 mins)
```
1. QUICK_REFERENCE.md (Error Handling)
2. WORKFLOW_DIAGRAM.md (Error Handling Flow)
3. ARCHITECTURE_DIAGRAMS.md (Error Handling diagram)
4. COMPONENT_INTERACTIONS.md (Error Propagation)
```
**Outcome**: Know where errors come from + how to fix them

### Path 4: "I need to deploy to production" (1 hour)
```
1. HLD.md (Scalability section)
2. QUICK_REFERENCE.md (Integration Checklist)
3. HLD.md (Deployment Instructions)
4. QUICK_REFERENCE.md (Testing Strategy)
```
**Outcome**: Ready to move from mock to production

### Path 5: "I'm new to agentic workflows" (3-4 hours)
```
1. QUICK_REFERENCE.md (Key Concepts section)
2. ARCHITECTURE_DIAGRAMS.md (Confidence Scoring diagram)
3. WORKFLOW_DIAGRAM.md (LLM Interaction section)
4. HLD.md (Design Patterns section)
5. COMPONENT_INTERACTIONS.md (LLM Interaction section)
```
**Outcome**: Understand how agents work + confidence gating + LLM integration

---

## 📌 Key Concepts Quick Links

| Concept | Quick Explanation | Full Details |
|---------|------------------|--------------|
| **AgentState** | Central shared state dict | [HLD § 2.2](HLD.md#22-agent-layer-appagent), [Quick Ref](QUICK_REFERENCE.md#1-agentstate-typeddict) |
| **Confidence Scoring** | 0-10 score to gate API execution | [Quick Ref § 2](QUICK_REFERENCE.md#2-confidence-scoring-0-10), [Diagrams](ARCHITECTURE_DIAGRAMS.md#3-confidence-scoring--gating) |
| **LangGraph** | State machine for workflows | [HLD § 2.2](HLD.md#22-agent-layer-appagent), [Workflow § 2](WORKFLOW_DIAGRAM.md#2-langgraph-agent-workflow) |
| **Conditional Routing** | Route based on state | [Workflow § 3](WORKFLOW_DIAGRAM.md#3-conditional-routing-logic), [Diagrams § 4](ARCHITECTURE_DIAGRAMS.md#4-conditional-router-logic) |
| **Mock Mode** | Skip real APIs, use mock | [Quick Ref](QUICK_REFERENCE.md#using-mock-mode-local-development), [Testing](QUICK_REFERENCE.md#-testing-strategy) |
| **Recommended Actions** | LLM decisions | [Quick Ref § 3](QUICK_REFERENCE.md#3-recommended-actions), [Prompt](QUICK_REFERENCE.md#-llm-prompt-engineering) |
| **Tracing** | Execution history | [Quick Ref § Observability](QUICK_REFERENCE.md#-observability--monitoring), [Interactions § 5](COMPONENT_INTERACTIONS.md#5-observability-tracing--metrics) |

---

## 🔧 File Reference

| File | Purpose | Key Sections |
|------|---------|--------------|
| `main.py` | FastAPI entry point | Health check, CORS, router inclusion |
| `app/api/routes.py` | REST endpoints | Issue resolution, traces, metrics |
| `app/api/schemas.py` | Pydantic models | Request/response validation |
| `app/agent/graph.py` | LangGraph state machine | Node registration, edges, routing |
| `app/agent/nodes.py` | Node functions | fetch, analyze, execute, summarize |
| `app/agent/state.py` | AgentState TypedDict | State structure definition |
| `app/agent/prompts.py` | LLM prompt template | System prompt with rules |
| `app/agent/tracing.py` | Trace collection | Recording, filtering, metrics |
| `app/services/salesforce.py` | SF API wrapper | OAuth, case creation |
| `app/services/billing.py` | Billing API wrapper | Task creation, storage |
| `app/config.py` | Configuration | Environment variable loading |
| `dashboard.py` | Streamlit dashboard | Visualization, metrics display |
| `requirements.txt` | Dependencies | All Python packages |

---

## 💡 Tips for Using This Documentation

1. **Use Ctrl+F to search** for specific terms across documents
2. **Start with Mermaid diagrams** if you prefer visual learning
3. **Read ASCII diagrams** in WORKFLOW_DIAGRAM.md for step-by-step understanding
4. **Check QUICK_REFERENCE.md first** for most questions
5. **Use learning paths** above based on your role/goal
6. **Cross-reference** — each doc links to others for deeper dives

---

## 🎯 Documentation Quality

All documentation includes:
- ✅ Clear structure and hierarchy
- ✅ Code examples and syntax highlighting
- ✅ Diagrams (both ASCII and Mermaid)
- ✅ Step-by-step workflows
- ✅ Error scenarios
- ✅ Configuration details
- ✅ Integration examples
- ✅ Cross-references

---

## 📞 Quick Reference by Question Type

### Architecture Questions
→ [HLD.md](HLD.md) § System Architecture

### "How do I...?" Questions  
→ [QUICK_REFERENCE.md](QUICK_REFERENCE.md) § Running the System

### "What is...?" Questions
→ [QUICK_REFERENCE.md](QUICK_REFERENCE.md) § Core Concepts

### Workflow Questions
→ [WORKFLOW_DIAGRAM.md](WORKFLOW_DIAGRAM.md)

### Visual/Diagram Questions
→ [ARCHITECTURE_DIAGRAMS.md](ARCHITECTURE_DIAGRAMS.md)

### Component Interaction Questions
→ [COMPONENT_INTERACTIONS.md](COMPONENT_INTERACTIONS.md)

---

## 🚀 Getting Started Checklist

- [ ] Read [QUICK_REFERENCE.md § Quick System Overview](QUICK_REFERENCE.md#-quick-system-overview)
- [ ] Look at [System Architecture (1 picture)](QUICK_REFERENCE.md#-system-architecture-in-one-picture)
- [ ] Read [Core Workflow (Simplified)](QUICK_REFERENCE.md#-core-workflow-simplified)
- [ ] View [LangGraph Workflow Diagram](ARCHITECTURE_DIAGRAMS.md#2-langgraph-agent-workflow)
- [ ] Follow [Running the System](QUICK_REFERENCE.md#-running-the-system)
- [ ] Try an example API call
- [ ] View dashboard at localhost:8501
- [ ] Explore [Swagger UI](http://localhost:8000/docs)
- [ ] Read deeper docs as needed

---

## 📊 Documentation Statistics

| Document | Lines | Sections | Diagrams | Code |
|----------|-------|----------|----------|------|
| HLD.md | 550+ | 9 | 1 ASCII | 5 |
| WORKFLOW_DIAGRAM.md | 800+ | 11 | 20+ ASCII | 10 |
| ARCHITECTURE_DIAGRAMS.md | 500+ | 13 | 13 Mermaid | 0 |
| QUICK_REFERENCE.md | 700+ | 18 | 2 ASCII | 20 |
| COMPONENT_INTERACTIONS.md | 900+ | 7 | 15+ ASCII | 30 |
| **TOTAL** | **3450+** | **58** | **~50** | **65** |

---

## ✨ What You'll Understand After Reading

After going through the appropriate documentation, you'll understand:

- ✅ **Architecture**: How all components connect
- ✅ **Workflows**: Exact steps from request to response
- ✅ **Data Flow**: How state evolves through execution
- ✅ **Decision Making**: Confidence-based gating mechanism
- ✅ **Integration**: How external APIs are called
- ✅ **Observability**: How to monitor & debug
- ✅ **Configuration**: How to customize behavior
- ✅ **Deployment**: How to move to production
- ✅ **Troubleshooting**: How to find & fix issues
- ✅ **Extension**: How to add new features

---

## 💬 Common Entry Points

**"Hi, I'm a new developer"** → Start with [QUICK_REFERENCE.md](QUICK_REFERENCE.md)

**"I need to debug something"** → Go to [WORKFLOW_DIAGRAM.md](WORKFLOW_DIAGRAM.md) § Error Handling

**"I want to understand the architecture"** → Read [HLD.md](HLD.md) + view [ARCHITECTURE_DIAGRAMS.md](ARCHITECTURE_DIAGRAMS.md)

**"How does the LLM work here?"** → Read [COMPONENT_INTERACTIONS.md](COMPONENT_INTERACTIONS.md) § LLM Interaction

**"I need to deploy to production"** → See [HLD.md](HLD.md) § Scalability & [QUICK_REFERENCE.md](QUICK_REFERENCE.md) § Integration Checklist

---

## 📅 Documentation Last Updated

- **HLD.md**: May 11, 2026
- **WORKFLOW_DIAGRAM.md**: May 11, 2026
- **ARCHITECTURE_DIAGRAMS.md**: May 11, 2026
- **QUICK_REFERENCE.md**: May 11, 2026
- **COMPONENT_INTERACTIONS.md**: May 11, 2026

---

**Happy learning! 🚀**

Choose your path above and dive into the documentation that matches your needs. All documents are interlinked for easy navigation.
