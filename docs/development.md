# GraphSupport AI — Developer Guide

This guide describes local development, environment setup, testing, Neo4j configuration, and verification procedures for **GraphSupport AI**.

---

## 1. Prerequisites

- **Operating System**: macOS Monterey 12.0+ (compatible with Intel x86_64 and Apple Silicon) or modern Linux.
- **Python**: Python 3.12 (Python 3.10+ supported).
- **Git**: Git 2.30+.
- **Database**: Neo4j 5.x or Neo4j AuraDB instance.

---

## 2. Local Environment Setup

### Step A: Clone and navigate to repository
```bash
cd graphsupport-ai
```

### Step B: Create and activate a virtual environment
```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

### Step C: Install dependencies in editable mode
```bash
pip install --upgrade pip
pip install -r requirements-dev.txt
pip install -e .
```

### Step D: Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Configure your Neo4j settings in `.env`:
```bash
NEO4J_URI=neo4j+s://<instance-id>.databases.neo4j.io
NEO4J_USERNAME=<username>
NEO4J_PASSWORD=<password>
NEO4J_DATABASE=<database-or-instance-id>
```
> **Security Note**: Never commit `.env` to Git. The `.gitignore` file automatically excludes it.

---

## 3. Environment Verification & Diagnostics

Run the automated diagnostic check:

```bash
python scripts/check_environment.py
```

This verifies:
- Python version (>= 3.10)
- Active virtual environment
- Git repository state
- Required dependencies (`pydantic`, `streamlit`, `neo4j`, `pytest`, `ruff`)
- Core application health
- Live Neo4j connection (if configured)

---

## 4. Running Automated Tests

### Run All Tests (Unit + Integration)
```bash
pytest -v
```

### Run Unit Tests Only (No Network Access Required)
All unit tests run against in-memory mocks without network dependencies:
```bash
pytest tests/unit/ -v
```
Includes:
- `test_phase6_dashboard.py`: Navigation options, offline evaluation benchmark suite, delegation tests.
- `test_agent_provider.py`: LLM provider authentication, timeouts, rate limits, model failure handling.
- `test_agent_tools.py`: Tool registry allowlisting, input validation, customer authorization checks.
- `test_support_agent.py`: Agent orchestrator workflow, memory grounding, tool loops, anti-hallucination.
- `test_graph_memory.py`: Relevance ranking and context builder.
- `test_phase3_repositories.py`: Parameterized repository tests for Customer, Product, Ticket, Conversation, Troubleshooting.
- `test_support_service.py`: Business workflow, validation, and authorization boundary tests.

### Run Live Neo4j Integration Tests
Live tests target your configured Neo4j instance, test connectivity, and run full end-to-end workflows with isolated prefixes (`test-phase3-*`, `test-phase4-*`, `test-phase5-*`) and guaranteed cleanup:
```bash
pytest tests/integration/ -v
```
Includes:
- `test_phase6_live.py`: Tests live Overview metrics, Subgraph extraction, and live evaluation execution against Neo4j Aura.
- `test_phase5_agent_live.py`: Tests complete agent request lifecycle against live Neo4j Aura.
*(If Neo4j is unconfigured or unreachable, integration tests skip automatically with clear messaging).*

---

## 5. Schema Initialization and Persistence Verification

Schema constraints and indexes are idempotent and use `IF NOT EXISTS` clauses:

### Via Python
```python
from graphsupport.config import get_settings
from graphsupport.graph.driver import get_driver_manager
from graphsupport.graph.schema import initialize_schema

settings = get_settings()
dm = get_driver_manager(settings=settings)
report = initialize_schema(dm.get_driver(), database=settings.neo4j_database)
print(f"Applied {report.succeeded}/{report.total} schema statements.")
```

### Via Streamlit UI
1. Launch `streamlit run app.py`.
2. Navigate to **System Health** in the sidebar.
3. Click **⚡ Apply Schema Constraints & Indexes**.
4. Explore the 10 operations pages (Overview, Support Chat, Customers, Products, Tickets, Ticket Details, Conversation History, Graph Explorer, System Health, Evaluation).

---

## 6. Code Quality & Formatting

```bash
# Check code style with Ruff
ruff check .

# Check formatting
ruff format --check .

# Apply formatting
ruff format .
```
