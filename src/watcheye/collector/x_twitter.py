"""X/Twitter collector using Apify."""

from __future__ import annotations

from datetime import datetime

from watcheye.collector.apify_client import ApifyCollector
from watcheye.collector.base import BaseCollector, RawPost


class XTwitterCollector(BaseCollector):
    """Collect X/Twitter posts via Apify scraper."""

    def __init__(self, apify: ApifyCollector, actor_id: str = "apidojo/twitter-scraper-v2"):
        self.apify = apify
        self.actor_id = actor_id

    @property
    def platform_name(self) -> str:
        return "x_twitter"

    def collect(self, account: str, limit: int = 50) -> list[RawPost]:
        run_input = {
            "handle": [account],
            "tweetsDesired": limit,
            "mode": "user",
        }
        items = self.apify.run_actor(self.actor_id, run_input)
        return [self._parse_item(item, account) for item in items]

    def _parse_item(self, item: dict, account: str) -> RawPost:
        media_urls = []
        for media in item.get("media", []):
            if isinstance(media, dict) and media.get("url"):
                media_urls.append(media["url"])

        posted_at = None
        if item.get("created_at"):
            try:
                posted_at = datetime.fromisoformat(item["created_at"])
            except (ValueError, TypeError):
                pass

        return RawPost(
            platform="x_twitter",
            platform_id=item.get("id_str", item.get("id", "")),
            account_handle=account,
            url=f"https://x.com/{account}/status/{item.get('id_str', '')}",
            caption=item.get("full_text", item.get("text", "")) or "",
            post_type="video" if any(
                m.get("type") == "video" for m in item.get("media", []) if isinstance(m, dict)
            ) else "image",
            posted_at=posted_at,
            likes=item.get("favorite_count", 0) or 0,
            comments=item.get("reply_count", 0) or 0,
            shares=item.get("retweet_count", 0) or 0,
            saves=item.get("bookmark_count", 0) or 0,
            views=item.get("views_count", 0) or 0,
            followers_at_time=item.get("user", {}).get("followers_count"),
            media_urls=media_urls,
            raw_data=item,
        )
