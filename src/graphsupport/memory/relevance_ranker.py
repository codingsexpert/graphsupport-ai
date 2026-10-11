"""Deterministic relevance ranker for customer support history (Phase 4).

Scores and orders support tickets using explainable, deterministic criteria:
active status, explicit ticket/product references, keyword similarity,
recency, and diagnostic attempt history.
"""

import logging
import re
from datetime import UTC, datetime

from graphsupport.graph.models import TicketStatus, TroubleshootingOutcome
from graphsupport.memory.history_retriever import RawTicketRecord
from graphsupport.memory.models import RankedTicketContext

logger = logging.getLogger("graphsupport.memory.relevance_ranker")

WORD_REGEX = re.compile(r"\b[a-zA-Z0-9_-]{3,}\b")


class RelevanceRanker:
    """Ranks support tickets based on deterministic, explainable criteria."""

    def rank_tickets(
        self,
        ticket_records: list[RawTicketRecord],
        queried_ticket_id: str | None = None,
        queried_product_id: str | None = None,
        issue_query: str | None = None,
        customer_product_ids: set[str] | None = None,
    ) -> list[RankedTicketContext]:
        """Score and sort raw ticket records into RankedTicketContext objects.

        Args:
            ticket_records: Raw ticket records from history retriever.
            queried_ticket_id: Optional target ticket reference.
            queried_product_id: Optional target product reference.
            issue_query: Optional search text / defect keywords.
            customer_product_ids: Set of product IDs owned/used by customer.

        Returns:
            List of RankedTicketContext sorted by relevance score descending.
        """
        user_products = customer_product_ids or set()
        query_tokens = self._extract_tokens(issue_query) if issue_query else set()
        ranked_list: list[RankedTicketContext] = []

        for record in ticket_records:
            score = 0.0
            reasons: list[str] = []
            tkt = record.ticket

            # 1. Explicit Ticket ID Match (+30.0)
            if queried_ticket_id and tkt.id == queried_ticket_id:
                score += 30.0
                reasons.append("explicit_ticket_match (+30.0)")

            # 2. Active Unresolved Status
            if tkt.status == TicketStatus.IN_PROGRESS:
                score += 15.0
                reasons.append("status_in_progress (+15.0)")
            elif tkt.status == TicketStatus.OPEN:
                score += 12.0
                reasons.append("status_open (+12.0)")
            elif tkt.status == TicketStatus.RESOLVED:
                score += 3.0
                reasons.append("status_resolved (+3.0)")
            elif tkt.status == TicketStatus.CLOSED:
                score += 1.0
                reasons.append("status_closed (+1.0)")

            # 3. Product Match
            tkt_pid = tkt.product_id or (record.product.id if record.product else None)
            if queried_product_id and tkt_pid == queried_product_id:
                score += 10.0
                reasons.append("queried_product_match (+10.0)")
            elif tkt_pid and tkt_pid in user_products:
                score += 3.0
                reasons.append("customer_product_match (+3.0)")

            # 4. Issue Keyword Similarity (up to +15.0)
            if query_tokens:
                text_corpus = f"{tkt.title} {tkt.description}"
                if record.issue:
                    text_corpus += f" {record.issue.title} {record.issue.description}"
                target_tokens = self._extract_tokens(text_corpus)
                overlap = query_tokens.intersection(target_tokens)
                if overlap:
                    token_boost = min(15.0, len(overlap) * 5.0)
                    score += token_boost
                    reasons.append(
                        f"issue_keyword_match:{len(overlap)}_tokens (+{token_boost:.1f})"
                    )

            # 5. Recency Boost
            ref_time = tkt.updated_at or tkt.created_at
            now = datetime.now(UTC)
            age_days = (now - ref_time).total_seconds() / 86400.0 if ref_time else 999.0
            if age_days <= 1.0:
                score += 6.0
                reasons.append("recency_within_24h (+6.0)")
            elif age_days <= 7.0:
                score += 4.0
                reasons.append("recency_within_7d (+4.0)")
            elif age_days <= 30.0:
                score += 2.0
                reasons.append("recency_within_30d (+2.0)")
            else:
                score += 0.5
                reasons.append("recency_older_30d (+0.5)")

            # 6. Diagnostic Attempt Status Weight
            has_failed = any(a.outcome == TroubleshootingOutcome.FAILED for a in record.attempts)
            has_partial = any(a.outcome == TroubleshootingOutcome.PARTIAL for a in record.attempts)
            if has_failed:
                score += 4.0
                reasons.append("has_failed_attempts (+4.0)")
            elif has_partial:
                score += 2.0
                reasons.append("has_partial_attempts (+2.0)")

            ranked_list.append(
                RankedTicketContext(
                    ticket=tkt,
                    relevance_score=round(score, 2),
                    ranking_reasons=reasons,
                    product=record.product,
                    issue=record.issue,
                    troubleshooting_attempts=record.attempts,
                    resolutions=record.resolutions,
                    related_messages=record.related_messages,
                )
            )

        # Deterministic sorting: score DESC, creation DESC, id ASC
        ranked_list.sort(
            key=lambda item: (
                -item.relevance_score,
                -item.ticket.created_at.timestamp(),
                item.ticket.id,
            )
        )
        return ranked_list

    @staticmethod
    def _extract_tokens(text: str | None) -> set[str]:
        """Extract lowercase alphanumeric tokens of length >= 3."""
        if not text:
            return set()
        matches = WORD_REGEX.findall(text.lower())
        return set(matches)
