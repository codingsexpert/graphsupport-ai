# GraphSupport AI — Developer Guide

This guide describes local development, environment setup, testing, and verification procedures for **GraphSupport AI**.

---

## 1. Prerequisites

- **Operating System**: macOS Monterey 12.0+ (compatible with Intel x86_64 and Apple Silicon) or modern Linux.
- **Python**: Python 3.12 (Python 3.10+ supported).
- **Git**: Git 2.30+.
- **Hardware**: Designed to run efficiently on 8 GB RAM machines.

---

## 2. Local Environment Setup

### Step A: Clone and navigate to repository
```bash
cd graphsupport-ai
```

### Step B: Create and activate a virtual environment
```bash
# Create isolated Python 3.12 environment
python3.12 -m venv .venv

# Activate environment on macOS / Linux
source .venv/bin/activate
```

### Step C: Install dependencies in editable mode
```bash
# Install runtime and development dependencies
pip install --upgrade pip
pip install -r requirements-dev.txt
pip install -e .
```

### Step D: Setup local configuration
```bash
# Copy example configuration template
cp .env.example .env
```
> **Note**: Do not store real API keys or sensitive passwords in `.env.example`. The `.env` file is ignored by Git.

---

## 3. Environment Verification

Run the automated diagnostic check to ensure all dependencies and system configurations are operational:

```bash
python scripts/check_environment.py
```

Expected output:
```text
========================================================================
 GraphSupport AI — Environment Diagnostics
 Platform: Darwin x86_64 (...)
========================================================================
[✓] Python Version            : PASS  - Detected Python 3.12.x
[✓] Virtual Environment       : PASS  - Active Prefix: .../.venv
[✓] Git Repository            : PASS  - Active Branch: 'main'
[✓] Package: pydantic         : PASS  - Version: 2.14.0
[✓] Package: pydantic-settings: PASS  - Version: 2.15.0
[✓] Package: streamlit        : PASS  - Version: 1.65.0
[✓] Package: pytest           : PASS  - Version: 9.1.1
[✓] Package: ruff             : PASS  - Version: 0.17.0
[✓] GraphSupport Core         : PASS  - Health: healthy, Phase: Phase 1
========================================================================
RESULT: All environment checks PASSED successfully.
```

---

## 4. Running Automated Tests

Run the complete test suite with `pytest`:

```bash
# Run all unit and integration tests
pytest

# Run with verbose output and coverage
pytest -v
```

---

## 5. Code Quality & Formatting

We use **Ruff** for fast linting and formatting:

```bash
# Check for lint errors
ruff check .

# Automatically apply safe fixes
ruff check . --fix

# Verify code formatting
ruff format --check .

# Apply formatting
ruff format .
```

---

## 6. Running the Streamlit Application

Start the Phase 1 dashboard:

```bash
streamlit run app.py
```

Streamlit will launch locally at `http://localhost:8501`.
- The dashboard displays application health, environment metrics, safe configuration, and the upcoming roadmap.
- The UI transparently indicates that Neo4j and LLM integrations are scheduled for subsequent phases.
