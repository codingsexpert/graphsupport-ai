# GraphSupport AI — System Architecture

## 1. Overview and Vision

**GraphSupport AI** is an intelligent, context-aware customer support engine. Traditional support bots treat inquiries as isolated queries or rely solely on flat vector databases, often missing relationships between products, known defects, customer ticket histories, and past troubleshooting attempts.

GraphSupport AI bridges this gap by persisting a connected property graph in **Neo4j** and pairing it with an LLM reasoning agent in later phases. The graph preserves cross-session context:
- Customer identity, subscription tier, and product ownership.
- Historical support tickets, triage logs, and symptom patterns.
- Product topologies, firmware versions, and known component failures.
- Step-by-step troubleshooting attempts and verified resolutions.

```
+-----------------------------------------------------------------------------------+
|                                Streamlit UI (app.py)                              |
|   - Customer Support Portal   - Ticket Dashboard   - Database Control Panel       |
+------------------------------------------+----------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------+
|                   Application Service Layer (graphsupport.application)            |
|   - SupportService: Validation, Workflows, Authorization Boundary Guards          |
+------------------------------------------+----------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------+
|                      Graph Persistence Layer (graphsupport.graph)                 |
|   - Repositories: Customer, Product, Ticket, Conversation, Troubleshooting        |
|   - Driver Manager (Pooling/TLS) - Schema Constraints - Idempotent Cypher         |
+------------------------------------------+----------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------+
|                        Core Layer (graphsupport.core)                             |
|   - Database Exception Hierarchy  - Structured Logging   - Health & Diagnostics   |
+------------------------------------------+----------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------+
|                       Config Layer (graphsupport.config)                          |
|   - Pydantic Settings         - Environment Loading    - Secret Masking           |
+------------------------------------------+----------------------------------------+
                                           |
         +---------------------------------+---------------------------------+
         | (Operational in Phase 3)                                          | (Reserved for Phase 5)
         v                                                                   v
+----------------------------------+               +----------------------------------+
|      Neo4j Graph Database        |               |      LLM Reasoning Engine        |
| - Customers, Tickets, Products   |               | - Subgraph Context Injection     |
| - Issues, Steps, Resolutions     |               | - Dynamic Tool Calling           |
+----------------------------------+               +----------------------------------+
```

---

## 2. Graph Schema & Domain Model (Phase 3)

### A. Graph Nodes
All core entities employ durable application-generated UUID4 identifiers as primary keys:

- `Customer` (`:Customer`): `id` (UUID, UNIQUE), `email` (string, UNIQUE), `name`, `tier`, `created_at`, `metadata`.
- `Product` (`:Product`): `id` (UUID, UNIQUE), `name`, `sku` (string, INDEXED), `category`, `version`, `metadata`.
- `Issue` (`:Issue`): `id` (UUID, UNIQUE), `title`, `description`, `category`, `severity`, `created_at`.
- `SupportTicket` (`:SupportTicket`): `id` (UUID, UNIQUE), `title`, `description`, `status` (enum, INDEXED), `priority`, `created_at`, `updated_at`.
- `Conversation` (`:Conversation`): `id` (UUID, UNIQUE), `session_id`, `channel`, `started_at`, `status`.
- `Message` (`:Message`): `id` (UUID, UNIQUE), `sender_type`, `content`, `sequence_number`, `timestamp`.
- `TroubleshootingStep` (`:TroubleshootingStep`): `id` (UUID, UNIQUE), `step_number`, `action`, `outcome` (enum), `notes`, `executed_at`, `previous_step_id`.
- `Resolution` (`:Resolution`): `id` (UUID, UNIQUE), `summary`, `resolution_type`, `verified`, `created_at`.

### B. Graph Relationships
```
(:Customer)-[:USES]->(:Product)
(:Customer)-[:HAS_TICKET]->(:SupportTicket)
(:Product)-[:HAS_ISSUE]->(:Issue)
(:Issue)-[:TRACKED_BY]->(:SupportTicket)
(:SupportTicket)-[:AFFECTS]->(:Product)
(:SupportTicket)-[:HAS_RESOLUTION]->(:Resolution)
(:SupportTicket)-[:HAS_ATTEMPT]->(:TroubleshootingStep)
(:TroubleshootingStep)-[:FOLLOWED_BY]->(:TroubleshootingStep)
(:Customer)-[:HAS_CONVERSATION]->(:Conversation)
(:Conversation)-[:CONTAINS]->(:Message)
(:Message)-[:ABOUT]->(:SupportTicket)
```

### C. Domain Enums
- `TicketStatus`: `open`, `in_progress`, `resolved`, `closed`.
- `TroubleshootingOutcome`: `success`, `failed`, `partial`, `unknown`.

---

## 3. Database Driver & Security Architecture

1. **Encrypted Aura Transport**: Uses official `neo4j` Python driver with `neo4j+s://` protocol and TLS encryption.
2. **Deterministic Connection Pooling**: Configured with explicit `connection_timeout` (15s) and `max_connection_lifetime` (3600s).
3. **Secret Isolation**: `neo4j_password` is encapsulated as `SecretStr`. Passwords and credentials are never emitted in exceptions, logs, or UI elements.
4. **Parameterized Cypher**: All repository operations strictly use query parameters (`$id`, `$email`, etc.). String interpolation for Cypher queries is strictly prohibited.
5. **Idempotent Schema Application**: All DDL statements utilize `IF NOT EXISTS` semantics, making schema initialization safe to execute repeatedly without dropping or modifying existing data.

---

## 4. Application & Repository Layer (Phase 3)

### A. Modular Repositories (`graphsupport.graph.repositories`)
- **`CustomerRepository`**: Handles customer creation, unique constraint validation, safe field updates, and deterministic paginated retrieval.
- **`ProductRepository`**: Manages product catalog upserts and idempotent customer usage linking via `(:Customer)-[:USES]->(:Product)`.
- **`TicketRepository`**: Coordinates atomic creation of tickets linked to customers, affected products, and tracked issues. Provides multi-hop ticket detail graph traversal.
- **`ConversationRepository`**: Appends sequential messages with tie-breaking ordering (`ORDER BY sequence_number ASC, timestamp ASC, id ASC`) and optional ticket context links (`[:ABOUT]`).
- **`TroubleshootingRepository`**: Records ordered troubleshooting attempts, validates ticket context for chained `[:FOLLOWED_BY]` edges, and persists verified resolutions.

### B. Application Coordinator (`graphsupport.application.SupportService`)
- Validates all business inputs prior to persistence.
- Enforces customer context and authorization boundaries across conversations and tickets.
- Translates database-level constraint violations into structured domain exceptions (`DuplicateEntityError`, `EntityNotFoundError`, `ValidationError`).
- Ensures non-destructive updates so customer identity cannot be accidentally replaced.

---

## 5. Persistent Graph Memory & Context Retrieval (Phase 4)

### A. Memory Subsystem Architecture (`graphsupport.memory`)

```
+------------------------------------------------------------------------------------+
|               SupportService.retrieve_customer_context(customer_id, ...)           |
+------------------------------------------------------------------------------------+
                                           |
                                           v
+------------------------------------------------------------------------------------+
|                  HistoryRetriever (graphsupport.memory.history_retriever)          |
|  - Validates customer ID and queries customer existence in Neo4j                  |
|  - Enforces tenant ownership checks (Ticket must belong to Customer)              |
|  - Parameterized subgraphs: Products, Tickets, Issues, Attempts, Resolutions      |
+------------------------------------------+-----------------------------------------+
                                           |
                                           v
+------------------------------------------------------------------------------------+
|                  RelevanceRanker (graphsupport.memory.relevance_ranker)            |
|  - Deterministic scoring: active tickets, ticket ID match, product match,          |
|    keyword overlap, recency decay, failed attempts weight                          |
|  - Zero embeddings / vector databases / external ranking APIs                     |
+------------------------------------------+-----------------------------------------+
                                           |
                                           v
+------------------------------------------------------------------------------------+
|                   ContextBuilder (graphsupport.memory.context_builder)              |
|  - Bounded assembly per RetrievalLimits (max_tickets, max_messages)                |
|  - Diagnostic missing-information flags (e.g. ticket_<id>_has_failed_attempt)      |
|  - Output: Serializable CustomerMemoryContext suitable for future Phase 5 LLM     |
+------------------------------------------------------------------------------------+
```

### B. Deterministic Relevance Scoring Criteria

Tickets are ranked using transparent, explainable scoring criteria:
1. **Explicit Ticket ID Match (+30.0)**: Highest weight when user or operator focuses on a specific ticket.
2. **Active Ticket Status (+15.0 / +12.0)**: `in_progress` (+15.0), `open` (+12.0), `resolved` (+3.0), `closed` (+1.0).
3. **Product Match (+10.0 / +3.0)**: Queried product match (+10.0), or customer-associated product (+3.0).
4. **Issue Keyword Overlap (Up to +15.0)**: Tokenized overlap against ticket title, description, and issue summaries (+5.0 per token match, capped at +15.0).
5. **Recency Boost (+6.0 to +0.5)**: Decaying recency based on `updated_at` or `created_at` (≤24h: +6.0, ≤7d: +4.0, ≤30d: +2.0, >30d: +0.5).
6. **Diagnostic History Weight (+4.0 / +2.0)**: Tickets with unresolved failed troubleshooting attempts receive +4.0 weight to avoid repeating failed actions; partial attempts receive +2.0.

### C. Outcome Fidelity & Persistence Guarantees

1. **Strict Outcome Preservation**: Historical diagnostic outcomes are never mutated:
   - A `failed` attempt remains strictly `failed`.
   - A `success` attempt remains strictly `success`.
   - Unknown outcomes remain `unknown`.
2. **Cross-Session Durability**: Neo4j is the single source of truth. Destroying the application session and instantiating a fresh service instance produces the exact same context.
3. **Anti-Hallucination Guard**: Historical data is never upgraded to confirmed facts without new database evidence. If no registered product or prior ticket exists, missing-information indicators (`no_prior_tickets_found`, `no_registered_products`) explicitly mark the absence of data.
4. **Tenant Isolation**: Tickets belonging to another customer are strictly filtered out; explicit access attempts raise `AuthorizationError`.

---

## 6. Context-Aware AI Support Agent Architecture (Phase 5)

### A. Subsystem Modules (`graphsupport.agents`)
- **`SupportAgent`**: Core orchestrator handling customer validation, graph memory retrieval, bounded prompt assembly, tool execution loop, output verification, and Neo4j conversation persistence.
- **`LLMProvider`**: Provider abstraction isolating model communication (`GoogleGeminiProvider`, `OpenAIProvider`, `MockLLMProvider`).
- **`ToolRegistry`**: Sandboxed tool registry exposing only approved domain tools. Rejects arbitrary code/shell execution and strictly enforces authorized customer ownership.
- **`prompt_templates`**: Trusted system instructions, memory grounding formatting, and anti-injection instructions.
- **`output_parser`**: Post-generation validator checking for internal token leaks, status transitions against tool evidence, and providing safe fallback messages when claims cannot be verified.

### B. Agent Lifecycle & Data Flow
```
User Message
    │
    ▼
[ 1. Validate Customer & Input ]  ──> Length check, identity validation
    │
    ▼
[ 2. Retrieve Graph Memory ]       ──> HistoryRetriever (ranked tickets, products, attempts)
    │
    ▼
[ 3. Assemble Prompt & Context ]   ──> BASE_SYSTEM_INSTRUCTIONS + formatted evidence + history
    │
    ▼
[ 4. Configurable LLM Provider ]   ──> Google Gemini / OpenAI / Mock with timeouts
    │
    ├── Tool Calls Requested?
    │        │
    │        ▼
    │   [ 5. Tool Registry ]      ──> Enforces customer ID, executes domain tools (max 4 iters)
    │        │
    │        └── Feeds tool result back to LLM
    │
    ▼
[ 6. Response Validation ]        ──> Verifies claims against evidence, sanitizes errors
    │
    ▼
[ 7. Conversation Persistence ]   ──> Atomic storage of user & assistant turns in Neo4j
    │
    ▼
UI Response Display
```

### C. Tool Safety & Guardrails
- **Identity Pinning**: Tools never trust a `customer_id` parameter generated by the LLM. Every tool call is locked to `self.authorized_customer_id` set by the application.
- **Bounded Iteration**: Tool loop is strictly limited to 4 iterations (`max_tool_iterations=4`) to prevent infinite recursive calls.
- **Strict Read/Write Schemas**: Each tool declares typed input parameters and validated output objects.
- **No Arbitrary Code**: The model cannot execute Python, shell commands, raw Cypher, or unauthenticated HTTP requests.


