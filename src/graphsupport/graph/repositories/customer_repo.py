"""Repository for Customer graph entities."""

import json
import logging
from datetime import datetime
from typing import Any

from neo4j.exceptions import ConstraintError, Neo4jError

from graphsupport.core.exceptions import (
    DuplicateEntityError,
    EntityNotFoundError,
    RepositoryError,
    ValidationError,
)
from graphsupport.graph.driver import Neo4jDriverManager, get_driver_manager
from graphsupport.graph.models import Customer

logger = logging.getLogger("graphsupport.graph.repositories.customer")


class CustomerRepository:
    """Repository handling persistence, retrieval, and updates for (:Customer) nodes."""

    def __init__(
        self,
        driver_manager: Neo4jDriverManager | None = None,
        database: str | None = None,
    ) -> None:
        self.driver_manager = driver_manager or get_driver_manager()
        self.database = database or self.driver_manager.settings.neo4j_database

    def create_customer(self, customer: Customer) -> Customer:
        """Create a new Customer node.

        Fails with RepositoryError if a customer with the same ID or email already exists.
        """
        logger.debug("Creating customer node (ID: %s)...", customer.id)
        query = """
        CREATE (c:Customer {
            id: $id,
            email: $email,
            name: $name,
            tier: $tier,
            created_at: $created_at,
            metadata: $metadata
        })
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
                    raise RepositoryError(f"Failed to create customer {customer.id}")
                return self._record_to_customer(record)
        except ConstraintError as err:
            raise DuplicateEntityError(
                f"Customer creation rejected by constraint (duplicate ID or email): {err.message}"
            ) from err
        except Neo4jError as err:
            err_msg = getattr(err, "message", str(err))
            raise RepositoryError(f"Database error during customer creation: {err_msg}") from err
        except Exception as err:
            raise RepositoryError(f"Unexpected error during customer creation: {err}") from err

    def upsert_customer(self, customer: Customer) -> Customer:
        """Create or update a Customer node using parameterized Cypher MERGE."""
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
                record = session.run(query, params).single()
                if not record:
                    raise RepositoryError(f"Failed to upsert customer {customer.id}")
                return self._record_to_customer(record)
        except ConstraintError as err:
            raise RepositoryError(f"Customer constraint violation: {err.message}") from err
        except Exception as err:
            raise RepositoryError(f"Database failure during customer upsert: {err}") from err

    def update_customer(
        self,
        customer_id: str,
        name: str | None = None,
        tier: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Customer:
        """Update explicitly permitted fields on an existing customer.

        Prevents identity replacement; never alters ID or email.
        """
        logger.debug("Updating customer fields for ID: %s...", customer_id)
        existing = self.get_by_id(customer_id)
        if not existing:
            raise EntityNotFoundError(f"Customer with ID '{customer_id}' does not exist")

        query = """
        MATCH (c:Customer {id: $id})
        SET
            c.name = CASE WHEN $name IS NOT NULL THEN $name ELSE c.name END,
            c.tier = CASE WHEN $tier IS NOT NULL THEN $tier ELSE c.tier END,
            c.metadata = CASE WHEN $metadata IS NOT NULL THEN $metadata ELSE c.metadata END
        RETURN c.id AS id, c.email AS email, c.name AS name, c.tier AS tier,
               c.created_at AS created_at, c.metadata AS metadata
        """
        params = {
            "id": customer_id,
            "name": name.strip() if name is not None else None,
            "tier": tier.strip() if tier is not None else None,
            "metadata": json.dumps(metadata) if metadata is not None else None,
        }
        try:
            with self.driver_manager.session(database=self.database) as session:
                record = session.run(query, params).single()
                if not record:
                    raise EntityNotFoundError(f"Customer with ID '{customer_id}' not found")
                return self._record_to_customer(record)
        except Exception as err:
            raise RepositoryError(f"Failed to update customer {customer_id}: {err}") from err

    def get_by_id(self, customer_id: str) -> Customer | None:
        """Retrieve a Customer entity by unique identifier."""
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
            err_msg = getattr(err, "message", str(err))
            raise RepositoryError(
                f"Database error retrieving customer: {type(err).__name__}: {err_msg}"
            ) from err
        except Exception as err:
            raise RepositoryError(f"Failed to retrieve customer: {err}") from err

    def get_by_email(self, email: str) -> Customer | None:
        """Retrieve a Customer entity by email address."""
        clean_email = email.strip().lower()
        query = """
        MATCH (c:Customer {email: $email})
        RETURN c.id AS id, c.email AS email, c.name AS name, c.tier AS tier,
               c.created_at AS created_at, c.metadata AS metadata
        """
        try:
            with self.driver_manager.session(database=self.database) as session:
                record = session.run(query, {"email": clean_email}).single()
                if not record:
                    return None
                return self._record_to_customer(record)
        except Neo4jError as err:
            err_msg = getattr(err, "message", str(err))
            raise RepositoryError(
                f"Database error retrieving customer: {type(err).__name__}: {err_msg}"
            ) from err
        except Exception as err:
            raise RepositoryError(f"Failed to retrieve customer: {err}") from err

    def list_customers(self, limit: int = 50, skip: int = 0) -> list[Customer]:
        """List customers using deterministic ordering and pagination."""
        if limit < 1 or limit > 500:
            raise ValidationError(f"Limit must be between 1 and 500, got {limit}")
        if skip < 0:
            raise ValidationError(f"Skip cannot be negative, got {skip}")

        query = """
        MATCH (c:Customer)
        RETURN c.id AS id, c.email AS email, c.name AS name, c.tier AS tier,
               c.created_at AS created_at, c.metadata AS metadata
        ORDER BY c.created_at DESC, c.id ASC
        SKIP $skip
        LIMIT $limit
        """
        customers: list[Customer] = []
        try:
            with self.driver_manager.session(database=self.database) as session:
                result = session.run(query, {"skip": skip, "limit": limit})
                for record in result:
                    customers.append(self._record_to_customer(record))
            return customers
        except Exception as err:
            raise RepositoryError(f"Failed to list customers: {err}") from err

    def delete_by_id(self, customer_id: str) -> bool:
        """Delete an exact customer record by ID (used for test data cleanup)."""
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
