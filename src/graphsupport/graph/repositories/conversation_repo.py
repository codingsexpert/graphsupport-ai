"""Repository for Conversation and Message graph entities."""

import logging
from datetime import UTC, datetime
from typing import Any

from neo4j.exceptions import ConstraintError, Neo4jError

from graphsupport.core.exceptions import EntityNotFoundError, RepositoryError, ValidationError
from graphsupport.graph.driver import Neo4jDriverManager, get_driver_manager
from graphsupport.graph.models import Conversation, ConversationDetails, Message

logger = logging.getLogger("graphsupport.graph.repositories.conversation")


class ConversationRepository:
    """Repository handling (:Conversation) and (:Message) storage, ordering, and ticket linkage."""

    def __init__(
        self,
        driver_manager: Neo4jDriverManager | None = None,
        database: str | None = None,
    ) -> None:
        self.driver_manager = driver_manager or get_driver_manager()
        self.database = database or self.driver_manager.settings.neo4j_database

    def create_conversation(self, conversation: Conversation, customer_id: str) -> Conversation:
        """Create a Conversation node and link to Customer via [:HAS_CONVERSATION]."""
        logger.debug("Creating conversation %s for customer %s...", conversation.id, customer_id)
        query = """
        MATCH (c:Customer {id: $customer_id})
        CREATE (conv:Conversation {
            id: $id,
            session_id: $session_id,
            channel: $channel,
            started_at: $started_at,
            status: $status
        })
        MERGE (c)-[:HAS_CONVERSATION]->(conv)
        RETURN conv.id AS id, conv.session_id AS session_id, conv.channel AS channel,
               conv.started_at AS started_at, conv.status AS status, c.id AS customer_id
        """
        params = {
            "id": conversation.id,
            "session_id": conversation.session_id,
            "channel": conversation.channel,
            "started_at": conversation.started_at.isoformat(),
            "status": conversation.status,
            "customer_id": customer_id,
        }
        try:
            with self.driver_manager.session(database=self.database) as session:
                record = session.run(query, params).single()
                if not record:
                    c_exists = bool(
                        session.run(
                            "MATCH (c:Customer {id: $id}) RETURN count(c) > 0 AS ex",
                            {"id": customer_id},
                        ).single()["ex"]
                    )
                    if not c_exists:
                        raise EntityNotFoundError(
                            f"Customer with ID '{customer_id}' does not exist"
                        )
                    raise RepositoryError(
                        f"Failed to create conversation for customer {customer_id}"
                    )
                return self._record_to_conversation(record)
        except EntityNotFoundError:
            raise
        except ConstraintError as err:
            raise RepositoryError(f"Conversation constraint violation: {err.message}") from err
        except Neo4jError as err:
            raise RepositoryError(f"Database error creating conversation: {err.message}") from err
        except Exception as err:
            raise RepositoryError(f"Failed to create conversation: {err}") from err

    def get_by_id(self, conversation_id: str) -> Conversation | None:
        """Retrieve a Conversation by ID."""
        query = """
        MATCH (conv:Conversation {id: $id})
        OPTIONAL MATCH (c:Customer)-[:HAS_CONVERSATION]->(conv)
        RETURN conv.id AS id, conv.session_id AS session_id, conv.channel AS channel,
               conv.started_at AS started_at, conv.status AS status, c.id AS customer_id
        """
        try:
            with self.driver_manager.session(database=self.database) as session:
                record = session.run(query, {"id": conversation_id}).single()
                if not record:
                    return None
                return self._record_to_conversation(record)
        except Exception as err:
            raise RepositoryError(f"Failed to retrieve conversation: {err}") from err

    def list_customer_conversations(
        self, customer_id: str, limit: int = 50, skip: int = 0
    ) -> list[Conversation]:
        """List conversations belonging to a customer with pagination."""
        if limit < 1 or limit > 500:
            raise ValidationError(f"Limit must be between 1 and 500, got {limit}")
        if skip < 0:
            raise ValidationError(f"Skip cannot be negative, got {skip}")

        query = """
        MATCH (c:Customer {id: $customer_id})-[:HAS_CONVERSATION]->(conv:Conversation)
        RETURN conv.id AS id, conv.session_id AS session_id, conv.channel AS channel,
               conv.started_at AS started_at, conv.status AS status, c.id AS customer_id
        ORDER BY conv.started_at DESC, conv.id ASC
        SKIP $skip
        LIMIT $limit
        """
        conversations: list[Conversation] = []
        try:
            with self.driver_manager.session(database=self.database) as session:
                params = {"customer_id": customer_id, "skip": skip, "limit": limit}
                result = session.run(query, params)
                for record in result:
                    conversations.append(self._record_to_conversation(record))
            return conversations
        except Exception as err:
            raise RepositoryError(f"Failed to list customer conversations: {err}") from err

    def append_message(
        self,
        message: Message,
        conversation_id: str,
        ticket_id: str | None = None,
    ) -> Message:
        """Append a Message to a conversation and optionally link to a support ticket."""
        logger.debug(
            "Appending message %s to conversation %s (ticket: %s)...",
            message.id,
            conversation_id,
            ticket_id,
        )
        query = """
        MATCH (conv:Conversation {id: $conversation_id})
        CREATE (m:Message {
            id: $id,
            sender_type: $sender_type,
            content: $content,
            sequence_number: $sequence_number,
            timestamp: $timestamp
        })
        MERGE (conv)-[:CONTAINS]->(m)
        WITH m, conv
        CALL {
            WITH m
            WITH m WHERE $ticket_id IS NOT NULL
            MATCH (t:SupportTicket {id: $ticket_id})
            MERGE (m)-[:ABOUT]->(t)
            RETURN count(t) AS linked_ticket
        }
        RETURN m.id AS id, m.sender_type AS sender_type, m.content AS content,
               m.sequence_number AS sequence_number, m.timestamp AS timestamp,
               $conversation_id AS conversation_id, $ticket_id AS ticket_id
        """
        params = {
            "id": message.id,
            "sender_type": message.sender_type,
            "content": message.content,
            "sequence_number": message.sequence_number,
            "timestamp": message.timestamp.isoformat(),
            "conversation_id": conversation_id,
            "ticket_id": ticket_id,
        }
        try:
            with self.driver_manager.session(database=self.database) as session:
                record = session.run(query, params).single()
                if not record:
                    conv_exists = bool(
                        session.run(
                            "MATCH (c:Conversation {id: $id}) RETURN count(c) > 0 AS ex",
                            {"id": conversation_id},
                        ).single()["ex"]
                    )
                    if not conv_exists:
                        raise EntityNotFoundError(
                            f"Conversation with ID '{conversation_id}' does not exist"
                        )

                    if ticket_id:
                        t_exists = bool(
                            session.run(
                                "MATCH (t:SupportTicket {id: $id}) RETURN count(t) > 0 AS ex",
                                {"id": ticket_id},
                            ).single()["ex"]
                        )
                        if not t_exists:
                            raise EntityNotFoundError(
                                f"Ticket with ID '{ticket_id}' does not exist"
                            )

                    raise RepositoryError("Failed to append message to conversation")

                return self._record_to_message(record)
        except EntityNotFoundError:
            raise
        except ConstraintError as err:
            raise RepositoryError(f"Message constraint violation: {err.message}") from err
        except Neo4jError as err:
            raise RepositoryError(f"Database error appending message: {err.message}") from err
        except Exception as err:
            raise RepositoryError(f"Failed to append message: {err}") from err

    def get_conversation_messages(self, conversation_id: str) -> list[Message]:
        """Retrieve all messages in a conversation, preserved in strict deterministic order."""
        query = """
        MATCH (conv:Conversation {id: $conversation_id})-[:CONTAINS]->(m:Message)
        OPTIONAL MATCH (m)-[:ABOUT]->(t:SupportTicket)
        RETURN m.id AS id, m.sender_type AS sender_type, m.content AS content,
               m.sequence_number AS sequence_number, m.timestamp AS timestamp,
               $conversation_id AS conversation_id, t.id AS ticket_id
        ORDER BY m.sequence_number ASC, m.timestamp ASC, m.id ASC
        """
        messages: list[Message] = []
        try:
            with self.driver_manager.session(database=self.database) as session:
                result = session.run(query, {"conversation_id": conversation_id})
                for record in result:
                    messages.append(self._record_to_message(record))
            return messages
        except Exception as err:
            raise RepositoryError(f"Failed to fetch conversation messages: {err}") from err

    def get_conversation_details(self, conversation_id: str) -> ConversationDetails | None:
        """Retrieve conversation along with its full ordered message transcript."""
        conv = self.get_by_id(conversation_id)
        if not conv:
            return None
        messages = self.get_conversation_messages(conversation_id)
        return ConversationDetails(conversation=conv, messages=messages)

    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete conversation and all contained messages (used for cleanup)."""
        query = """
        MATCH (conv:Conversation {id: $id})
        OPTIONAL MATCH (conv)-[:CONTAINS]->(m:Message)
        DETACH DELETE m, conv
        RETURN count(conv) AS deleted_count
        """
        try:
            with self.driver_manager.session(database=self.database) as session:
                result = session.run(query, {"id": conversation_id}).single()
                return bool(result and result["deleted_count"] > 0)
        except Exception as err:
            raise RepositoryError(f"Failed to delete conversation: {err}") from err

    @staticmethod
    def _record_to_conversation(record: Any) -> Conversation:
        started_at_raw = record.get("started_at")
        started_at = (
            datetime.fromisoformat(started_at_raw)
            if isinstance(started_at_raw, str)
            else (started_at_raw or datetime.now(UTC))
        )
        return Conversation(
            id=record["id"],
            customer_id=record.get("customer_id"),
            session_id=record.get("session_id", record["id"]),
            channel=record.get("channel", "web"),
            started_at=started_at,
            status=record.get("status", "active"),
        )

    @staticmethod
    def _record_to_message(record: Any) -> Message:
        timestamp_raw = record.get("timestamp")
        timestamp = (
            datetime.fromisoformat(timestamp_raw)
            if isinstance(timestamp_raw, str)
            else (timestamp_raw or datetime.now(UTC))
        )
        return Message(
            id=record["id"],
            conversation_id=record.get("conversation_id"),
            sender_type=record["sender_type"],
            content=record["content"],
            sequence_number=record.get("sequence_number", 1),
            ticket_id=record.get("ticket_id"),
            timestamp=timestamp,
        )
