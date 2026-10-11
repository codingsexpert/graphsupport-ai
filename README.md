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
| **Phase 4** | **Graph Retrieval & Memory** | *Pending* | Persistent graph memory, customer history retrieval, ticket-context retrieval, relevance ranking |
| **Phase 5** | **Context-Aware LLM Agent** | *Pending* | LLM reasoning engine, prompt orchestration, cross-session memory |
| **Phase 6** | **Interactive Support UI** | *Pending* | Interactive Streamlit portal, chat UI, graph visualizer |

---

## 🕸️ Graph Data Architecture (Phase 3)

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
Open your browser at `http://localhost:8501` to access the Phase 3 Customer Support Workbench.

---

## 🧪 Testing and Quality Assurance

### Run Unit and Integration Tests
```bash
# Run all tests (unit + live integration)
pytest -v

# Run unit tests only (fast, completely mocked)
pytest tests/unit/ -v

# Run live Neo4j integration tests
pytest tests/integration/ -v
```

### Code Style & Formatting
```bash
ruff check .
ruff format --check .
```

---

## 🔒 Security & Authorization Boundaries

- **Parameterization**: 100% of Cypher queries use `$params` without string concatenation or f-string interpolation.
- **Secret Safety**: Passwords, URIs, and tokens are automatically masked by Pydantic Settings and filtered from log outputs.
- **Demo Identity Boundary**: Customer ownership checks are verified in the application layer. Full enterprise authentication (OAuth2/OIDC) is scheduled for subsequent phases.

---

## 📄 License

Proprietary — Internal Development.
