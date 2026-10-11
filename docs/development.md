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
```bash
pytest tests/unit/ -v
```

### Run Live Neo4j Integration Tests
Live tests target your configured Neo4j instance, test connectivity, apply schema, upsert a test customer with prefix `test-phase2-<uuid>`, and delete the test record immediately after:

```bash
pytest tests/integration/test_neo4j_live.py -v
```
*(If Neo4j is unconfigured or unreachable, integration tests skip automatically).*

---

## 5. Explicit Schema Initialization

Schema constraints and indexes are not automatically applied at startup to prevent unintended modifications. To explicitly initialize the graph schema:

### Via Python Script / Shell
```python
from graphsupport.config import get_settings
from graphsupport.graph.driver import get_driver_manager
from graphsupport.graph.schema import initialize_schema

settings = get_settings()
dm = get_driver_manager(settings=settings)
report = initialize_schema(dm.get_driver(), database=settings.neo4j_database)
print(f"Applied {report.succeeded}/{report.total} statements.")
```

### Via Streamlit UI
1. Launch `streamlit run app.py`.
2. Locate the **Neo4j Database Operations (Phase 2)** control panel.
3. Click **⚡ Initialize Graph Schema (Idempotent)**.

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
