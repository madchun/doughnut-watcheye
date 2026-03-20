"""Tests for engagement scoring logic."""

from datetime import datetime, timezone, timedelta

from watcheye.config import ScoringConfig
from watcheye.scorer.engagement import EngagementScorer
from watcheye.storage.models import ContentItem


def _make_item(**kwargs) -> ContentItem:
    """Create a ContentItem with defaults for testing."""
    defaults = {
        "brand_id": 1,
        "platform": "instagram",
        "platform_id": "test_123",
        "account_handle": "test_account",
        "likes": 100,
        "comments": 10,
        "shares": 5,
        "saves": 8,
        "views": 1000,
        "followers_at_time": 10000,
        "posted_at": datetime.now(timezone.utc),
    }
    defaults.update(kwargs)
    return ContentItem(**defaults)


def test_raw_score():
    """Test weighted raw score calculation."""
    config = ScoringConfig()
    scorer = EngagementScorer(config)
    item = _make_item(likes=100, comments=10, shares=5, saves=8)

    score = scorer.raw_score(item)
    expected = 100 * 1.0 + 10 * 3.0 + 5 * 5.0 + 8 * 4.0
    assert score == expected


def test_engagement_rate():
    """Test engagement rate calculation."""
    config = ScoringConfig()
    scorer = EngagementScorer(config)
    item = _make_item(likes=100, comments=10, shares=5, saves=8, followers_at_time=10000)

    rate = scorer.engagement_rate(item)
    assert rate is not None
    assert rate == (100 + 10 + 5 + 8) / 10000


def test_engagement_rate_no_followers():
    """Test engagement rate when followers unknown."""
    config = ScoringConfig()
    scorer = EngagementScorer(config)
    item = _make_item(followers_at_time=None)

    assert scorer.engagement_rate(item) is None


def test_engagement_rate_zero_followers():
    """Test engagement rate when followers is zero."""
    config = ScoringConfig()
    scorer = EngagementScorer(config)
    item = _make_item(followers_at_time=0)

    assert scorer.engagement_rate(item) is None


def test_velocity_score_recent():
    """Test velocity bonus for recent posts."""
    config = ScoringConfig(velocity_bonus_hours=24, velocity_bonus_multiplier=1.5)
    scorer = EngagementScorer(config)
    item = _make_item(posted_at=datetime.now(timezone.utc) - timedelta(hours=2))

    assert scorer.velocity_score(item) == 1.5


def test_velocity_score_old():
    """Test no velocity bonus for old posts."""
    config = ScoringConfig(velocity_bonus_hours=24, velocity_bonus_multiplier=1.5)
    scorer = EngagementScorer(config)
    item = _make_item(posted_at=datetime.now(timezone.utc) - timedelta(days=7))

    assert scorer.velocity_score(item) == 1.0


def test_velocity_score_no_date():
    """Test velocity score when post date unknown."""
    config = ScoringConfig()
    scorer = EngagementScorer(config)
    item = _make_item(posted_at=None)

    assert scorer.velocity_score(item) == 1.0


def test_custom_weights():
    """Test scoring with custom weights."""
    config = ScoringConfig(weights={"likes": 2.0, "comments": 5.0, "shares": 10.0, "saves": 8.0})
    scorer = EngagementScorer(config)
    item = _make_item(likes=50, comments=5, shares=2, saves=3)

    score = scorer.raw_score(item)
    expected = 50 * 2.0 + 5 * 5.0 + 2 * 10.0 + 3 * 8.0
    assert score == expected
