# GraphSupport AI

> **Context-Aware Customer Support Agent Powered by Neo4j Knowledge Graphs & LLM Reasoning**

GraphSupport AI is an enterprise customer support platform designed to remember customers, devices, tickets, troubleshooting attempts, and verified resolutions across sessions using a connected Neo4j knowledge graph.

---

## 📌 Implementation Status

| Phase | Milestone | Status | Details |
|---|---|---|---|
| **Phase 1** | **Professional Foundation** | **Completed** | Modular Python package, typed configuration, logging, health check, UI scaffold, automated tests |
| **Phase 2** | Neo4j Schema & Storage | *Upcoming* | Neo4j driver connection, constraints, indexes, repositories, transaction handling |
| **Phase 3** | Knowledge & Ticket Ingestion | *Pending* | Customer and ticket data pipelines, resolution mapping |
| **Phase 4** | Graph Retrieval & Algorithms | *Pending* | Subgraph extraction, pathfinding, similarity matching |
| **Phase 5** | Context-Aware LLM Agent | *Pending* | LangChain/LlamaIndex reasoning, cross-session memory |
| **Phase 6** | Interactive Support UI | *Pending* | Interactive Streamlit portal, ticket manager, graph visualizer |

---

## 🚀 Quickstart Guide

### 1. Prerequisites
- Python 3.10+ (Python 3.12 recommended)
- macOS Monterey 12.0+ or Linux
- Git

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
*(No external database or API key is required to run Phase 1).*

### 4. Run Environment Diagnostics
```bash
python scripts/check_environment.py
```

### 5. Launch the Streamlit Dashboard
```bash
streamlit run app.py
```
Open your browser at `http://localhost:8501` to view the Phase 1 system status and architecture dashboard.

---

## 🧪 Testing and Quality Assurance

### Run Automated Tests
```bash
# Execute unit and integration tests
pytest
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
        exceptions.py            # Centralized exception hierarchy
        logging_config.py        # Structured logging with secret sanitization
        health.py                # Health inspection & phase readiness
      ui/                        # Streamlit UI design system & components
        __init__.py
        navigation.py            # Sidebar and navigation controls
        components.py            # Reusable UI cards, metrics, and roadmap
        styles.py                # Custom modern CSS styling
  tests/
    unit/
      test_settings.py           # Configuration and secret protection tests
      test_health.py             # Health readiness tests
      test_logging_config.py     # Logging formatting and idempotence tests
    integration/
      test_application_startup.py# Application startup & import integration tests
  docs/
    architecture.md              # System design and component boundaries
    development.md               # Developer setup and troubleshooting guide
  scripts/
    check_environment.py         # Automated local environment diagnostic tool
```

---

## 🔒 Security & Secret Isolation

- Secrets (such as `NEO4J_PASSWORD` and `LLM_API_KEY`) are encapsulated in Pydantic's `SecretStr`.
- Plaintext secrets are never emitted in string representations, JSON dumps, log messages, or UI cards.
- The `.env` file is excluded from version control.
- Tests use isolated configurations and never depend on or overwrite live credentials.
