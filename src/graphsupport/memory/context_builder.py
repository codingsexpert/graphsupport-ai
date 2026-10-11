"""Context builder compiling structured, bounded customer graph memory (Phase 4).

Transforms retrieved raw graph records and ranked ticket collections into
a bounded, serializable CustomerMemoryContext with missing-information indicators.
"""

import logging
from datetime import UTC, datetime

from graphsupport.graph.models import TicketStatus, TroubleshootingOutcome
from graphsupport.memory.history_retriever import RawCustomerHistory
from graphsupport.memory.models import (
    CustomerMemoryContext,
    MemoryRetrievalMetadata,
    RankedTicketContext,
    RetrievalLimits,
)
from graphsupport.memory.relevance_ranker import RelevanceRanker

logger = logging.getLogger("graphsupport.memory.context_builder")


class ContextBuilder:
    """Transforms raw graph records into a structured, bounded memory context."""

    def __init__(self, ranker: RelevanceRanker | None = None) -> None:
        self.ranker = ranker or RelevanceRanker()

    def build_memory_context(
        self,
        raw_history: RawCustomerHistory,
        queried_product_id: str | None = None,
        queried_ticket_id: str | None = None,
        issue_query: str | None = None,
        limits: RetrievalLimits | None = None,
    ) -> CustomerMemoryContext:
        """Construct bounded CustomerMemoryContext from raw customer history.

        Args:
            raw_history: Raw entities from HistoryRetriever.
            queried_product_id: Optional queried product reference.
            queried_ticket_id: Optional queried ticket reference.
            issue_query: Optional search keyword or description.
            limits: Bounding configuration limits.

        Returns:
            Validated, serializable CustomerMemoryContext.
        """
        active_limits = limits or RetrievalLimits()
        customer_product_ids = {p.id for p in raw_history.products}

        # 1. Rank tickets deterministically
        ranked_tickets = self.ranker.rank_tickets(
            ticket_records=raw_history.ticket_records,
            queried_ticket_id=queried_ticket_id,
            queried_product_id=queried_product_id,
            issue_query=issue_query,
            customer_product_ids=customer_product_ids,
        )

        # 2. Apply bounded ticket limits
        bounded_tickets: list[RankedTicketContext] = []
        for ranked in ranked_tickets[: active_limits.max_tickets]:
            bounded_attempts = ranked.troubleshooting_attempts[
                : active_limits.max_attempts_per_ticket
            ]
            bounded_resolutions = ranked.resolutions[: active_limits.max_resolutions_per_ticket]
            bounded_tickets.append(
                RankedTicketContext(
                    ticket=ranked.ticket,
                    relevance_score=ranked.relevance_score,
                    ranking_reasons=ranked.ranking_reasons,
                    product=ranked.product,
                    issue=ranked.issue,
                    troubleshooting_attempts=bounded_attempts,
                    resolutions=bounded_resolutions,
                    related_messages=ranked.related_messages,
                )
            )

        # 3. Detect missing or unknown information indicators
        missing_indicators = self._detect_missing_information(
            raw_history=raw_history,
            bounded_tickets=bounded_tickets,
        )

        # 4. Total diagnostic attempts count across all records
        total_attempts = sum(len(tr.attempts) for tr in raw_history.ticket_records)

        # 5. Build retrieval metadata
        metadata = MemoryRetrievalMetadata(
            queried_customer_id=raw_history.customer.id,
            queried_product_id=queried_product_id,
            queried_ticket_id=queried_ticket_id,
            issue_query=issue_query,
            retrieved_at=datetime.now(UTC),
            total_tickets_found=len(raw_history.ticket_records),
            tickets_included=len(bounded_tickets),
            total_attempts_found=total_attempts,
            total_conversations_found=len(raw_history.conversations),
        )

        # 6. Bound conversations
        bounded_conversations = raw_history.conversations[: active_limits.max_conversations]

        return CustomerMemoryContext(
            customer=raw_history.customer,
            products=raw_history.products,
            ranked_tickets=bounded_tickets,
            recent_conversations=bounded_conversations,
            retrieval_metadata=metadata,
            missing_information=missing_indicators,
        )

    @staticmethod
    def _detect_missing_information(
        raw_history: RawCustomerHistory,
        bounded_tickets: list[RankedTicketContext],
    ) -> list[str]:
        """Produce deterministic indicators of missing facts and open states."""
        indicators: list[str] = []

        if not raw_history.products:
            indicators.append("customer_has_no_registered_products")

        if not raw_history.ticket_records:
            indicators.append("no_support_tickets_found")
        else:
            has_active = any(
                r.ticket.status in (TicketStatus.OPEN, TicketStatus.IN_PROGRESS)
                for r in raw_history.ticket_records
            )
            if not has_active:
                indicators.append("no_active_open_tickets")

        # Ticket-level indicators
        for rt in bounded_tickets:
            tid = rt.ticket.id
            if not rt.troubleshooting_attempts:
                indicators.append(f"ticket_{tid}_has_no_troubleshooting_attempts")
            else:
                failed_steps = [
                    s.step_number
                    for s in rt.troubleshooting_attempts
                    if s.outcome == TroubleshootingOutcome.FAILED
                ]
                for snum in failed_steps:
                    indicators.append(f"ticket_{tid}_has_failed_attempt_step_{snum}")

            if rt.ticket.status in (TicketStatus.OPEN, TicketStatus.IN_PROGRESS):
                indicators.append(f"ticket_{tid}_unresolved")

            if rt.resolutions:
                indicators.append(f"ticket_{tid}_has_recorded_resolution")

        return indicators
