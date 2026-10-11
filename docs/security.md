# GraphSupport AI — Security Architecture & Threat Model

This document specifies the security controls, trust boundaries, threat model, and residual risks for **GraphSupport AI** (Phase 7 Hardening).

---

## 1. Threat Model & Protected Assets

### A. Protected Assets
1. **Customer Records**: Personal identifiers (`id`, `email`, `name`, `tier`, `metadata`).
2. **Customer Support History**: Tickets, triage summaries, diagnostic steps, outcomes, and resolutions.
3. **Conversational Transcripts**: Customer-agent dialogue messages across sessions.
4. **Graph Database Credentials**: Neo4j Aura URI, username, password, and database namespaces.
5. **LLM Provider Credentials**: API keys for external providers (Google Gemini, OpenAI).
6. **System Integrity**: Preventing arbitrary Cypher injection, tool hijacking, or malicious prompt execution.

### B. Threat Actors & Scenarios
| Threat Actor | Vector | Objective | Defense Mechanism |
|---|---|---|---|
| **Malicious Customer** | Direct Prompt Injection | Extract system instructions, bypass safety rules, harvest credentials | Isolated system prompt index, sandwich reminder, heuristic signature scanner |
| **Malicious Customer** | Cross-Tenant Data Access | Inspect or modify another customer's ticket or conversation | Scoped `authorized_customer_id` check in `ToolRegistry` and application service boundaries |
| **Malicious Customer** | Injection Payloads | Inject Cypher/SQL commands via IDs or form inputs | Strict `validate_entity_id()` regex and 100% parameterized Cypher (`$params`) |
| **Compromised LLM** | Hallucinated Action Claim | Claim ticket was resolved or created without tool invocation | `OutputParser` fact-checker verifying against executed tool results |
| **Automated Client** | Denial of Service / Quota Drain | Flood agent chat or database with rapid requests | Thread-safe `InMemoryRateLimiter` sliding window throttling per customer |
| **Internal Operator** | Credential Leakage in Logs | View raw passwords or API keys in standard application logs | Pydantic `SecretStr`, `redact_sensitive_text()`, and `safe_summary()` masking |

---

## 2. Trust Boundaries & Isolation

```
[ UNTRUSTED USER INPUT ]
   - Customer messages
   - Search queries
   - Form inputs
         │
         ▼  (Input Sanitization & Identifier Validation)
[ APPLICATION BOUNDARY: SupportService / ToolRegistry ]
   - Enforces authorized_customer_id
   - Validates ownership before reads & writes
   - Rate limiting & deduplication guards
         │
         ▼  (Parameterized Cypher Only: $id, $email)
[ PERSISTENCE BOUNDARY: Neo4j Aura ]
   - Unique constraints & indexes
   - Scoped property graph
```

### Customer Tenant Boundary
- In the current development and demo state, the customer selector allows switching customer context.
- **Critical Boundary Guarantee**: Once an `authorized_customer_id` is established for an agent turn, the `ToolRegistry` strictly locks all tool executions (`get_customer_history`, `get_ticket_status`, `create_support_ticket`, `record_troubleshooting_attempt`, `update_ticket_status`, `escalate_ticket`) to that customer.
- Any attempt by the LLM or an argument payload to access a ticket belonging to another customer raises `AuthorizationError` and returns a structured failure without leaking data.

---

## 3. Parameterized Cypher & Query Safety

1. **Zero String Concatenation**: 100% of Cypher queries across `CustomerRepository`, `ProductRepository`, `TicketRepository`, `ConversationRepository`, `TroubleshootingRepository`, and `SupportService` use parameterized values (`$id`, `$cid`, `$limit`, etc.).
2. **Safe Identifier Validation**: All entity IDs are passed through `validate_entity_id()`, which rejects whitespace, quotes, slashes, null bytes, and control characters:
   ```python
   SAFE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\.]{1,128}$")
   ```
3. **Bounded Graph Traversal**: Subgraph visualizer queries and history retrieval enforce hard limits (maximum 60 nodes for graph visualizer; maximum 50 records for list queries).

---

## 4. Prompt Injection Defense & Residual Risks

### A. Defense-in-Depth Pipeline
1. **Heuristic Signature Scanner**: `scan_for_prompt_injection()` inspects incoming messages for known override patterns (`ignore previous instructions`, `you are now DAN`, `reveal system prompt`, `drop database`).
2. **Structural Separation**: System directives reside in message index `0` as an isolated `system` role. User messages are isolated as `user` role turns and can never redefine system-level directives.
3. **Output Validation**: `OutputParser` fact-checks final model responses against actual tool executions. If the model claims it created or resolved a ticket without a corresponding tool record, the claim is flagged as unverified.
4. **Tool Allowlisting**: The model cannot execute arbitrary Python, shell commands, or unapproved tools. Only the 7 allowlisted domain tools can be executed.

### B. Residual Risks & Disclaimers
> [!IMPORTANT]
> **Prompt injection cannot be 100% eliminated through heuristic filters alone.** Complex semantic rephrasing, steganography, or multilingual adversarial attacks can theoretically bypass heuristic regexes.
> For production environments:
> - Do not grant the AI agent access to destructive deletion tools or financial transactions.
> - Maintain human-in-the-loop review for high-impact actions (e.g., ticket closure, tier-2 escalation).
> - Deploy specialized guardrail classifiers (e.g., Llama Guard or NeMo Guardrails) in front of model completion calls.

---

## 5. Tool Safety & Deduplication Safeguards

Every domain tool features:
- **Pydantic Validation**: Strict length, character, and enum validation.
- **Tenant Authorization Check**: Confirms customer owns the target ticket before inspection or modification.
- **Deduplication Safeguards**:
  - `create_support_ticket`: Reuses an existing active ticket with an identical title instead of creating duplicate records during retries.
  - `record_troubleshooting_attempt`: Detects duplicate step numbers and identical actions to prevent cluttered diagnostic timelines.
- **Execution Timing & Correlation Tracking**: Every tool execution records execution duration (`duration_ms`) and request correlation ID (`correlation_id`).
- **Secret Redaction**: Error strings are passed through `redact_sensitive_text()` before return to the model or UI.

---

## 6. Rate Limiting & Resource Protection

- `InMemoryRateLimiter`: Thread-safe sliding window tracking request timestamps per client key (default: 60 requests/minute).
- Exceeding the rate limit raises `RateLimitExceededError` with clear retry guidance.
- **Limitation Note**: In-memory rate limiting is per-process. A multi-instance production deployment requires distributed caching (e.g., Redis / Valkey).

---

## 7. Production Deployment Roadmap (Pre-Launch Requirements)

Before exposing GraphSupport AI to the public internet:

1. **Enterprise Identity & Authentication**:
   - Replace the demo customer dropdown with OIDC / OAuth2 token authentication (e.g., Auth0, Okta, Firebase Auth).
   - Derive `authorized_customer_id` from cryptographically verified JWT claims, not user-controllable UI state.
2. **Role-Based Access Control (RBAC)**:
   - Separate permissions into three roles:
     - `Customer`: Can only view their own products, tickets, and conversations.
     - `Support Agent`: Can view all customer tickets, triage issues, and log resolutions.
     - `Administrator`: Can manage configuration and view system health.
3. **Distributed Rate Limiting**:
   - Move from `InMemoryRateLimiter` to a distributed Redis token-bucket limiter to support multi-worker containers.
4. **Audit Logging & SIEM**:
   - Stream structured audit logs (containing correlation IDs, customer IDs, and tool execution outcomes) to CloudWatch, Datadog, or Google Cloud Logging.
5. **TLS Termination & WAF**:
   - Enforce HTTPS and place a Web Application Firewall (WAF) in front of the Streamlit server to block automated bots and DDoS attacks.
