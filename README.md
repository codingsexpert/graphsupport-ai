# GraphSupport AI

> **Context-Aware Customer Support Agent Powered by Neo4j Knowledge Graphs & LLM Reasoning**

GraphSupport AI is an enterprise customer support platform designed to remember customers, devices, tickets, troubleshooting attempts, and verified resolutions across sessions using a connected Neo4j knowledge graph.

---

## 📌 Implementation Status

| Phase | Milestone | Status | Details |
|---|---|---|---|
| **Phase 1** | **Professional Foundation** | **Completed** | Modular Python package, typed configuration, logging, health check, UI scaffold, automated tests |
| **Phase 2** | **Neo4j Schema & Storage** | **Completed** | Neo4j driver connection pooling, graph models, uniqueness constraints, indexes, customer repository |
| **Phase 3** | Knowledge & Ticket Ingestion | *Upcoming* | Customer and ticket data pipelines, historical troubleshooting ingestion |
| **Phase 4** | Graph Retrieval & Algorithms | *Pending* | Multi-hop traversal, subgraph extraction, shortest-path troubleshooting |
| **Phase 5** | Context-Aware LLM Agent | *Pending* | LLM reasoning engine, prompt orchestration, cross-session memory |
| **Phase 6** | Interactive Support UI | *Pending* | Interactive Streamlit portal, ticket manager, graph visualizer |

---

## 🕸️ Graph Model Architecture (Phase 2)

### Node Entities
- `Customer`: Unique customer identity (`id` UUID, `email` UNIQUE, `name`, `tier`).
- `Product`: Catalog products and hardware devices (`id` UUID, `name`, `sku` INDEXED).
- `Issue`: Canonical defects and symptom classification (`id` UUID, `title`, `severity`).
- `SupportTicket`: Customer support tickets (`id` UUID, `title`, `status` INDEXED, `priority`).
- `Conversation`: Support session context (`id` UUID, `session_id`, `channel`).
- `Message`: Transcript entry (`id` UUID, `sender_type`, `content`, `timestamp`).
- `TroubleshootingStep`: Diagnostic actions (`id` UUID, `step_number`, `action`, `outcome`).
- `Resolution`: Verified solutions (`id` UUID, `summary`, `resolution_type`, `verified`).

### Graph Relationships
```
(Customer)-[:USES]->(Product)
(Customer)-[:HAS_TICKET]->(SupportTicket)
(Product)-[:HAS_ISSUE]->(Issue)
(Issue)-[:TRACKED_BY]->(SupportTicket)
(SupportTicket)-[:HAS_RESOLUTION]->(Resolution)
(SupportTicket)-[:HAS_ATTEMPT]->(TroubleshootingStep)
(Customer)-[:HAS_CONVERSATION]->(Conversation)
(Conversation)-[:CONTAINS]->(Message)
(Message)-[:ABOUT]->(SupportTicket)
(TroubleshootingStep)-[:FOLLOWED_BY]->(TroubleshootingStep)
```

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
Open your browser at `http://localhost:8501` to view the Phase 2 system status and database control panel.

---

## 🧪 Testing and Quality Assurance

### Run All Automated Tests (Unit + Integration)
```bash
pytest -v
```

### Run Unit Tests Only (Mocks Only, Zero Network Calls)
```bash
pytest tests/unit/ -v
```

### Run Linter and Formatter
```bash
# Check code style and rules
ruff check .

# Verify code formatting
ruff format --check .
```

---

## 📂 Project Structure

```
graphsupport-ai/
  app.py                         # Streamlit application entrypoint
  README.md                      # Project documentation and quickstart
  pyproject.toml                 # Package metadata and tool configurations
  requirements.txt               # Pinned runtime dependencies
  requirements-dev.txt           # Development and testing dependencies
  .env.example                   # Non-sensitive configuration template
  .gitignore                     # Git ignore rules for virtualenvs, caches, secrets
  .python-version                # Pinned Python version (3.12)
  src/
    graphsupport/
      __init__.py
      config/                    # Typed Pydantic Settings & validation
        __init__.py
        settings.py
      core/                      # Core foundation components
        __init__.py
        exceptions.py            # Centralized exception hierarchy (incl. DatabaseError)
        logging_config.py        # Structured logging with secret sanitization
        health.py                # Health inspection & reachability reporting
      graph/                     # Neo4j graph persistence & models (Phase 2)
        __init__.py
        models.py                # Pydantic graph models & enums
        driver.py                # Safe Neo4j connection pooling & TLS manager
        schema.py                # Idempotent schema constraints & index DDL
        repository.py            # Parameterized Cypher customer repository
        queries/
          schema.cypher          # Readable Cypher schema definition file
      ui/                        # Streamlit UI design system & components
        __init__.py
        navigation.py            # Sidebar and navigation controls
        components.py            # Reusable UI cards, metrics, and DB control panel
        styles.py                # Custom modern CSS styling
  tests/
    unit/
      test_settings.py           # Configuration tests
      test_health.py             # Health readiness tests
      test_logging_config.py     # Logging formatting tests
      test_graph_models.py       # Domain entity models & enum tests
      test_graph_driver.py       # Driver connection pooling & error tests
      test_graph_schema.py       # Schema DDL initialization tests
      test_graph_repository.py   # Customer repository CRUD tests
    integration/
      test_application_startup.py# Startup & import integration tests
      test_neo4j_live.py         # Live AuraDB connectivity & isolated CRUD tests
  docs/
    architecture.md              # System design and component boundaries
    development.md               # Developer setup and troubleshooting guide
  scripts/
    check_environment.py         # Automated local environment diagnostic tool
```
