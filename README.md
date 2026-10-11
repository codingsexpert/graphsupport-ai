# ⚡ GraphSupport AI

<p align="center">
  <strong>Enterprise Context-Aware Customer Support Engine Powered by Neo4j Property Graphs, Sarvam AI & LangSmith</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.12" />
  <img src="https://img.shields.io/badge/Graph_Database-Neo4j_AuraDB-008CC1?style=flat-square&logo=neo4j&logoColor=white" alt="Neo4j AuraDB" />
  <img src="https://img.shields.io/badge/LLM_Provider-Sarvam_AI_%7C_Gemini-FF6F00?style=flat-square" alt="Sarvam AI" />
  <img src="https://img.shields.io/badge/Observability-LangSmith-1C3C3C?style=flat-square&logo=langchain&logoColor=white" alt="LangSmith" />
  <img src="https://img.shields.io/badge/UI_Dashboard-Streamlit-FF4B4B?style=flat-square&logo=streamlit&logoColor=white" alt="Streamlit" />
  <img src="https://img.shields.io/badge/Tests-157_Passed_(100%25)-success?style=flat-square" alt="Tests" />
  <img src="https://img.shields.io/badge/Code_Style-Ruff-black?style=flat-square" alt="Ruff" />
</p>

---

## 💡 The Core Problem: Why Traditional Support Bots Fail

Traditional customer support chatbots and basic RAG (Retrieval-Augmented Generation) architectures suffer from **session amnesia**:
- ❌ **They forget previous attempts:** If a user returns 10 minutes later, the bot asks them to repeat the exact same troubleshooting step (e.g., *"Have you tried restarting?"* or *"Please click the password reset link"*).
- ❌ **Flat Vector DBs lack multi-hop relationships:** Vector embeddings compare text similarities, but they cannot inherently trace:  
  `Customer` ➔ *OWNS* ➔ `Hardware Product` ➔ *TRACKS* ➔ `Active Ticket` ➔ *RECORDED* ➔ `Failed Diagnostic Step`.
- ❌ **Hallucinated resolutions:** Bots often claim they "fixed" or "escalated" an issue without verifiable database state mutations.

### ✨ How GraphSupport AI Solves This

**GraphSupport AI** replaces flat vector retrieval with a **Neo4j Property Graph** combined with **Sarvam AI's reasoning engine** and **LangSmith tracing**:

| Traditional AI Support Bot | ⚡ GraphSupport AI |
|---|---|
| Treats every chat session in isolation | Recalls past conversations, tickets, and owned devices across sessions |
| Repeats failed troubleshooting steps | Strict **Outcome Fidelity**: Recognizes `FAILED` steps and advances to the next technical tier |
| No concept of entity ownership | Strict **Tenant Isolation**: Validates customer boundaries before running any tool |
| Black-box unstructured memory | Deterministic, explainable graph traversal (`HAS_TICKET`, `AFFECTS`, `HAS_ATTEMPT`, `CONTAINS`) |
| Unmonitored LLM generation | Full end-to-end tracing on **LangSmith** with token, latency, and tool telemetry |

---

## 🏗️ System Architecture

```
                  ┌──────────────────────────────────────────────┐
                  │          Streamlit Operations UI             │
                  │ (Overview • Chat • Graph Explorer • Tickets) │
                  └──────────────────────┬───────────────────────┘
                                         │
                                         ▼
                  ┌──────────────────────────────────────────────┐
                  │       Context-Aware Support Agent            │
                  │   (Safety Guards • Strict Prompt Boundary)   │
                  └──────────────┬───────────────┬───────────────┘
                                 │               │
        ┌────────────────────────┘               └────────────────────────┐
        ▼                                                                 ▼
┌───────────────────────────────┐                               ┌───────────────────────────────┐
│     Neo4j Graph Memory        │                               │       AI Reasoning Core       │
│  - Parameterized Cypher       │                               │  - Sarvam AI (sarvam-105b)    │
│  - Multi-hop Traversal        │                               │  - Google Gemini / OpenAI     │
│  - Deterministic Ranker       │                               │  - Sandboxed Domain Tools     │
└──────────────┬────────────────┘                               └───────────────┬───────────────┘
               │                                                                │
               └────────────────────────┬───────────────────────────────────────┘
                                        │
                                        ▼
                  ┌──────────────────────────────────────────────┐
                  │         LangSmith Observability              │
                  │  (Hierarchical Run Trees • Latency • Logs)   │
                  └──────────────────────────────────────────────┘
```

---

## 🕸️ Knowledge Graph Topology

The system models customer support as a fully typed, connected property graph in **Neo4j**:

```
(:Customer) ──[:USES]───────────────► (:Product)
    │                                     │
    │                                     ▼
    ├──[:HAS_TICKET]────────────────► (:SupportTicket) ──[:AFFECTS]──► (:Product)
    │                                     │
    │                                     ├──[:HAS_ATTEMPT]────► (:TroubleshootingStep)
    │                                     │                           │
    │                                     │                           └──[:FOLLOWED_BY]──► (:TroubleshootingStep)
    │                                     └──[:HAS_RESOLUTION]─► (:Resolution)
    │
    └──[:HAS_CONVERSATION]──────────► (:Conversation)
                                          │
                                          └──[:CONTAINS]───────► (:Message) ──[:ABOUT]──► (:SupportTicket)
```

### Graph Entities & Constraints
- **`Customer`**: Unique identity (`id`, `email` [UNIQUE], `name`, `tier`, `created_at`).
- **`Product`**: Hardware products & SaaS catalog (`id`, `name`, `sku` [INDEXED], `version`).
- **`SupportTicket`**: Support lifecycle cases (`id`, `title`, `status` [INDEXED], `priority`).
- **`TroubleshootingStep`**: Diagnostic attempts with immutable outcome (`action`, `outcome`: `SUCCESS` | `FAILED` | `PARTIAL` | `UNKNOWN`).
- **`Resolution`**: Verified technical fixes (`summary`, `resolution_type`, `verified`).
- **`Conversation` & `Message`**: Chronological support transcripts with strict sequence ordering.

---

## 🎯 Reproducible Hackathon Demo: The Sarah Chen Story

GraphSupport AI comes with a **1-click seed scenario** specifically designed to showcase graph memory in action:

1. **The Scenario:**
   - **Customer:** Sarah Chen (`demo-cust-sarah`), Enterprise Tier.
   - **Product:** SmartMesh Home Gateway Pro (`SM-GW-PRO`).
   - **Issue:** Cloud portal login returns HTTP 401 Unauthorized.
   - **Active Ticket:** `demo-tkt-101` (Priority: High, Status: `OPEN`).
   - **Past Attempt:** Dispatched automated password reset link ➔ **Outcome: `FAILED`** (Token expired immediately).

2. **The Test in `Support Chat`:**
   Ask the AI:
   ```text
   Hi, I still cannot log in to my SmartMesh cloud portal. What should I do next?
   ```

3. **The Wow Factor:**
   - **Standard Bot Response:** *"Have you checked your email for the password reset link?"* (Fails the customer).
   - **GraphSupport AI Response:** *"I see that you have an open ticket regarding portal login, and our automated password reset attempt previously **failed with an HTTP 401 error**. Rather than repeating that step, let's examine your session cache and token issuance..."*

4. **Resolving the Case:**
   Send the follow-up:
   ```text
   The admin cleared my cloud session token and I can log in now! Please resolve my ticket.
   ```
   The AI invokes its authorized database tools, transitions `demo-tkt-101` from `OPEN` to **`RESOLVED`**, logs a verified resolution, and records the transcript in Neo4j.

---

## 🖥️ 10-Page Operations Dashboard

The Streamlit dashboard (`app.py`) provides an enterprise-ready interface:

| Page | Description |
|---|---|
| **Overview** | Real-time graph telemetry (Customer, Product, Ticket KPIs), recent activity cards, and 1-click Demo Scenario loader. |
| **Support Chat** | Context-aware AI assistant powered by Sarvam AI / Gemini, with live tool execution and conversation memory. |
| **Customers** | Customer directory with search, Customer 360 overview (linked products, ticket history, conversation sessions). |
| **Products** | Hardware & SaaS product catalog, SKU inspection, and customer-device linkage forms. |
| **Tickets** | Support ticket queue with multi-filter status search (`OPEN`, `IN_PROGRESS`, `RESOLVED`, `CLOSED`). |
| **Ticket Details** | 360-degree timeline view of diagnostic steps, outcome badges, verified resolutions, and status transition controls. |
| **Conversation History** | Multi-session audit transcripts with chronological message order and ticket references. |
| **Graph Explorer** | Interactive vis.js physics visualizer with color-coded nodes, drag-and-drop graph exploration, and tabular fallback. |
| **System Health** | Infrastructure diagnostics, live Neo4j Aura connection verification, and masked configuration audits. |
| **Evaluation** | Offline deterministic benchmark suite running 9 evaluation vectors (consumes 0 paid LLM tokens). |

---

## 🛡️ Enterprise Security & Hardening Controls

- **Strict Identifier Validation:** All entity IDs are validated against `^[a-zA-Z0-9_\-\.]{1,128}$`, preventing Cypher injection and malformed inputs.
- **Tenant Data Isolation:** The agent boundary enforces that users cannot inspect or mutate tickets belonging to other customers (`AuthorizationError`).
- **Prompt Injection Defense:** Heuristic scanners flag prompt override attempts (`IGNORE PREVIOUS INSTRUCTIONS`), and system instructions remain strictly isolated.
- **Tool Boundary Enforcement:** The agent cannot execute raw shell commands, execute arbitrary Cypher, or query external networks.
- **Credential Scrubbing:** Real API keys (`NEO4J_PASSWORD`, `SARVAM_API_KEY`, `LANGSMITH_API_KEY`) are masked in diagnostic outputs and redacted from system error logs.
- **Rate Limiting:** In-memory sliding-window rate limiters prevent API flooding and token exhaustion.

---

## 🧪 Deterministic 9-Vector Evaluation Suite

Run the comprehensive offline evaluation suite in one command without spending any paid API tokens:

```bash
python -c "from graphsupport.application.evaluation import EvaluationRunner; import json; print(json.dumps(EvaluationRunner().run_all_evaluations().to_dict(), indent=2))"
```

The benchmark rigorously verifies:
1. **Context Retrieval Relevance:** Open tickets receive priority ranking over closed records.
2. **Outcome Fidelity:** Failed attempts remain strictly flagged with diagnostic indicators.
3. **Ticket Lifecycle Transitions:** Status changes strictly follow valid state transitions.
4. **Anti-Hallucination:** Unverified claims of ticket actions are detected and blocked.
5. **Tenant Isolation:** Cross-customer ticket queries are rejected at the boundary.
6. **Tool Argument Validation:** Invalid characters and SQL/Cypher tokens are sanitized.
7. **Prompt Injection Defense:** Heuristic override attempts are neutralized.
8. **Resilience & Privacy:** Connection strings and passwords are redacted from error logs.
9. **Latency Benchmark:** In-memory context compilation completes in `<5.0ms`.

---

## 🚀 Quickstart Guide

### 1. Prerequisites
- Python 3.10+ (Python 3.12 recommended)
- macOS Monterey 12.0+ or Linux
- Neo4j 5.x or free [Neo4j AuraDB](https://neo4j.com/cloud/platform/aura-graph-database/) instance

### 2. Setup Virtual Environment
```bash
# Clone the repository
git clone https://github.com/codingsexpert/graphsupport-ai.git
cd graphsupport-ai

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install package and development tools
pip install --upgrade pip
pip install -r requirements-dev.txt
pip install -e .
```

### 3. Configure Environment Variables
Copy the configuration template:
```bash
cp .env.example .env
```
Update `.env` with your credentials:
```bash
# Neo4j Aura Database
NEO4J_URI=neo4j+s://<your-instance-id>.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=<your-neo4j-password>
NEO4J_DATABASE=neo4j

# AI Provider (Sarvam AI / Gemini)
LLM_PROVIDER=sarvam
SARVAM_API_KEY=<your-sarvam-api-key>
SARVAM_MODEL=sarvam-105b-conversations

# LangSmith Observability (Optional)
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=<your-langsmith-key>
LANGSMITH_PROJECT=graphsupport-ai
```

### 4. Verify Subsystems & Run Tests
```bash
# Run complete test suite (157 passing tests)
pytest -q

# Run code format and lint checks (Ruff)
ruff check . && ruff format --check .
```

### 5. Launch the Dashboard
```bash
streamlit run app.py
```
Open **[http://localhost:8501](http://localhost:8501)** in your browser!

---

## 🧰 CLI Utilities

| Command | Action |
|---|---|
| `python scripts/check_environment.py` | Verify Python version, dependencies, and environment configuration. |
| `python scripts/seed_demo.py` | Seed the Sarah Chen demo scenario into Neo4j. |
| `python scripts/seed_demo.py --status` | Check if demo data is currently seeded in Neo4j. |
| `python scripts/seed_demo.py --reset` | Safely remove demo records only (leaves real customer data untouched). |

---

## 👥 Contributors & Hackathon Team

- **Author & Lead Architect:** Mukesh Singh ([@codingsexpert](https://github.com/codingsexpert))
- **Tech Stack:** Python 3.12, Neo4j AuraDB, Sarvam AI, LangSmith, Streamlit, Pydantic v2, Pytest.

---

<p align="center">
  <sub>Built with ❤️ for intelligent, context-aware customer support that never forgets.</sub>
</p>
