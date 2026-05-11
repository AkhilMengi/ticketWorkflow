# System Architecture & Workflow Diagrams (Mermaid)

## 1. System Architecture Diagram

```mermaid
graph TB
    subgraph Client["🖥️ Client Layer"]
        Browser["Web Browser<br/>(Swagger UI)"]
        Dashboard["📊 Dashboard<br/>(Streamlit)"]
    end

    subgraph API["🔌 API Layer<br/>(FastAPI)"]
        Routes["Routes & Schemas<br/>(Pydantic Validation)"]
        Health["Health Check"]
    end

    subgraph Agent["🧠 Agent Orchestration<br/>(LangGraph)"]
        Graph["StateGraph<br/>Graph Compilation"]
        Fetch["fetch_account_node<br/>(DB/CRM Lookup)"]
        Analyze["analyze_issue_node<br/>(LLM Analysis)"]
        Execute["execute_actions_node<br/>(SF + Billing APIs)"]
        Summarize["summarize_node<br/>(Response Compilation)"]
    end

    subgraph Services["⚙️ Services Layer"]
        SF["Salesforce Service<br/>(REST API + OAuth)"]
        Billing["Billing Service<br/>(Task Management)"]
        Config["Configuration<br/>(Environment Variables)"]
    end

    subgraph External["🌐 External Systems"]
        OpenAI["🤖 OpenAI API<br/>(GPT-4o-mini)"]
        SFAPI["🔷 Salesforce API<br/>(Case Creation)"]
        BillingAPI["💳 Billing API<br/>(Task Processing)"]
    end

    subgraph Observability["📈 Observability"]
        Traces["Agent Traces<br/>(Execution History)"]
        Metrics["Metrics<br/>(Success Rate, Confidence)"]
        Logging["Logging<br/>(Structured Logs)"]
    end

    Browser -->|POST /resolve-issue| Routes
    Dashboard -->|GET /traces, /metrics| Routes
    Routes -->|Initialize State| Graph
    Graph -->|Invoke| Fetch
    Fetch -->|State Update| Analyze
    Analyze -->|Route (confidence-based)| Execute
    Analyze -->|Route| Summarize
    Execute -->|Execute Actions| SF
    Execute -->|Execute Actions| Billing
    Execute -->|State Update| Summarize
    Summarize -->|Final Summary| Routes
    SF -->|OAuth + POST| SFAPI
    Billing -->|HTTP POST| BillingAPI
    Analyze -->|LLM Prompt| OpenAI
    OpenAI -->|JSON Response| Analyze
    Routes -->|Record| Traces
    Routes -->|Update| Metrics
    Analyze -->|Log| Logging
    Execute -->|Log| Logging
    Routes -->|Send Response| Browser
    Traces -->|Display| Dashboard
    Metrics -->|Display| Dashboard
    Config -.->|Env Vars| SF
    Config -.->|Env Vars| Billing
    Config -.->|Env Vars| Analyze
```

## 2. LangGraph Agent Workflow

```mermaid
graph TD
    A["🟢 START"] --> B["fetch_account_node"]
    B -->|account_details| C["analyze_issue_node<br/>(LLM Call)"]
    
    C -->|Output: confidence_score<br/>recommended_actions| D{Confidence >= 5<br/>& Actions?}
    
    D -->|❌ NO<br/>confidence < 5<br/>OR no actions| E["summarize_node<br/>(Error Path)"]
    D -->|✅ YES<br/>confidence >= 5<br/>& actions exist| F["execute_actions_node"]
    
    F -->|1️⃣ create_sf_case| F1["→ Call Salesforce API<br/>OAuth + Case Create"]
    F -->|2️⃣ call_billing_api| F2["→ Call Billing API<br/>Task Creation"]
    
    F1 -->|sf_case_result| G["Update State"]
    F2 -->|billing_result| G
    G -->|actions_executed| E
    
    E -->|final_summary<br/>error| H["🟢 END"]
    
    style A fill:#90EE90
    style H fill:#90EE90
    style D fill:#FFB6C6
    style F fill:#87CEEB
    style E fill:#FFD700
```

## 3. Confidence Scoring & Gating

```mermaid
graph TD
    A["LLM Analyzes Issue<br/>Returns Confidence: 0-10"] --> B{Confidence<br/>Level?}
    
    B -->|9-10| C["Crystal Clear<br/>Specific details provided"]
    B -->|6-8| D["Pretty Clear<br/>Enough info to decide"]
    B -->|4-5| E["Unclear<br/>Missing critical details"]
    B -->|0-3| F["Cannot Understand<br/>Too vague/contradictory"]
    
    C -->|✅| G["Proceed to<br/>execute_actions"]
    D -->|✅| G
    E -->|❌| H["Skip Actions<br/>Route to summarize<br/>with error message"]
    F -->|❌| H
    
    G -->|→ Salesforce API<br/>→ Billing API| I["Actions Executed"]
    H -->|Response: Unable<br/>to understand| J["Final Summary"]
    I --> J
    
    style C fill:#90EE90
    style D fill:#90EE90
    style E fill:#FFB6C6
    style F fill:#FFB6C6
    style G fill:#87CEEB
    style H fill:#FFD700
```

## 4. Conditional Router Logic

```mermaid
graph TD
    A["_route_after_analysis<br/>(Decision Function)"] --> B{Check:<br/>can_understand_issue?}
    
    B -->|FALSE<br/>confidence < 5| C["🔴 Route to SUMMARIZE<br/>Return error response"]
    B -->|TRUE<br/>confidence >= 5| D{Check:<br/>recommended_actions<br/>not empty?}
    
    D -->|NO| E["🟡 Route to SUMMARIZE<br/>No actions needed"]
    D -->|YES| F["🟢 Route to EXECUTE_ACTIONS<br/>Call SF + Billing APIs"]
    
    C --> G["Result: error message<br/>+ detailed instructions"]
    E --> H["Result: summary of<br/>findings only"]
    F --> I["Result: summary<br/>+ API results"]
    
    style C fill:#FFB6C6
    style E fill:#FFD700
    style F fill:#87CEEB
```

## 5. Data Flow Through AgentState

```mermaid
graph LR
    subgraph Input["📥 INPUT (from client)"]
        IN1["account_id"]
        IN2["issue_description"]
    end
    
    subgraph Fetch["fetch_account_node"]
        F1["account_details ← DB lookup"]
    end
    
    subgraph Analyze["analyze_issue_node<br/>(LLM)"]
        A1["issue_analysis"]
        A2["confidence_score 0-10"]
        A3["can_understand_issue boolean"]
        A4["recommended_actions []"]
        A5["sf_case_payload {..}"]
        A6["billing_payload {..}"]
    end
    
    subgraph Execute["execute_actions_node"]
        E1["sf_case_result API response"]
        E2["billing_result API response"]
        E3["actions_executed []"]
    end
    
    subgraph Output["📤 OUTPUT (to client)"]
        OUT1["final_summary"]
        OUT2["error"]
    end
    
    Input --> Fetch
    Fetch --> Analyze
    Analyze --> Execute
    Execute --> Output
    
    A2 -.->|gates execution| Execute
    A4 -.->|determines| Execute
    
    style Input fill:#E8F5E9
    style Output fill:#E8F5E9
```

## 6. State Machine Transitions

```mermaid
stateDiagram-v2
    [*] --> START: Client submits issue
    
    START --> fetch_account: Initialize agent
    note right of START
        AgentState created
        All fields initialized
    end note
    
    fetch_account --> analyze_issue: Account loaded
    note right of fetch_account
        account_details populated
        from DB/CRM
    end note
    
    analyze_issue --> route_decision: LLM returns
    note right of analyze_issue
        issue_analysis
        confidence_score
        recommended_actions
    end note
    
    route_decision --> execute_actions: confidence ≥ 5 & actions exist
    route_decision --> summarize: confidence < 5 OR no actions
    
    execute_actions --> summarize: SF & Billing calls complete
    note right of execute_actions
        sf_case_result
        billing_result
        actions_executed updated
    end note
    
    summarize --> [*]: Response compiled
    note right of summarize
        final_summary generated
        error field set if needed
    end note
```

## 7. API Endpoints & Data Models

```mermaid
graph LR
    subgraph Endpoints["📡 REST Endpoints"]
        POST1["POST /resolve-issue<br/>(Sync)"]
        POST2["POST /resolve-issue/stream<br/>(SSE Streaming)"]
        GET1["GET /actions"]
        GET2["GET /traces"]
        GET3["GET /traces/metrics"]
        GET4["GET /health"]
    end
    
    subgraph Requests["📨 Request Models"]
        REQ["IssueRequest<br/>account_id<br/>issue_description"]
    end
    
    subgraph Responses["📤 Response Models"]
        RESP["IssueResponse<br/>account_id<br/>issue_description<br/>issue_analysis<br/>confidence_score<br/>recommended_actions<br/>actions_executed<br/>sf_case_result<br/>billing_result<br/>final_summary<br/>error"]
        ACT["List[str]<br/>supported actions"]
        TRACES["List[Dict]<br/>execution history"]
        METRICS["Dict<br/>success_rate<br/>avg_confidence<br/>..."]
    end
    
    POST1 --> REQ
    POST2 --> REQ
    REQ --> RESP
    GET1 --> ACT
    GET2 --> TRACES
    GET3 --> METRICS
    
    style Endpoints fill:#E3F2FD
    style Requests fill:#F3E5F5
    style Responses fill:#FCE4EC
```

## 8. External API Integration

```mermaid
graph TB
    subgraph Agent["Agent Execution"]
        Analyze["analyze_issue_node"]
        Execute["execute_actions_node"]
    end
    
    subgraph OpenAIInt["🤖 OpenAI Integration"]
        OA1["LLM Call"]
        OA2["GPT-4o-mini"]
        OA3["temperature=0"]
        OA4["JSON Response"]
    end
    
    subgraph SFInt["🔷 Salesforce Integration"]
        SF1["OAuth 2.0 Flow"]
        SF2["Token Request"]
        SF3["POST Case"]
        SF4["Case Response"]
    end
    
    subgraph BillingInt["💳 Billing Integration"]
        B1["Build Task"]
        B2["HTTP POST"]
        B3["Task Response"]
    end
    
    Analyze -->|Structured Prompt| OA1
    OA1 --> OA2
    OA2 -->|'temp=0'| OA3
    OA3 --> OA4
    OA4 -->|JSON Parse| Analyze
    
    Execute -->|create_sf_case| SF1
    SF1 --> SF2
    SF2 --> SF3
    SF3 --> SF4
    SF4 --> Execute
    
    Execute -->|call_billing_api| B1
    B1 --> B2
    B2 --> B3
    B3 --> Execute
    
    style OA2 fill:#FFE0B2
    style SF3 fill:#C8E6C9
    style B2 fill:#B3E5FC
```

## 9. Error Handling Flow

```mermaid
graph TD
    A["Workflow Executing"] --> B{Error<br/>Occurs?}
    
    B -->|No| C["✅ Success<br/>All steps completed"]
    B -->|Yes| D{Error<br/>Type?}
    
    D -->|DB Lookup| E["Log Warning<br/>Continue with<br/>empty account_details"]
    D -->|LLM API| F["Catch Exception<br/>Set can_understand=False<br/>Route to summarize"]
    D -->|SF API| G["Log Error<br/>Skip SF call<br/>Put error in result"]
    D -->|Billing API| H["Log Error<br/>Skip Billing call<br/>Put error in result"]
    D -->|Parse Error| I["Log & Treat as<br/>Cannot Understand"]
    
    E --> J["Return Error<br/>Response"]
    F --> J
    G --> J
    H --> J
    I --> J
    C --> K["Return<br/>Success<br/>Response"]
    
    J --> L["HTTP 200 OK<br/>(with error details<br/>in response body)"]
    K --> L
    
    style C fill:#90EE90
    style J fill:#FFB6C6
    style L fill:#87CEEB
```

## 10. Execution Timeline

```mermaid
sequenceDiagram
    participant Client
    participant API as FastAPI Layer
    participant Agent as LangGraph Agent
    participant DB as DB/CRM
    participant OpenAI as OpenAI API
    participant SF as Salesforce API
    participant Billing as Billing API

    Client->>API: POST /resolve-issue
    API->>API: Validate & Initialize State
    API->>Agent: Execute graph
    
    Agent->>DB: Fetch account details
    DB-->>Agent: account_details
    Note over Agent: +25ms
    
    Agent->>OpenAI: Send prompt with context
    OpenAI-->>Agent: JSON response (analysis + confidence)
    Note over Agent: +2000-3000ms (LLM latency)
    
    alt Confidence >= 5 & Actions?
        Agent->>SF: create_sf_case (POST Case)
        SF-->>Agent: case_id
        Note over Agent: +200ms
        
        Agent->>Billing: call_billing_api (POST Task)
        Billing-->>Agent: task_id
        Note over Agent: +150ms
    else
        Agent->>Agent: Skip to summarize
    end
    
    Agent->>Agent: Compile final_summary
    Agent-->>API: Return final state
    API->>API: Serialize IssueResponse
    API-->>Client: HTTP 200 + JSON
    
    Note over Client,Billing: Total: ~2.5-3.5 seconds
```

## 11. Database Schema (Future)

```mermaid
erDiagram
    ACCOUNT ||--o{ BILLING_TASK : creates
    ACCOUNT ||--o{ AGENT_TRACE : has
    AGENT_TRACE ||--o{ BILLING_TASK : records
    AGENT_TRACE ||--o{ SALESFORCE_CASE : records
    
    ACCOUNT {
        string account_id PK
        string name
        string email
        string plan
        string status
        float outstanding_balance
        datetime last_payment_date
        float last_payment_amount
    }
    
    AGENT_TRACE {
        string trace_id PK
        string account_id FK
        string issue_description
        int confidence_score
        string issue_analysis
        string[] recommended_actions
        string[] actions_executed
        string final_summary
        float duration_seconds
        string status
        datetime timestamp
    }
    
    BILLING_TASK {
        string transaction_id PK
        string account_id FK
        string action_type
        float amount
        string currency
        string reason
        string notes
        string status
        datetime created_at
        datetime updated_at
    }
    
    SALESFORCE_CASE {
        string case_id PK
        string case_number
        string account_id FK
        string subject
        string priority
        string status
    }
```

## 12. Component Dependency Graph

```mermaid
graph LR
    FastAPI["FastAPI<br/>main.py"]
    Routes["routes.py<br/>(Endpoints)"]
    Schemas["schemas.py<br/>(Validation)"]
    Config["config.py<br/>(Env Vars)"]
    
    Graph["graph.py<br/>(LangGraph)"]
    Nodes["nodes.py<br/>(Node Functions)"]
    State["state.py<br/>(TypedDict)"]
    Prompts["prompts.py<br/>(LLM Prompt)"]
    Tracing["tracing.py<br/>(Observability)"]
    
    SF["salesforce.py<br/>(SF Service)"]
    Billing["billing.py<br/>(Billing Service)"]
    
    Dashboard["dashboard.py<br/>(Streamlit)"]
    
    FastAPI --> Routes
    Routes --> Schemas
    Routes --> Config
    Routes --> Graph
    Routes --> Tracing
    
    Graph --> State
    Graph --> Nodes
    Nodes --> State
    Nodes --> Prompts
    Nodes --> Config
    Nodes --> SF
    Nodes --> Billing
    
    SF --> Config
    Billing --> Config
    
    Dashboard -.->|calls API| Routes
    
    style FastAPI fill:#E3F2FD
    style Routes fill:#E3F2FD
    style Graph fill:#F3E5F5
    style Nodes fill:#F3E5F5
    style SF fill:#C8E6C9
    style Billing fill:#B3E5FC
    style Dashboard fill:#FFE0B2
```

## 13. Mock vs Real Flow

```mermaid
graph TD
    A["execute_actions_node<br/>Decides to call SF API"] --> B{MOCK_SALESFORCE<br/>env var?}
    
    B -->|true| C["Return mock response<br/>MOCK-ACC-001<br/>(Deterministic)"]
    B -->|false| D["Real SF OAuth flow<br/>POST token endpoint<br/>POST case endpoint"]
    
    C --> E["sf_case_result populated"]
    D --> E
    
    E --> F["Local Dev <br/>continues to next action"]
    
    style C fill:#FFE0B2
    style D fill:#C8E6C9
    style F fill:#87CEEB
```

---

This visual representation covers:
1. ✅ System architecture with all components
2. ✅ LangGraph workflow & conditional routing
3. ✅ Confidence gating mechanism
4. ✅ State machine transitions
5. ✅ API endpoints & data models
6. ✅ External API integrations
7. ✅ Error handling paths
8. ✅ Execution sequence & timing
9. ✅ Future database schema
10. ✅ Component dependencies
11. ✅ Mock vs real execution paths
