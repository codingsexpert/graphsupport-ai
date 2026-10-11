# GraphSupport AI

> **Context-Aware Customer Support Agent Powered by Neo4j Knowledge Graphs & LLM Reasoning**

GraphSupport AI is an enterprise customer support platform designed to remember customers, products, tickets, troubleshooting attempts, conversations, and verified resolutions across sessions using a connected Neo4j knowledge graph.

---

## 📌 Implementation Status

| Phase | Milestone | Status | Details |
|---|---|---|---|
| **Phase 1** | **Professional Foundation** | **Completed** | Modular Python package, typed configuration, logging, health check, UI scaffold, automated tests |
| **Phase 2** | **Neo4j Schema & Storage** | **Completed** | Neo4j driver connection pooling, graph models, uniqueness constraints, indexes, customer repository |
| **Phase 3** | **Persistent Customer Support Data Layer** | **Completed** | Persistent Customers, Products, Issues, Tickets, Conversations, Messages, Attempts, Resolutions, Service layer, Streamlit Workbench |
| **Phase 4** | **Graph Retrieval & Memory** | **Completed** | Persistent graph memory, customer context retrieval, deterministic relevance ranking, outcome fidelity, Streamlit Memory Inspector |
| **Phase 5** | **Context-Aware LLM Agent** | **Completed** | Configurable LLM provider (Gemini, OpenAI, Mock), 7 domain tools, grounded prompt templates, response validator, Streamlit AI Chat |
| **Phase 6** | **Interactive Support Dashboard** | **Completed** | 10-page operations dashboard, customer 360, ticket lifecycle, interactive vis.js graph explorer, offline evaluation suite |
| **Phase 7** | **Security Hardening & Production Polish** | **Completed** | Threat modeling, tenant isolation, prompt-injection scanner, tool deduplication, rate limiting, correlation IDs, 138 tests |
| **Phase 8** | **Final Evaluation, E2E Demo & Hackathon Readiness** | **Completed** | 10-step E2E flow tests, 9-vector evaluation benchmark, Sarah Chen demo scenario seeder, CLI tooling, presentation materials |

---

## 🧠 Persistent Graph Memory & Retrieval (Phase 4)

Phase 4 establishes cross-session persistent customer memory using deterministic graph retrieval from Neo4j. It provides the structured context layer required for subsequent LLM reasoning in Phase 5 without premature AI agent logic, embeddings, or external vector databases.

### 1. Memory Architecture Components (`graphsupport.memory`)
- **`HistoryRetriever`**: Parameterized Cypher queries traversing customer products, open/recent tickets, issues, sequential attempts, resolutions, and messages with strict customer ownership validation.
- **`RelevanceRanker`**: Transparent, deterministic ranking scoring tickets by active status, explicit ticket match, product match, keyword overlap, recency decay, and failed attempt weight.
- **`ContextBuilder`**: Compiles raw retrieved graph records into a bounded, serializable `CustomerMemoryContext` model with diagnostic missing-information indicators (`no_prior_tickets_found`, `ticket_<id>_has_failed_attempt_step_<n>`).
- **`MemoryWriter`**: Safely coordinates write operations for new interactions, diagnostic attempts, and resolutions through `SupportService`.

### 2. Deterministic Relevance Ranking Formula
| Factor | Weight | Condition |
|---|---|---|
| **Explicit Ticket Match** | `+30.0` | Focuses on queried `ticket_id` parameter |
| **Active Status** | `+15.0` / `+12.0` | `in_progress` (+15.0), `open` (+12.0), `resolved` (+3.0), `closed` (+1.0) |
| **Product Match** | `+10.0` / `+3.0` | Queried product match (+10.0), customer product portfolio match (+3.0) |
| **Keyword Overlap** | Up to `+15.0` | `+5.0` per token match against ticket title, description, and issue text |
| **Recency Decay** | `+6.0` to `+0.5` | ≤24h (+6.0), ≤7d (+4.0), ≤30d (+2.0), >30d (+0.5) |
| **Diagnostic History** | `+4.0` / `+2.0` | Unresolved failed attempts (+4.0) to prioritize issues needing alternative fixes; partial attempts (+2.0) |

### 3. Outcome Fidelity Guarantees
- **No Outcome Mutation**: Failed diagnostic attempts remain strictly `failed`; successful attempts remain `success`. Historical facts are never inverted or upgraded without verified evidence.
- **Anti-Hallucination Boundaries**: Missing information is explicitly flagged via `missing_information` indicator strings instead of assuming defaults.
- **Tenant Isolation**: Tickets belonging to other customers are blocked at the application boundary (`AuthorizationError`).

---

## 🕸️ Graph Data Architecture (Phase 3 & 4)

### Node Entities
- `Customer`: Unique customer identity (`id` UUID, `email` UNIQUE, `name`, `tier`, `created_at`, `metadata`).
- `Product`: Catalog products and hardware devices (`id` UUID, `name`, `sku` INDEXED, `category`, `version`).
- `Issue`: Canonical defects and symptom classification (`id` UUID, `title`, `description`, `category`, `severity`).
- `SupportTicket`: Customer support tickets (`id` UUID, `title`, `status` INDEXED, `priority`, `created_at`, `updated_at`).
- `Conversation`: Support session context (`id` UUID, `session_id`, `channel`, `started_at`, `status`).
- `Message`: Transcript entry (`id` UUID, `sender_type`, `content`, `sequence_number`, `timestamp`).
- `TroubleshootingStep`: Diagnostic actions (`id` UUID, `step_number`, `action`, `outcome`, `notes`, `executed_at`).
- `Resolution`: Verified solutions (`id` UUID, `summary`, `resolution_type`, `verified`, `created_at`).

### Graph Relationships
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

---

## 🛠️ Phase 3 Supported Operations

### 1. Customer Persistence
- **Create**: Create customer with stable application-generated ID. Duplicate IDs or emails are rejected (`DuplicateEntityError`).
- **Upsert**: Idempotent update without resetting unmodified properties.
- **Update**: Update explicitly permitted fields (`name`, `tier`, `metadata`) while preserving identity and email.
- **Retrieve & List**: Fetch by ID, email, or paginated deterministic listing.

### 2. Product Persistence & Linking
- **Upsert**: Idempotent product creation with SKU indexing.
- **Link**: Link customer to product via `(:Customer)-[:USES]->(:Product)` with idempotent relationship semantics.
- **Retrieve**: List products and query customer product portfolios.

### 3. Support Tickets and Issues
- **Issue Ingestion**: Create known defects linked to products via `(:Product)-[:HAS_ISSUE]->(:Issue)`.
- **Atomic Ticket Creation**: Create support ticket atomically linked to `(:Customer)-[:HAS_TICKET]->(:SupportTicket)`, `(:SupportTicket)-[:AFFECTS]->(:Product)`, and optional `(:Issue)-[:TRACKED_BY]->(:SupportTicket)`.
- **Status Lifecycle**: Transition ticket status (`open`, `in_progress`, `resolved`, `closed`).
- **Context Inspection**: Traversal retrieving customer, product, issue, troubleshooting steps, and resolutions in one call.

### 4. Conversations and Messages
- **Session Tracking**: Create conversation linked to customer `(:Customer)-[:HAS_CONVERSATION]->(:Conversation)`.
- **Deterministic Ordering**: Append messages with auto-incrementing sequence numbers and timestamps (`ORDER BY sequence_number ASC, timestamp ASC, id ASC`).
- **Ticket Linkage**: Support linking messages to tickets via `(:Message)-[:ABOUT]->(:SupportTicket)`.
- **Identity Boundary**: Verifies customer authorization context before message addition or transcript retrieval.

### 5. Troubleshooting Attempts and Resolutions
- **Step Persistence**: Record attempts linked via `(:SupportTicket)-[:HAS_ATTEMPT]->(:TroubleshootingStep)`.
- **Follow-up Chaining**: Connect sequential attempts via `(:TroubleshootingStep)-[:FOLLOWED_BY]->(:TroubleshootingStep)` within the same ticket context.
- **Resolution Persistence**: Idempotently record resolutions via `(:SupportTicket)-[:HAS_RESOLUTION]->(:Resolution)`.

---

## 🤖 Context-Aware AI Support Agent (Phase 5)

Phase 5 builds on Phases 1–4 by providing an enterprise AI support agent capable of reasoning over retrieved Neo4j knowledge graphs, running authorized database tools within safe boundaries, persisting conversation transcripts, and presenting a conversational interface in Streamlit.

### 1. Agent Architecture & Request Lifecycle
```
User Message
     │
     ▼
[ 1. Validate Customer & Input ]  ──> Enforce non-empty string, length bounds, identity check
     │
     ▼
[ 2. Retrieve Graph Memory ]       ──> HistoryRetriever (ranked tickets, products, failed steps)
     │
     ▼
[ 3. Assemble Prompt & Context ]   ──> BASE_SYSTEM_INSTRUCTIONS + formatted evidence + history
     │
     ▼
[ 4. Configurable LLM Provider ]   ──> Google Gemini / OpenAI / Mock with timeouts & retry guards
     │
     ├── Tool Calls Requested?
     │         │
     │         ▼
     │   [ 5. Tool Registry ]     ──> Authorize customer ID, execute approved tools (max 4 iters)
     │         │
     │         └── Loop back to LLM with tool output
     │
     ▼
[ 6. Response Validation ]        ──> Detect hallucinated claims, sanitize leaks, verify status
     │
     ▼
[ 7. Conversation Persistence ]   ──> Atomic storage of user & assistant turns in Neo4j
     │
     ▼
Response to UI / Caller
```

### 2. Configurable LLM Providers (`graphsupport.agents.provider`)
Supported providers selectable via typed settings:
- **`google` / `gemini`**: Direct Google Gemini API integration using models like `gemini-2.0-flash` or `gemini-1.5-pro`.
- **`openai`**: OpenAI-compatible REST API integration using models like `gpt-4o-mini` or `gpt-4o`.
- **`sarvam`**: Sarvam AI Indian LLM provider (`sarvam-105b`, `sarvam-2b`) with multilingual support and dual-header authentication (`api-subscription-key` & Bearer).
- **`mock`**: In-memory test provider for unit tests, offline development, and deterministic simulation.

Environment variables in `.env`:
```bash
# Standard Provider
LLM_PROVIDER=google          # Options: google, openai, sarvam, mock
LLM_MODEL=gemini-2.0-flash   # Model identifier
LLM_API_KEY=<your-api-key>   # Secret key (never logged, masked in diagnostics)

# Sarvam AI (Indian LLM & Multilingual)
SARVAM_API_KEY=<your-sarvam-key>
SARVAM_MODEL=sarvam-105b     # Options: sarvam-105b, sarvam-2b
SARVAM_BASE_URL=https://api.sarvam.ai/v1

# LangSmith Observability & Tracing
LANGSMITH_TRACING=true       # Enable full agent run tree tracing
LANGSMITH_API_KEY=<your-lsv2-key>
LANGSMITH_PROJECT=graphsupport-ai
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
```

### 2b. LangSmith Tracing & Observability (`graphsupport.core.tracing`)
- **Zero-overhead fail-safe design**: Operates in fast, zero-overhead no-op mode when `LANGSMITH_TRACING=false` or credentials are unset.
- **Hierarchical Run Trees**: Traces root agent turns (`chain`), child tool executions (`tool`), and LLM provider generations (`llm`).
- **Telemetry & Safety**: Records prompt tokens, response latency, tool parameters, error states, and execution duration while automatically masking sensitive customer data and credentials.

### 3. Approved Domain Tools (`graphsupport.agents.tool_registry`)
All tools are strictly sandboxed and bound to the authenticated customer's boundary:
| Tool Name | Operation | Purpose |
|---|---|---|
| `get_customer_history` | Read | Retrieve recent tickets, products, diagnostic steps, and resolutions |
| `get_ticket_status` | Read | Check ticket status, title, and priority (enforces ownership) |
| `get_product_info` | Read | Look up catalog products by name or SKU |
| `record_troubleshooting_attempt` | Write | Log diagnostic action and outcome (`failed`, `success`, `partial`, `unknown`) |
| `create_support_ticket` | Write | Atomically open support ticket linked to customer, product, and issue |
| `update_ticket_status` | Write | Transition ticket lifecycle status (`open`, `in_progress`, `resolved`, `closed`) |
| `escalate_ticket` | Write | Record escalation attempt to Tier 2 support |

*Safety rule*: The agent cannot run arbitrary code, shell commands, raw Cypher, or query other customers' tickets.

### 4. Memory Grounding & Anti-Hallucination Directives
- **Factual Evidence Only**: Retrieved graph facts are treated strictly as evidence. Missing records cannot be fabricated.
- **Outcome Fidelity**: If a troubleshooting step failed in a previous session, the agent is instructed not to repeat it without technical justification and to acknowledge the prior attempt.
- **Verification Before Claims**: The agent is forbidden from claiming an action succeeded unless verified by a tool return.
- **Prompt Injection Defense**: Customer inputs and stored history are treated as untrusted data blocks. System directives cannot be overridden by user messages.

---

## 🚀 Quickstart Guide

### 1. Prerequisites
- Python 3.10+ (Python 3.12 recommended)
- macOS Monterey 12.0+ or Linux
- Neo4j 5.x or Neo4j AuraDB instance

### 2. Virtual Environment Setup
```bash
# Clone and enter directory
cd graphsupport-ai

# Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate

# Upgrade pip and install package with development tooling
pip install --upgrade pip
pip install -r requirements-dev.txt
pip install -e .
```

### 3. Configure Local Settings
```bash
# Copy example configuration template
cp .env.example .env
```
Fill in your Neo4j credentials in `.env`:
```bash
NEO4J_URI=neo4j+s://<instance-id>.databases.neo4j.io
NEO4J_USERNAME=<username>
NEO4J_PASSWORD=<password>
NEO4J_DATABASE=<database>
```
*(Never commit `.env` to Git; it is strictly ignored).*

### 4. Run Environment Diagnostics
```bash
python scripts/check_environment.py
```

### 5. Launch the Streamlit Dashboard
```bash
streamlit run app.py
```
Open your browser at `http://localhost:8501` to access the 10-page operations dashboard.

---

## 🖥️ GraphSupport AI Support Dashboard (Phase 6)

Phase 6 provides a professional, operations-grade Streamlit dashboard structured into 10 dedicated pages:

1. **Overview**: Real-time KPI telemetry (Customers, Tickets, Open/In-Progress/Resolved counts), ticket status distribution, recent diagnostic attempts, verified resolutions, and manual telemetry refresh.
2. **Support Chat**: Interactive AI support assistant integrating the Phase 5 `SupportAgent`. Enforces customer memory grounding, shows active tool call telemetry, and provides session reset controls.
3. **Customers**: Customer directory with ID search, Customer 360 overview (linked products, ticket history, conversation sessions), and validated customer onboarding.
4. **Products**: Complete product catalog, SKU inspection, and customer-product relationship linkage forms.
5. **Tickets**: Support ticket queue with status filtering (`open`, `in_progress`, `resolved`, `closed`), keyword search, and ticket opening workflow.
6. **Ticket Details**: Deep diagnostic view featuring customer & product context, troubleshooting attempt timeline with outcome badges (`SUCCESS`, `FAILED`, `PARTIAL`, `UNKNOWN`), verified resolution cards, diagnostic attempt logging, and validated status lifecycle transitions.
7. **Conversation History**: Multi-session audit log with conversation selector, chronological message stream, sender badges (`CUSTOMER`, `AGENT`), and ticket links.
8. **Graph Explorer**: Safe, read-only graph visualizer using interactive vis.js physics layout. Features color-coded node taxonomy (Customer, Product, Ticket, Step, Resolution), bounded queries (10–60 nodes), and tabular fallback.
9. **System Health**: Subsystem readiness auditing, explicit live Neo4j connectivity checks, idempotent schema initializers, and sanitized AI provider configurations.
10. **Evaluation**: Offline benchmark runner evaluating memory grounding, outcome fidelity, tool safety, claim verification, prompt injection defense, and retrieval latency (consumes 0 paid LLM tokens).

---

---

## 🚀 Phase 8: Final Evaluation, E2E Demo & Hackathon Readiness

Phase 8 finalizes the platform for production evaluation, automated benchmarks, and hackathon demonstrations. For full presentation materials and the slide deck guide, see [docs/HACKATHON_DEMO.md](file:///Users/MukeshSingh/Desktop/graphsupport-ai/docs/HACKATHON_DEMO.md).

### 1. Two-Conversation Reproducible Demo Scenario
Demonstrates why persistent graph memory solves session amnesia:
- **Conversation 1**: Customer Sarah Chen (`demo-cust-sarah`) reports login failure on SmartMesh Gateway Pro (`SM-GW-PRO`). Ticket `demo-tkt-101` is opened and an automated password reset link is attempted, which **fails** (HTTP 401 token expiration). Issue remains open.
- **Conversation 2**: Sarah returns in a separate session saying: *"My account still isn't working."* The system retrieves the previous ticket and failed attempt from Neo4j memory, acknowledges the prior failure, and suggests higher-tier authentication diagnostics without repeating the failed step.

```bash
# Seed the demo scenario into Neo4j:
python scripts/seed_demo.py

# Check status:
python scripts/seed_demo.py --status

# Safely reset demo records only (deletes only nodes starting with 'demo-'):
python scripts/seed_demo.py --reset
```

### 2. Deterministic 9-Vector Evaluation Suite
Zero paid LLM tokens consumed. Evaluates the 9 core pillars:
1. **Context Retrieval Relevance & Ticket Ranking** (Open tickets prioritized over closed)
2. **Diagnostic Outcome Fidelity** (Failed steps preserved as `failed` with diagnostic warning flags)
3. **Ticket Lifecycle Transitions** (`open` ➔ `in_progress` ➔ `resolved` ➔ `closed`)
4. **Groundedness & Anti-Hallucination** (`OutputParser` detects claims without tool evidence)
5. **Customer Data Isolation** (`ToolRegistry` blocks cross-tenant ticket operations)
6. **Tool Argument Validation** (Cypher injection tokens and invalid entity IDs rejected)
7. **Prompt Injection Defense** (Heuristic scanner flags overrides; system directives isolated)
8. **Resilience & Privacy-Safe Logging** (Database passwords and cards redacted from logs)
9. **Performance Latency** (In-memory context compilation under 5.0ms)

```bash
# Run the 9-vector evaluation benchmark:
python -c "from graphsupport.application.evaluation import EvaluationRunner; import json; print(json.dumps(EvaluationRunner().run_all_evaluations().to_dict(), indent=2))"
```

---

## 🧪 Testing and Quality Assurance

### Run Unit and Integration Tests
```bash
# Run all tests (139 passing unit + live integration tests)
pytest -v

# Run 10-step end-to-end workflow tests (unit + live Neo4j integration)
pytest tests/unit/test_end_to_end_support_flow.py tests/integration/test_end_to_end_support_flow.py -v

# Run Phase 7 security and hardening tests
pytest tests/unit/test_security_hardening.py -v

# Run Phase 6 dashboard unit tests (including 9-vector evaluation benchmark)
pytest tests/unit/test_phase6_dashboard.py -v

# Run Phase 5 Agent unit tests (provider, tools, agent orchestrator)
pytest tests/unit/test_agent_*.py tests/unit/test_support_agent.py -v

# Run Phase 4 graph memory unit tests
pytest tests/unit/test_graph_memory.py -v

# Run all live Neo4j Aura integration tests
pytest tests/integration/ -v
```

---

## 🔒 Security Architecture & Hardening Controls (Phase 7)

For full architectural details, see [docs/security.md](file:///Users/MukeshSingh/Desktop/graphsupport-ai/docs/security.md).

- **Strict Identifier Validation**: All entity IDs are checked against `^[a-zA-Z0-9_\-\.]{1,128}$` via `validate_entity_id()`, rejecting control characters and injection tokens.
- **In-Memory Rate Limiting**: `InMemoryRateLimiter` enforces sliding-window rate limiting per customer session to prevent denial-of-service and quota exhaustion.
- **Prompt Injection Defense-in-Depth**:
  - `scan_for_prompt_injection()` scans user messages for instruction overrides, persona hijacking, and credential harvesting.
  - Isolated system prompt formatting ensures user text cannot alter directives.
  - Output validation fact-checks claims before returning responses.
- **Tool Deduplication & Safety**:
  - `create_support_ticket` checks for existing active tickets with identical titles, preventing duplicate storms during retries.
  - `record_troubleshooting_attempt` avoids duplicate step entries.
  - Ownership validation ensures cross-customer ticket operations are blocked.
- **Sanitized Observability**:
  - Request correlation IDs (`req-*`) track agent workflows across logging and tool executions.
  - Secret and card scrubbing (`redact_sensitive_text()`) masks sensitive tokens.
- **Pre-Production Roadmap**:
  - Before public deployment, enterprise OIDC authentication and distributed Redis rate limiting must replace demo components.

---

## 📄 License

Proprietary — Internal Development.

