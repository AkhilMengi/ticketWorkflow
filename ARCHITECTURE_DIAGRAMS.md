# TicketWorkflow - Architecture Diagrams

## 1. System Architecture Overview

```mermaid
graph TB
    Client["🔹 Client/External Systems"]
    
    subgraph API["FastAPI Layer"]
        Endpoint["POST /api/request<br/>GET /api/jobs"]
    end
    
    subgraph Queue["Queue & Job Management"]
        JobSvc["Job Service<br/>(SQLite)"]
        JobDB[(Job Records)]
    end
    
    subgraph Workers["Worker Pool"]
        W1["Worker 1"]
        W2["Worker 2"]
        W3["Worker N"]
    end
    
    subgraph Agent["LangGraph Agent Engine"]
        RG["Routing Graph<br/>(Main Workflow)"]
        CG["Contract Graph<br/>(Contract Creation)"]
        MG["Memory Graph<br/>(Context)"]
    end
    
    subgraph Integrations["Integration Layer"]
        SF["Salesforce<br/>Adapter"]
        Bill["Billing<br/>Adapter"]
        DB["Database<br/>Adapter"]
    end
    
    subgraph External["External Systems"]
        SFA["Salesforce API"]
        BillAPI["Billing System"]
        SQLite[(SQLite DB)]
    end
    
    Client -->|Submit Request| Endpoint
    Endpoint -->|Create Job| JobSvc
    JobSvc -->|Store| JobDB
    JobSvc -->|Queue| W1 & W2 & W3
    W1 & W2 & W3 -->|Execute| RG & CG
    RG & CG -->|Call| SF & Bill & DB
    SF -->|API Call| SFA
    Bill -->|Integrate| BillAPI
    DB -->|Query| SQLite
    
    RG -->|Update Result| JobSvc
    JobSvc -->|Response| Endpoint
    Endpoint -->|Return| Client
    
    style API fill:#4CAF50,stroke:#2E7D32,color:#fff
    style Queue fill:#2196F3,stroke:#1565C0,color:#fff
    style Workers fill:#FF9800,stroke:#E65100,color:#fff
    style Agent fill:#9C27B0,stroke:#6A1B9A,color:#fff
    style Integrations fill:#F44336,stroke:#C62828,color:#fff
    style External fill:#607D8B,stroke:#37474F,color:#fff
```

---

## 2. Complete Request Processing Flow

```mermaid
graph TD
    A["📥 Request Received<br/>{user_id, issue_type,<br/>message, context}"] 
    
    B["🏪 Job Service<br/>Create job record<br/>Status: PENDING"]
    
    C["⏳ Queue to Worker<br/>Async execution"]
    
    D{{"🤖 Routing Graph Starts"}}
    
    E["📍 DECIDE Node<br/>Determine context needed"]
    
    F["📿 Enrichment Phase"]
    F1["🔍 fetch_profile"]
    F2["📋 fetch_logs"]
    F3["🎫 fetch_tickets"]
    
    G["🧠 ROUTING Node<br/>Classification:<br/>SF|Billing|Manual"]
    
    H{{"Which System?"}}
    
    I["✅ SF Route<br/>Confidence: High"]
    J["✅ Billing Route<br/>Confidence: High"]
    K["✅ Intelligent Route<br/>Multi-Action"]
    L["⚠️ Manual Review<br/>Low Confidence"]
    
    I1["SF Adapter"]
    J1["Billing Adapter"]
    K1["Intelligent Adapter"]
    L1["Manual Review"]
    
    M["📊 AGGREGATION Node<br/>Combine results<br/>Create audit trail"]
    
    N["💾 Update Job<br/>Status: COMPLETED<br/>Store results"]
    
    O["✨ Return Result<br/>Case ID / Credits<br/>Audit Log"]
    
    A --> B --> C --> D
    D --> E --> F
    F --> F1 & F2 & F3
    F1 & F2 & F3 --> G
    
    G --> H
    H -->|Technical Issue| I
    H -->|Billing Issue| J
    H -->|Complex| K
    H -->|Unknown| L
    
    I --> I1
    J --> J1
    K --> K1
    L --> L1
    
    I1 --> M
    J1 --> M
    K1 --> M
    L1 --> M
    
    M --> N --> O
    
    style A fill:#E3F2FD,stroke:#1976D2
    style B fill:#F3E5F5,stroke:#7B1FA2
    style D fill:#9C27B0,stroke:#6A1B9A,color:#fff
    style G fill:#9C27B0,stroke:#6A1B9A,color:#fff
    style H fill:#FF9800,stroke:#E65100,color:#fff
    style M fill:#4CAF50,stroke:#2E7D32,color:#fff
    style O fill:#00BCD4,stroke:#006064,color:#fff
```

---

## 3. LangGraph - Routing Workflow State Machine

```mermaid
graph LR
    START["🟢 START"]
    
    DECIDE["Node: decide<br/>Analyze context"]
    
    subgraph Enrichment["Enrichment Phase"]
        PROF["fetch_profile"]
        LOGS["fetch_logs"]
        TICK["fetch_tickets"]
    end
    
    ROUTE["Node: routing<br/>Classify issue<br/>SF|Billing|Manual"]
    
    subgraph Execution["Execution Phase"]
        SF["sf_execution<br/>Create case<br/>Add comments"]
        BILL["billing_execution<br/>Process refund<br/>Update account"]
        INT["intelligent_routing<br/>Multi-action"]
        MAN["manual_review<br/>Escalate"]
    end
    
    AGG["Node: aggregation<br/>Combine results<br/>Create audit"]
    
    END["🔴 END"]
    
    COND1{{"Route<br/>Decision"}}
    COND2{{"Exec<br/>Type"}}
    
    START --> DECIDE
    DECIDE --> Enrichment
    PROF -.->|Async| ROUTE
    LOGS -.->|Async| ROUTE
    TICK -.->|Async| ROUTE
    
    ROUTE --> COND1
    COND1 -->|SF| COND2
    COND1 -->|Billing| COND2
    COND1 -->|Intelligent| COND2
    COND1 -->|Manual| COND2
    
    COND2 -->|SF Request| SF
    COND2 -->|Billing Request| BILL
    COND2 -->|Multi-Action| INT
    COND2 -->|Low Confidence| MAN
    
    SF --> AGG
    BILL --> AGG
    INT --> AGG
    MAN --> AGG
    
    AGG --> END
    
    style START fill:#4CAF50,color:#fff
    style END fill:#F44336,color:#fff
    style DECIDE fill:#2196F3,color:#fff
    style ROUTE fill:#9C27B0,color:#fff
    style Enrichment fill:#FF9800,stroke:#E65100,color:#fff
    style Execution fill:#00BCD4,stroke:#006064,color:#fff
    style AGG fill:#8BC34A,color:#fff
```

---

## 4. Three Core Workflow Types

```mermaid
graph TB
    subgraph W1["Workflow 1: Simple SF Integration"]
        W1A["Input:<br/>user_id, tech_issue"]
        W1B["Classify:<br/>Technical → SF"]
        W1C["Create Case"]
        W1D["Return: case_id"]
        W1A --> W1B --> W1C --> W1D
    end
    
    subgraph W2["Workflow 2: Intelligent SF"]
        W2A["Input:<br/>Complex issue<br/>+ context"]
        W2B["Classify +<br/>Run AI Agent"]
        W2C["Parse Suggestions"]
        W2D["Map to Actions:<br/>Primary<br/>Secondary<br/>Tertiary"]
        W2E["Execute<br/>Multi-action"]
        W2F["Return:<br/>Results + Audit"]
        W2A --> W2B --> W2C --> W2D --> W2E --> W2F
    end
    
    subgraph W3["Workflow 3: Contract Generation"]
        W3A["Input:<br/>Tenant info<br/>Dates"]
        W3B["Validate:<br/>Dates<br/>Required fields"]
        W3C["Prepare:<br/>Format data<br/>Template fill"]
        W3D["Create:<br/>Generate ID<br/>Store DB"]
        W3E["Return:<br/>contract_id<br/>PDF"]
        W3A --> W3B --> W3C --> W3D --> W3E
    end
    
    style W1 fill:#B3E5FC,stroke:#01579B,color:#000
    style W2 fill:#E1BEE7,stroke:#4A148C,color:#000
    style W3 fill:#C8E6C9,stroke:#1B5E20,color:#000
```

---

## 5. Data Flow - Intelligent Action Service

```mermaid
graph LR
    A["Customer<br/>Issue"]
    
    B["Extract<br/>Context"]
    
    C["Load<br/>suggestions.txt"]
    
    D["🤖 OpenAI<br/>GPT-4<br/>Analyze"]
    
    E["Parse<br/>Response"]
    
    F{{"Action<br/>Type?"}}
    
    G["SalesforceAdapter"]
    H["BillingAdapter"]
    I["ManualAdapter"]
    
    J["Execute<br/>Action"]
    
    K["Collect<br/>Results"]
    
    L["Return:<br/>Primary<br/>Secondary<br/>Tertiary"]
    
    A --> B --> C
    B --> D
    C --> D
    
    D --> E --> F
    
    F -->|Create Case| G
    F -->|Apply Credit| H
    F -->|Escalate| I
    
    G --> J
    H --> J
    I --> J
    
    J --> K --> L
    
    style D fill:#9C27B0,stroke:#6A1B9A,color:#fff
    style L fill:#4CAF50,stroke:#2E7D32,color:#fff
```

---

## 6. Why LangGraph vs LangChain

```mermaid
graph TB
    subgraph LCH["❌ LangChain Approach"]
        LC1["Sequential Chains"]
        LC2["Hidden State"]
        LC3["Tool-based Actions"]
        LC4["Callback Chains"]
        LC5["Complex Debugging"]
        
        LC1 --> LC2 --> LC3 --> LC4 --> LC5
    end
    
    subgraph LG["✅ LangGraph Approach"]
        LG1["State Machine"]
        LG2["Explicit State<br/>in TypedDict"]
        LG3["Conditional Edges<br/>Based on State"]
        LG4["Centralized<br/>Decision Logic"]
        LG5["Clear<br/>Debugging Path"]
        
        LG1 --> LG2 --> LG3 --> LG4 --> LG5
    end
    
    CHOICE["TicketWorkflow<br/>Uses LangGraph"]
    
    LCH -.->|Rejected| CHOICE
    LG -->|Chosen| CHOICE
    
    style LCH fill:#FFEBEE,stroke:#C62828
    style LG fill:#E8F5E9,stroke:#2E7D32
    style CHOICE fill:#E3F2FD,stroke:#1976D2
```

---

## 7. Service Adapter Pattern

```mermaid
graph TB
    A["Intelligent<br/>Action Node"]
    
    SUGGEST["AI Suggestions<br/>from LLM"]
    
    MAP["Action Type<br/>Mapping"]
    
    ADAPTER{{"Which<br/>Adapter?"}}
    
    SF["🔹 SalesforceAdapter<br/>- validate_action<br/>- execute"]
    
    BILL["💳 BillingAdapter<br/>- validate_action<br/>- execute"]
    
    MANUAL["👤 ManualAdapter<br/>- validate_action<br/>- execute"]
    
    SFA["Salesforce<br/>REST API"]
    
    BA["Billing<br/>System"]
    
    MA["Human<br/>Team"]
    
    RESULT["Combined<br/>Results"]
    
    A --> SUGGEST --> MAP --> ADAPTER
    
    ADAPTER -->|SF Action| SF
    ADAPTER -->|Billing Action| BILL
    ADAPTER -->|Manual Action| MANUAL
    
    SF -->|REST| SFA
    BILL -->|Integration| BA
    MANUAL -->|Queue| MA
    
    SFA --> RESULT
    BA --> RESULT
    MA --> RESULT
    
    style ADAPTER fill:#FF9800,stroke:#E65100,color:#fff
    style SF fill:#4CAF50,stroke:#2E7D32,color:#fff
    style BILL fill:#2196F3,stroke:#1565C0,color:#fff
    style MANUAL fill:#9C27B0,stroke:#6A1B9A,color:#fff
```

---

## 8. State Management Structure

```mermaid
graph LR
    INPUT["Input<br/>{<br/>  user_id,<br/>  issue_type,<br/>  message,<br/>  context<br/>}"]
    
    STATE{{"EnhancedAgentState<br/>(TypedDict)<br/>━━━━━━━━━━━━━━━━"}}
    
    CLASSIFY["Classification<br/>{<br/>  type: SF|Billing,<br/>  confidence: 0.92,<br/>  reason: ...<br/>}"]
    
    ACTIONS["Actions<br/>{<br/>  primary: {...},<br/>  secondary: {...},<br/>  tertiary: {...}<br/>}"]
    
    AUDIT["Audit Trail<br/>{<br/>  decisions: [],<br/>  actions_taken: [],<br/>  timestamps: [],<br/>  status: ...<br/>}"]
    
    OUTPUT["Output<br/>{<br/>  case_id,<br/>  results,<br/>  audit_log<br/>}"]
    
    INPUT -->|1️⃣ Initial| STATE
    STATE -->|2️⃣ Classify| CLASSIFY
    CLASSIFY -->|3️⃣ Execute| ACTIONS
    ACTIONS -->|4️⃣ Track| AUDIT
    AUDIT -->|5️⃣ Return| OUTPUT
    
    style STATE fill:#9C27B0,stroke:#6A1B9A,color:#fff
    style CLASSIFY fill:#2196F3,stroke:#1565C0,color:#fff
    style ACTIONS fill:#FF9800,stroke:#E65100,color:#fff
    style AUDIT fill:#4CAF50,stroke:#2E7D32,color:#fff
```

---

## 9. Contract Generation Workflow (LangGraph)

```mermaid
graph TD
    START["Start<br/>Contract Request"]
    
    NODE1["Node: validation<br/>━━━━━━━━━━━━━<br/>✓ Check dates<br/>✓ Verify tenant<br/>✓ Field check"]
    
    COND1{{"Validation<br/>Result"}}
    
    REJECT["Reject<br/>Return error"]
    
    NODE2["Node: prepare<br/>━━━━━━━━━━━━━<br/>✓ Format data<br/>✓ Fill template<br/>✓ Calculate"]
    
    NODE3["Node: create<br/>━━━━━━━━━━━━━<br/>✓ Generate ID<br/>✓ Store in DB<br/>✓ Create PDF"]
    
    NODE4["Node: summarize<br/>━━━━━━━━━━━━━<br/>✓ Return result<br/>✓ Include ID<br/>✓ Add metadata"]
    
    END["End<br/>Return:{<br/>  contract_id,<br/>  status,<br/>  pdf_url<br/>}"]
    
    START --> NODE1
    NODE1 --> COND1
    
    COND1 -->|FAIL| REJECT
    COND1 -->|PASS| NODE2
    
    NODE2 --> NODE3 --> NODE4 --> END
    REJECT --> END
    
    style NODE1 fill:#2196F3,stroke:#1565C0,color:#fff
    style NODE2 fill:#FF9800,stroke:#E65100,color:#fff
    style NODE3 fill:#4CAF50,stroke:#2E7D32,color:#fff
    style NODE4 fill:#9C27B0,stroke:#6A1B9A,color:#fff
    style START fill:#E3F2FD,stroke:#1976D2
    style END fill:#E8F5E9,stroke:#2E7D32
```

---

## 10. Multi-Action Orchestration Flow

```mermaid
graph TB
    ISSUE["Complex<br/>Issue"]
    
    LLM["🤖 LLM Analyzes<br/>Returns suggestions"]
    
    PRIMARY["Primary Action<br/>High confidence<br/>Main resolution"]
    
    SECONDARY["Secondary Action<br/>Supporting<br/>Context"]
    
    TERTIARY["Tertiary Action<br/>Follow-up<br/>Prevention"]
    
    EX1["Execute<br/>Primary"]
    EX2["Execute<br/>Secondary"]
    EX3["Execute<br/>Tertiary"]
    
    R1["Result 1:<br/>Case created"]
    R2["Result 2:<br/>Label added"]
    R3["Result 3:<br/>Task created"]
    
    AGG["Aggregate<br/>All Results"]
    
    FINAL["Final Output:<br/>{<br/>  primary: {...},<br/>  secondary: {...},<br/>  tertiary: {...}<br/>}"]
    
    ISSUE --> LLM
    
    LLM --> PRIMARY
    LLM --> SECONDARY
    LLM --> TERTIARY
    
    PRIMARY --> EX1 --> R1
    SECONDARY --> EX2 --> R2
    TERTIARY --> EX3 --> R3
    
    R1 --> AGG
    R2 --> AGG
    R3 --> AGG
    
    AGG --> FINAL
    
    style ISSUE fill:#E3F2FD,stroke:#1976D2
    style LLM fill:#9C27B0,stroke:#6A1B9A,color:#fff
    style PRIMARY fill:#4CAF50,stroke:#2E7D32,color:#fff
    style SECONDARY fill:#FF9800,stroke:#E65100,color:#fff
    style TERTIARY fill:#2196F3,stroke:#1565C0,color:#fff
    style FINAL fill:#00BCD4,stroke:#006064,color:#fff
```

---

## 11. Component Interaction Matrix

```mermaid
graph TB
    FC["FastAPI<br/>Controller"]
    JS["Job<br/>Service"]
    WP["Worker<br/>Pool"]
    RG["Routing<br/>Graph"]
    CG["Contract<br/>Graph"]
    SF["SF<br/>Adapter"]
    BA["Billing<br/>Adapter"]
    DB["Database"]
    
    FC -->|Create Job| JS
    JS -->|Queue| WP
    WP -->|Execute| RG
    WP -->|Execute| CG
    
    RG -->|Call| SF
    RG -->|Call| BA
    RG -->|Call| DB
    
    CG -->|Store| DB
    
    SF -->|Salesforce API| FC
    BA -->|Billing API| FC
    
    style FC fill:#4CAF50,color:#fff
    style JS fill:#2196F3,color:#fff
    style WP fill:#FF9800,color:#fff
    style RG fill:#9C27B0,color:#fff
    style CG fill:#9C27B0,color:#fff
    style SF fill:#F44336,color:#fff
    style BA fill:#F44336,color:#fff
    style DB fill:#607D8B,color:#fff
```

---

## 12. End-to-End Execution Timeline

```mermaid
timeline
    title End-to-End Request Processing Timeline
    
    section Request
        T1: 0ms : Request arrives at FastAPI
        T2: 10ms : Validation & schema check
        T3: 50ms : Job created in DB
    
    section Queue
        T4: 100ms : Queued to worker
    
    section Enrichment
        T5: 150ms : Worker picks up
        T6: 300ms : Fetch customer profile
        T7: 500ms : Fetch issue logs
    
    section Classification
        T8: 1000ms : Send to classifier
        T9: 2000ms : Receive classification
    
    section Execution
        T10: 2100ms : Route to SF adapter
        T11: 2500ms : Create Salesforce case
        T12: 3500ms : Add comments
        T13: 4000ms : Intelligent secondary action
    
    section Response
        T14: 4100ms : Aggregate results
        T15: 4200ms : Update job record
        T16: 4300ms : Response ready for client
        
    section Total: ~4.3 seconds async
        Complete: ✅
```

