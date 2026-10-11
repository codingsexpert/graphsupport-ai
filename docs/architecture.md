# GraphSupport AI — System Architecture

## 1. Overview and Vision

**GraphSupport AI** is an intelligent, context-aware customer support engine. Traditional support bots treat inquiries as isolated queries or rely solely on flat vector databases, often missing relationships between products, known defects, customer ticket histories, and past troubleshooting attempts.

GraphSupport AI bridges this gap by persisting a connected property graph in **Neo4j** and pairing it with an LLM reasoning agent. The graph preserves cross-session context:
- Customer identity, subscription tier, and device ownership.
- Historical support tickets, triage logs, and symptom patterns.
- Product topologies, firmware versions, and known component failures.
- Step-by-step troubleshooting attempts and verified resolutions.

```
+-----------------------------------------------------------------------------------+
|                                Streamlit UI (app.py)                              |
|   - Customer Support Portal   - Ticket Dashboard   - Graph Context Explorer       |
+------------------------------------------+----------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------+
|                        Core Layer (graphsupport.core)                             |
|   - Exception Hierarchy       - Structured Logging     - Health & Diagnostics     |
+------------------------------------------+----------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------+
|                       Config Layer (graphsupport.config)                          |
|   - Pydantic Settings         - Environment Loading    - Secret Masking           |
+------------------------------------------+----------------------------------------+
                                           |
         +---------------------------------+---------------------------------+
         | (Reserved for Phase 2)                                            | (Reserved for Phase 5)
         v                                                                   v
+----------------------------------+               +----------------------------------+
|      Neo4j Graph Database        |               |      LLM Reasoning Engine        |
| - Customers, Tickets, Products   |               | - Subgraph Context Injection     |
| - Issues, Steps, Resolutions     |               | - Dynamic Tool Calling           |
+----------------------------------+               +----------------------------------+
```

---

## 2. Layered Component Boundaries

To guarantee testability, maintainability, and clean separation of concerns, the codebase is structured into isolated layers:

### A. Configuration Layer (`src/graphsupport/config`)
- **Responsibility**: Loads, validates, and manages typed application settings.
- **Technology**: `pydantic-settings` (`BaseSettings`).
- **Security**: Sensitive attributes (`neo4j_password`, `llm_api_key`) utilize `SecretStr`. Plaintext credentials are automatically masked from logs, string representations, and API payloads.
- **Isolation**: Supports dynamic reloading and test parameter overrides without altering on-disk `.env` files.

### B. Core Layer (`src/graphsupport/core`)
- **Exceptions (`exceptions.py`)**: Structured hierarchy rooted at `GraphSupportError`. Forbids broad exception swallowing and provides domain-specific diagnostics (`ConfigurationError`, `EnvironmentValidationError`, `ServiceUnavailableError`).
- **Logging (`logging_config.py`)**: Structured standard library logging with ISO timestamps, module names, line numbers, and a `SecretSanitizingFilter` that redacts inadvertent credential exposures.
- **Health & Diagnostics (`health.py`)**: Non-sensitive inspection module reporting initialization status, Python/OS details, and readiness indicators for upcoming phases.

### C. UI Presentation Layer (`src/graphsupport/ui`)
- **Responsibility**: Lightweight Streamlit presentation components (`components.py`, `styles.py`, `navigation.py`).
- **Design Tokens**: Accessible color palette, custom CSS layout cards, and responsive sidebar navigation.
- **Integrity**: Accurately reflects current implementation status without claiming unconfigured services are connected.

### D. Graph Persistence Layer (Reserved for Phase 2)
- **Scope**: Dedicated Neo4j driver connection pooling, graph schema constraints, unique indices, node/relationship data models, and repository interfaces.

### E. LLM Reasoning Agent (Reserved for Phase 5)
- **Scope**: Graph-RAG prompt orchestrator, cross-session memory manager, and multi-turn conversational interface.

---

## 3. Data & Graph Model Preview (Phase 2+)

In upcoming phases, Neo4j will store the support domain model with the following primary node types and relationships:

```
(:Customer) -[:SUBMITTED]-> (:Ticket) -[:AFFECTS]-> (:Product)
     |                           |
     |                           +---[:DESCRIBES_ISSUE]-> (:Issue)
     v                                                      |
(:Device)                                             [:RESOLVED_BY]-> (:Resolution)
```

- `Customer`: Unique customer identity, email, name, account tier.
- `Product`: Model name, SKU, firmware version, category.
- `Ticket`: Support ticket ID, priority, status, opening timestamp.
- `Issue`: Canonical symptom classification, root cause analysis.
- `TroubleshootingStep`: Diagnostic action, verification result.
- `Resolution`: Verified solution, fix documentation link.

---

## 4. Phase 1 Deliverable Status

Phase 1 establishes the production-grade foundation:
1. Modular package structure under `src/graphsupport`.
2. Typed Pydantic configuration with secret protection.
3. Centralized exceptions and structured logging.
4. Health check diagnostics.
5. Streamlit dashboard showing accurate Phase 1 status.
6. Full unit and integration test coverage.
7. Ruff linting and code formatting configuration.
