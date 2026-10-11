# GraphSupport AI — System Architecture

## 1. Overview and Vision

**GraphSupport AI** is an intelligent, context-aware customer support engine. Traditional support bots treat inquiries as isolated queries or rely solely on flat vector databases, often missing relationships between products, known defects, customer ticket histories, and past troubleshooting attempts.

GraphSupport AI bridges this gap by persisting a connected property graph in **Neo4j** and pairing it with an LLM reasoning agent in later phases. The graph preserves cross-session context:
- Customer identity, subscription tier, and product ownership.
- Historical support tickets, triage logs, and symptom patterns.
- Product topologies, firmware versions, and known component failures.
- Step-by-step troubleshooting attempts and verified resolutions.

```
+-----------------------------------------------------------------------------------+
|                                Streamlit UI (app.py)                              |
|   - Customer Support Portal   - Ticket Dashboard   - Database Control Panel       |
+------------------------------------------+----------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------+
|                      Graph Persistence Layer (graphsupport.graph)                 |
|   - Driver Manager (Pooling/TLS) - Schema Migrations - Customer Repository        |
|   - Domain Models (Customer, Product, Issue, Ticket, Step, Resolution)            |
+------------------------------------------+----------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------+
|                        Core Layer (graphsupport.core)                             |
|   - Database Exception Hierarchy  - Structured Logging   - Health & Diagnostics   |
+------------------------------------------+----------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------+
|                       Config Layer (graphsupport.config)                          |
|   - Pydantic Settings         - Environment Loading    - Secret Masking           |
+------------------------------------------+----------------------------------------+
                                           |
         +---------------------------------+---------------------------------+
         | (Operational in Phase 2)                                          | (Reserved for Phase 5)
         v                                                                   v
+----------------------------------+               +----------------------------------+
|      Neo4j Graph Database        |               |      LLM Reasoning Engine        |
| - Customers, Tickets, Products   |               | - Subgraph Context Injection     |
| - Issues, Steps, Resolutions     |               | - Dynamic Tool Calling           |
+----------------------------------+               +----------------------------------+
```

---

## 2. Graph Schema & Domain Model (Phase 2)

### A. Graph Nodes
All core entities employ durable application-generated UUID4 identifiers as primary keys:

- `Customer` (`:Customer`): `id` (UUID, UNIQUE), `email` (string, UNIQUE), `name`, `tier`, `created_at`, `metadata`.
- `Product` (`:Product`): `id` (UUID, UNIQUE), `name`, `sku` (string, INDEXED), `category`, `version`, `metadata`.
- `Issue` (`:Issue`): `id` (UUID, UNIQUE), `title`, `description`, `category`, `severity`, `created_at`.
- `SupportTicket` (`:SupportTicket`): `id` (UUID, UNIQUE), `title`, `description`, `status` (enum, INDEXED), `priority`, `created_at`, `updated_at`.
- `Conversation` (`:Conversation`): `id` (UUID, UNIQUE), `session_id`, `channel`, `started_at`, `status`.
- `Message` (`:Message`): `id` (UUID, UNIQUE), `sender_type`, `content`, `timestamp`.
- `TroubleshootingStep` (`:TroubleshootingStep`): `id` (UUID, UNIQUE), `step_number`, `action`, `outcome` (enum), `notes`, `executed_at`.
- `Resolution` (`:Resolution`): `id` (UUID, UNIQUE), `summary`, `resolution_type`, `verified`, `created_at`.

### B. Graph Relationships
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

### C. Documented Enums
- `TicketStatus`: `open`, `in_progress`, `resolved`, `closed`.
- `TroubleshootingOutcome`: `success`, `failed`, `partial`, `unknown`.

---

## 3. Database Driver & Security Architecture

1. **Encrypted Aura Transport**: Uses official `neo4j` Python driver with `neo4j+s://` protocol and TLS encryption.
2. **Deterministic Connection Pooling**: Configured with explicit `connection_timeout` (15s) and `max_connection_lifetime` (3600s).
3. **Secret Isolation**: `neo4j_password` is encapsulated as `SecretStr`. Passwords and credentials are never emitted in exceptions, logs, or UI elements.
4. **Parameterized Cypher**: All repository operations strictly use query parameters (`$id`, `$email`, etc.). String interpolation for Cypher queries is strictly prohibited.
5. **Idempotent Schema Application**: All DDL statements utilize `IF NOT EXISTS` semantics, making schema initialization safe to execute repeatedly without dropping or modifying existing data.
