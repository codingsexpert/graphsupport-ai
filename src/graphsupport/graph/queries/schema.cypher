// ==============================================================================
// GraphSupport AI — Neo4j Graph Schema Definitions (Phase 2)
// ==============================================================================
// All constraints and indexes use idempotent `IF NOT EXISTS` syntax (Neo4j 5.x+).
// Application-managed UUIDs serve as durable entity primary keys.
// ==============================================================================

// --- Node Key & Uniqueness Constraints ---

// Customer uniqueness
CREATE CONSTRAINT customer_id_unique IF NOT EXISTS
FOR (c:Customer) REQUIRE c.id IS UNIQUE;

CREATE CONSTRAINT customer_email_unique IF NOT EXISTS
FOR (c:Customer) REQUIRE c.email IS UNIQUE;

// Product catalog uniqueness
CREATE CONSTRAINT product_id_unique IF NOT EXISTS
FOR (p:Product) REQUIRE p.id IS UNIQUE;

// Known issues and defects
CREATE CONSTRAINT issue_id_unique IF NOT EXISTS
FOR (i:Issue) REQUIRE i.id IS UNIQUE;

// Support tickets
CREATE CONSTRAINT ticket_id_unique IF NOT EXISTS
FOR (t:SupportTicket) REQUIRE t.id IS UNIQUE;

// Conversations and chat sessions
CREATE CONSTRAINT conversation_id_unique IF NOT EXISTS
FOR (c:Conversation) REQUIRE c.id IS UNIQUE;

// Transcript messages
CREATE CONSTRAINT message_id_unique IF NOT EXISTS
FOR (m:Message) REQUIRE m.id IS UNIQUE;

// Troubleshooting steps
CREATE CONSTRAINT step_id_unique IF NOT EXISTS
FOR (s:TroubleshootingStep) REQUIRE s.id IS UNIQUE;

// Verified resolutions
CREATE CONSTRAINT resolution_id_unique IF NOT EXISTS
FOR (r:Resolution) REQUIRE r.id IS UNIQUE;

// --- Lookup Indexes for Fast Traversal & Filtering ---

// Support ticket status filtering
CREATE INDEX ticket_status_idx IF NOT EXISTS
FOR (t:SupportTicket) ON (t.status);

// Product SKU lookup
CREATE INDEX product_sku_idx IF NOT EXISTS
FOR (p:Product) ON (p.sku);
