"""Abstract collector interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RawPost:
    """Unified post schema from any platform."""
    platform: str
    platform_id: str
    account_handle: str
    url: str = ""
    caption: str = ""
    post_type: str = ""  # image, video, carousel, reel
    posted_at: datetime | None = None
    likes: int = 0
    comments: int = 0
    shares: int = 0
    saves: int = 0
    views: int = 0
    followers_at_time: int | None = None
    media_urls: list[str] = field(default_factory=list)
    raw_data: dict = field(default_factory=dict)


class BaseCollector(ABC):
    """Abstract base for platform-specific collectors."""

    @abstractmethod
    def collect(self, account: str, limit: int = 50) -> list[RawPost]:
        """Collect posts from a social media account."""
        ...

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Return the platform identifier."""
        ...
