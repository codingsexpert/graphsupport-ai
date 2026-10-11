"""Graph persistence and repository layer for GraphSupport AI.

Provides safe, parameterized repository access for customer graph entities
with managed transaction handling and zero user-constructed Cypher strings.
"""

import json
import logging
from datetime import datetime
from typing import Any

from neo4j.exceptions import Neo4jError

from graphsupport.core.exceptions import RepositoryError
from graphsupport.graph.driver import Neo4jDriverManager, get_driver_manager
from graphsupport.graph.models import Customer

logger = logging.getLogger("graphsupport.graph.repository")


class CustomerRepository:
    """Repository handling persistence and retrieval of (:Customer) graph nodes."""

    def __init__(
        self,
        driver_manager: Neo4jDriverManager | None = None,
        database: str | None = None,
    ) -> None:
        self.driver_manager = driver_manager or get_driver_manager()
        self.database = database or self.driver_manager.settings.neo4j_database

    def upsert_customer(self, customer: Customer) -> Customer:
        """Create or update a Customer node using parameterized Cypher MERGE.

        Args:
            customer: Validated Customer domain model instance.

        Returns:
            The persisted Customer entity.

        Raises:
            RepositoryError: If Cypher execution or transaction fails.
        """
        logger.debug("Upserting customer node (ID: %s)...", customer.id)

        query = """
        MERGE (c:Customer {id: $id})
        ON CREATE SET
            c.email = $email,
            c.name = $name,
            c.tier = $tier,
            c.created_at = $created_at,
            c.metadata = $metadata
        ON MATCH SET
            c.email = $email,
            c.name = $name,
            c.tier = $tier,
            c.metadata = $metadata
        RETURN c.id AS id, c.email AS email, c.name AS name, c.tier AS tier,
               c.created_at AS created_at, c.metadata AS metadata
        """

        params = {
            "id": customer.id,
            "email": customer.email,
            "name": customer.name,
            "tier": customer.tier,
            "created_at": customer.created_at.isoformat(),
            "metadata": json.dumps(customer.metadata),
        }

        try:
            with self.driver_manager.session(database=self.database) as session:
                result = session.run(query, params)
                record = result.single()
                if not record:
                    raise RepositoryError(
                        f"Failed to upsert customer {customer.id}: no record returned"
                    )

                return self._record_to_customer(record)
        except Neo4jError as err:
            raise RepositoryError(
                f"Database error during customer upsert: {type(err).__name__}: {err.message}"
            ) from err
        except Exception as err:
            raise RepositoryError(
                f"Unexpected failure during customer upsert: {type(err).__name__}: {err}"
            ) from err

    def get_by_id(self, customer_id: str) -> Customer | None:
        """Retrieve a Customer entity by unique identifier.

        Args:
            customer_id: Unique UUID string of customer.

        Returns:
            Customer instance or None if not found.
        """
        logger.debug("Retrieving customer by ID: %s", customer_id)
        query = """
        MATCH (c:Customer {id: $id})
        RETURN c.id AS id, c.email AS email, c.name AS name, c.tier AS tier,
               c.created_at AS created_at, c.metadata AS metadata
        """
        try:
            with self.driver_manager.session(database=self.database) as session:
                record = session.run(query, {"id": customer_id}).single()
                if not record:
                    return None
                return self._record_to_customer(record)
        except Neo4jError as err:
            raise RepositoryError(
                f"Database error retrieving customer by ID: {type(err).__name__}: {err.message}"
            ) from err
        except Exception as err:
            raise RepositoryError(
                f"Failed to retrieve customer: {type(err).__name__}: {err}"
            ) from err

    def get_by_email(self, email: str) -> Customer | None:
        """Retrieve a Customer entity by email address."""
        logger.debug("Retrieving customer by email...")
        query = """
        MATCH (c:Customer {email: $email})
        RETURN c.id AS id, c.email AS email, c.name AS name, c.tier AS tier,
               c.created_at AS created_at, c.metadata AS metadata
        """
        try:
            with self.driver_manager.session(database=self.database) as session:
                record = session.run(query, {"email": email}).single()
                if not record:
                    return None
                return self._record_to_customer(record)
        except Neo4jError as err:
            raise RepositoryError(
                f"Database error retrieving customer by email: {type(err).__name__}: {err.message}"
            ) from err
        except Exception as err:
            raise RepositoryError(
                f"Failed to retrieve customer: {type(err).__name__}: {err}"
            ) from err

    def delete_by_id(self, customer_id: str) -> bool:
        """Delete an exact customer record by ID (used for test data cleanup)."""
        logger.debug("Deleting customer node by ID: %s", customer_id)
        query = """
        MATCH (c:Customer {id: $id})
        DETACH DELETE c
        RETURN count(c) AS deleted_count
        """
        try:
            with self.driver_manager.session(database=self.database) as session:
                result = session.run(query, {"id": customer_id}).single()
                return bool(result and result["deleted_count"] > 0)
        except Exception as err:
            raise RepositoryError(f"Failed to delete customer {customer_id}: {err}") from err

    @staticmethod
    def _record_to_customer(record: Any) -> Customer:
        """Parse Cypher record map into a validated Customer entity."""
        raw_metadata = record.get("metadata", "{}")
        if isinstance(raw_metadata, str):
            try:
                metadata = json.loads(raw_metadata)
            except Exception:
                metadata = {}
        elif isinstance(raw_metadata, dict):
            metadata = raw_metadata
        else:
            metadata = {}

        raw_created_at = record.get("created_at")
        if isinstance(raw_created_at, str):
            try:
                created_at = datetime.fromisoformat(raw_created_at)
            except Exception:
                created_at = datetime.now()
        elif isinstance(raw_created_at, datetime):
            created_at = raw_created_at
        else:
            created_at = datetime.now()

        return Customer(
            id=record["id"],
            email=record["email"],
            name=record["name"],
            tier=record.get("tier", "standard"),
            created_at=created_at,
            metadata=metadata,
        )
