"""Facebook collector using Apify."""

from __future__ import annotations

from datetime import datetime

from watcheye.collector.apify_client import ApifyCollector
from watcheye.collector.base import BaseCollector, RawPost


class FacebookCollector(BaseCollector):
    """Collect Facebook posts via Apify scraper."""

    def __init__(self, apify: ApifyCollector, actor_id: str = "apify/facebook-posts-scraper"):
        self.apify = apify
        self.actor_id = actor_id

    @property
    def platform_name(self) -> str:
        return "facebook"

    def collect(self, account: str, limit: int = 50) -> list[RawPost]:
        run_input = {
            "startUrls": [{"url": f"https://www.facebook.com/{account}"}],
            "resultsLimit": limit,
        }
        items = self.apify.run_actor(self.actor_id, run_input)
        return [self._parse_item(item, account) for item in items]

    def _parse_item(self, item: dict, account: str) -> RawPost:
        media_urls = []
        if item.get("imageUrl"):
            media_urls.append(item["imageUrl"])
        if item.get("videoUrl"):
            media_urls.append(item["videoUrl"])

        posted_at = None
        if item.get("time"):
            try:
                posted_at = datetime.fromisoformat(item["time"])
            except (ValueError, TypeError):
                pass

        return RawPost(
            platform="facebook",
            platform_id=item.get("postId", ""),
            account_handle=account,
            url=item.get("postUrl", ""),
            caption=item.get("text", "") or "",
            post_type="video" if item.get("videoUrl") else "image",
            posted_at=posted_at,
            likes=item.get("likesCount", 0) or 0,
            comments=item.get("commentsCount", 0) or 0,
            shares=item.get("sharesCount", 0) or 0,
            saves=0,
            views=item.get("videoViewCount", 0) or 0,
            media_urls=media_urls,
            raw_data=item,
        )
