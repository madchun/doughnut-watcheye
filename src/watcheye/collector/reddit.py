"""Reddit collector using Apify."""

from __future__ import annotations

from datetime import datetime

from watcheye.collector.apify_client import ApifyCollector
from watcheye.collector.base import BaseCollector, RawPost


class RedditCollector(BaseCollector):
    """Collect Reddit posts via Apify scraper."""

    def __init__(self, apify: ApifyCollector, actor_id: str = "trudax/reddit-scraper"):
        self.apify = apify
        self.actor_id = actor_id

    @property
    def platform_name(self) -> str:
        return "reddit"

    def collect(self, account: str, limit: int = 30) -> list[RawPost]:
        run_input = {
            "startUrls": [{"url": f"https://www.reddit.com/user/{account}"}],
            "maxItems": limit,
        }
        items = self.apify.run_actor(self.actor_id, run_input)
        return [self._parse_item(item, account) for item in items]

    def _parse_item(self, item: dict, account: str) -> RawPost:
        media_urls = []
        if item.get("thumbnail") and item["thumbnail"].startswith("http"):
            media_urls.append(item["thumbnail"])
        if item.get("url") and any(item["url"].endswith(ext) for ext in (".jpg", ".png", ".gif")):
            media_urls.append(item["url"])

        posted_at = None
        if item.get("created_utc"):
            try:
                posted_at = datetime.fromtimestamp(item["created_utc"])
            except (ValueError, TypeError, OSError):
                pass

        return RawPost(
            platform="reddit",
            platform_id=item.get("id", ""),
            account_handle=account,
            url=f"https://www.reddit.com{item.get('permalink', '')}",
            caption=item.get("title", "") + "\n" + (item.get("selftext", "") or ""),
            post_type="image" if media_urls else "text",
            posted_at=posted_at,
            likes=item.get("ups", 0) or 0,
            comments=item.get("num_comments", 0) or 0,
            shares=0,
            saves=0,
            views=0,
            media_urls=media_urls,
            raw_data=item,
        )
