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
| **Phase 6** | **Interactive Support UI** | *Pending* | Interactive Streamlit portal, ticket views, conversation history, graph visualizer, evaluation interface |

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
- **`google` / `gemini`**: Direct Google Gemini API integration using models like `gemini-1.5-flash` or `gemini-1.5-pro`.
- **`openai`**: OpenAI-compatible REST API integration using models like `gpt-4o-mini` or `gpt-4o`.
- **`mock`**: In-memory test provider for unit tests, offline development, and deterministic simulation.

Environment variables in `.env`:
```bash
LLM_PROVIDER=google          # Options: google, openai, mock
LLM_MODEL=gemini-1.5-flash   # Model identifier
LLM_API_KEY=<your-api-key>   # Secret key (never logged, masked in diagnostics)
LLM_TIMEOUT_SECONDS=30.0     # HTTP request timeout
```

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
Open your browser at `http://localhost:8501` to access the Phase 4 Memory Inspector and Phase 3 Workbench.

---

## 🧪 Testing and Quality Assurance

### Run Unit and Integration Tests
```bash
# Run all tests (all 101 unit + live integration tests)
pytest -v

# Run Phase 5 Agent unit tests (provider, tools, agent orchestrator)
pytest tests/unit/test_agent_*.py tests/unit/test_support_agent.py -v

# Run Phase 4 graph memory unit tests
pytest tests/unit/test_graph_memory.py -v

# Run Phase 5 live agent integration test against Neo4j Aura
pytest tests/integration/test_phase5_agent_live.py -v

# Run all live Neo4j integration tests
pytest tests/integration/ -v
```

### Reproducing Cross-Session Persistence Demo
To verify that history survives across application sessions:
1. In the Streamlit UI (or via `SupportService`), register a customer and a product.
2. Open a ticket for that product (e.g. "WiFi dropping connection").
3. Record a troubleshooting attempt with outcome `failed` (e.g. "Factory Reset" -> `FAILED`).
4. Terminate the Streamlit server or start a new python session (`del service; service = SupportService()`).
5. Open the **Phase 4: Persistent Graph Memory Inspector** section in the UI or run `service.retrieve_customer_context(customer_id)`.
6. Verify that the previous ticket, product linkage, and the failed troubleshooting attempt are retrieved intact from Neo4j.
7. Verify that the failed attempt remains marked as `🔴 FAILED` with diagnostic flags preserved.
8. Ask the AI Support Agent about the issue; note that it acknowledges the failed attempt and avoids suggesting it again!

---

## 🔒 Security & Authorization Boundaries

- **Parameterization**: 100% of Cypher queries use `$params` without string concatenation or f-string interpolation.
- **Secret Safety**: Passwords, URIs, and API keys are automatically masked by Pydantic Settings and filtered from log outputs.
- **Tenant Ownership Validation**: Customer-to-ticket ownership is verified before context assembly and before any tool action. Cross-customer manipulation is blocked at application runtime.
- **Bounded Loops**: Agent tool loops are strictly capped at 4 iterations with maximum context limits.
- **Untrusted Input Treatment**: User messages and database strings cannot alter system prompt instructions.

---

## 🔮 Scope Boundaries & Deferred Features (Phase 6)

Phase 5 completes the context-aware AI support agent and tool execution layer. The following features are intentionally scheduled for Phase 6:
- **Polished Streamlit Support Dashboard**: Dedicated ticket views, live analytics, and filtering.
- **Interactive Graph Explorer**: Visual rendering of customer-ticket-attempt subgraphs.
- **Agent Evaluation Interface**: Systematic benchmark suite for diagnostic accuracy and hallucination rates.

---

## 📄 License

Proprietary — Internal Development.

