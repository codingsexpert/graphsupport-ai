"""Repository for Product graph entities and (:Customer)-[:USES]->(:Product) linkages."""

import json
import logging
from typing import Any

from neo4j.exceptions import ConstraintError, Neo4jError

from graphsupport.core.exceptions import EntityNotFoundError, RepositoryError, ValidationError
from graphsupport.graph.driver import Neo4jDriverManager, get_driver_manager
from graphsupport.graph.models import Product

logger = logging.getLogger("graphsupport.graph.repositories.product")


class ProductRepository:
    """Repository handling persistence, retrieval, and customer linkage for (:Product) nodes."""

    def __init__(
        self,
        driver_manager: Neo4jDriverManager | None = None,
        database: str | None = None,
    ) -> None:
        self.driver_manager = driver_manager or get_driver_manager()
        self.database = database or self.driver_manager.settings.neo4j_database

    def upsert_product(self, product: Product) -> Product:
        """Create or update a Product node using parameterized Cypher MERGE."""
        logger.debug("Upserting product node (ID: %s, SKU: %s)...", product.id, product.sku)
        query = """
        MERGE (p:Product {id: $id})
        ON CREATE SET
            p.name = $name,
            p.sku = $sku,
            p.category = $category,
            p.version = $version,
            p.metadata = $metadata
        ON MATCH SET
            p.name = $name,
            p.sku = $sku,
            p.category = $category,
            p.version = $version,
            p.metadata = $metadata
        RETURN p.id AS id, p.name AS name, p.sku AS sku, p.category AS category,
               p.version AS version, p.metadata AS metadata
        """
        params = {
            "id": product.id,
            "name": product.name,
            "sku": product.sku,
            "category": product.category,
            "version": product.version,
            "metadata": json.dumps(product.metadata),
        }
        try:
            with self.driver_manager.session(database=self.database) as session:
                record = session.run(query, params).single()
                if not record:
                    raise RepositoryError(f"Failed to upsert product {product.id}")
                return self._record_to_product(record)
        except ConstraintError as err:
            raise RepositoryError(f"Product constraint violation: {err.message}") from err
        except Neo4jError as err:
            raise RepositoryError(f"Database error during product upsert: {err.message}") from err
        except Exception as err:
            raise RepositoryError(f"Unexpected error during product upsert: {err}") from err

    def get_by_id(self, product_id: str) -> Product | None:
        """Retrieve a Product by ID."""
        query = """
        MATCH (p:Product {id: $id})
        RETURN p.id AS id, p.name AS name, p.sku AS sku, p.category AS category,
               p.version AS version, p.metadata AS metadata
        """
        try:
            with self.driver_manager.session(database=self.database) as session:
                record = session.run(query, {"id": product_id}).single()
                if not record:
                    return None
                return self._record_to_product(record)
        except Exception as err:
            raise RepositoryError(f"Failed to retrieve product by ID: {err}") from err

    def get_by_sku(self, sku: str) -> Product | None:
        """Retrieve a Product by SKU."""
        clean_sku = sku.strip()
        query = """
        MATCH (p:Product {sku: $sku})
        RETURN p.id AS id, p.name AS name, p.sku AS sku, p.category AS category,
               p.version AS version, p.metadata AS metadata
        """
        try:
            with self.driver_manager.session(database=self.database) as session:
                record = session.run(query, {"sku": clean_sku}).single()
                if not record:
                    return None
                return self._record_to_product(record)
        except Exception as err:
            raise RepositoryError(f"Failed to retrieve product by SKU: {err}") from err

    def list_products(self, limit: int = 50, skip: int = 0) -> list[Product]:
        """List products with pagination and deterministic ordering."""
        if limit < 1 or limit > 500:
            raise ValidationError(f"Limit must be between 1 and 500, got {limit}")
        if skip < 0:
            raise ValidationError(f"Skip cannot be negative, got {skip}")

        query = """
        MATCH (p:Product)
        RETURN p.id AS id, p.name AS name, p.sku AS sku, p.category AS category,
               p.version AS version, p.metadata AS metadata
        ORDER BY p.name ASC, p.id ASC
        SKIP $skip
        LIMIT $limit
        """
        products: list[Product] = []
        try:
            with self.driver_manager.session(database=self.database) as session:
                result = session.run(query, {"skip": skip, "limit": limit})
                for record in result:
                    products.append(self._record_to_product(record))
            return products
        except Exception as err:
            raise RepositoryError(f"Failed to list products: {err}") from err

    def link_customer_to_product(self, customer_id: str, product_id: str) -> bool:
        """Link a customer to a product via (:Customer)-[:USES]->(:Product).

        Idempotent; does not duplicate relationships if already linked.
        """
        logger.debug("Linking customer %s to product %s (:USES)...", customer_id, product_id)
        query = """
        MATCH (c:Customer {id: $customer_id})
        MATCH (p:Product {id: $product_id})
        MERGE (c)-[r:USES]->(p)
        RETURN count(r) AS linked
        """
        try:
            with self.driver_manager.session(database=self.database) as session:
                result = session.run(query, {"customer_id": customer_id, "product_id": product_id})
                record = result.single()
                if not record or record["linked"] == 0:
                    # Determine which entity was missing
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

                    p_exists = bool(
                        session.run(
                            "MATCH (p:Product {id: $id}) RETURN count(p) > 0 AS ex",
                            {"id": product_id},
                        ).single()["ex"]
                    )
                    if not p_exists:
                        raise EntityNotFoundError(f"Product with ID '{product_id}' does not exist")

                return True
        except EntityNotFoundError:
            raise
        except Exception as err:
            raise RepositoryError(f"Failed to link customer to product: {err}") from err

    def get_customer_products(self, customer_id: str) -> list[Product]:
        """Retrieve all products associated with a customer."""
        query = """
        MATCH (c:Customer {id: $customer_id})-[:USES]->(p:Product)
        RETURN p.id AS id, p.name AS name, p.sku AS sku, p.category AS category,
               p.version AS version, p.metadata AS metadata
        ORDER BY p.name ASC, p.id ASC
        """
        products: list[Product] = []
        try:
            with self.driver_manager.session(database=self.database) as session:
                result = session.run(query, {"customer_id": customer_id})
                for record in result:
                    products.append(self._record_to_product(record))
            return products
        except Exception as err:
            raise RepositoryError(f"Failed to fetch customer products: {err}") from err

    def delete_by_id(self, product_id: str) -> bool:
        """Delete an exact product record by ID (used for test data cleanup)."""
        query = """
        MATCH (p:Product {id: $id})
        DETACH DELETE p
        RETURN count(p) AS deleted_count
        """
        try:
            with self.driver_manager.session(database=self.database) as session:
                result = session.run(query, {"id": product_id}).single()
                return bool(result and result["deleted_count"] > 0)
        except Exception as err:
            raise RepositoryError(f"Failed to delete product {product_id}: {err}") from err

    @staticmethod
    def _record_to_product(record: Any) -> Product:
        """Parse Cypher record map into a validated Product entity."""
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

        return Product(
            id=record["id"],
            name=record["name"],
            sku=record["sku"],
            category=record.get("category", "general"),
            version=record.get("version", "1.0.0"),
            metadata=metadata,
        )
