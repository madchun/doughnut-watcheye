"""Engagement scoring logic."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from watcheye.config import ScoringConfig
from watcheye.storage.models import ContentItem


class EngagementScorer:
    """Score content items based on engagement metrics."""

    def __init__(self, config: ScoringConfig):
        self.config = config

    def raw_score(self, item: ContentItem) -> float:
        """Weighted sum of engagement metrics."""
        w = self.config.weights
        return (
            item.likes * w.get("likes", 1.0)
            + item.comments * w.get("comments", 3.0)
            + item.shares * w.get("shares", 5.0)
            + item.saves * w.get("saves", 4.0)
        )

    def engagement_rate(self, item: ContentItem) -> float | None:
        """Engagement rate = total interactions / followers."""
        if not item.followers_at_time or item.followers_at_time == 0:
            return None
        total = item.likes + item.comments + item.shares + item.saves
        return total / item.followers_at_time

    def velocity_score(self, item: ContentItem) -> float:
        """Bonus for high engagement within short time window."""
        if not item.posted_at:
            return 1.0
        now = datetime.now(timezone.utc)
        posted = item.posted_at
        if posted.tzinfo is None:
            posted = posted.replace(tzinfo=timezone.utc)
        hours_since = (now - posted).total_seconds() / 3600
        if hours_since <= self.config.velocity_bonus_hours:
            return self.config.velocity_bonus_multiplier
        return 1.0

    def normalize_within_account(
        self, session: Session, item: ContentItem, raw: float
    ) -> float:
        """Normalize score 0-100 relative to same account's history."""
        stmt = select(ContentItem).where(
            ContentItem.account_handle == item.account_handle,
            ContentItem.platform == item.platform,
        )
        peers = session.execute(stmt).scalars().all()

        if len(peers) <= 1:
            return 50.0

        scores = [self.raw_score(p) for p in peers]
        max_score = max(scores)
        min_score = min(scores)

        if max_score == min_score:
            return 50.0

        return ((raw - min_score) / (max_score - min_score)) * 100

    def score_item(self, session: Session, item: ContentItem) -> None:
        """Calculate and set all scores on a content item."""
        raw = self.raw_score(item)
        item.engagement_score = raw
        item.engagement_rate = self.engagement_rate(item)
        item.velocity_score = self.velocity_score(item)

        normalized = self.normalize_within_account(session, item, raw)
        item.final_score = normalized * (item.velocity_score or 1.0)
        # Cap at 100
        item.final_score = min(item.final_score, 100.0)

    def score_all(self, session: Session) -> int:
        """Score all unscored or re-score all content items. Returns count."""
        stmt = select(ContentItem)
        items = session.execute(stmt).scalars().all()
        for item in items:
            self.score_item(session, item)
        return len(items)
