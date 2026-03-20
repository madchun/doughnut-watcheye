"""Instagram collector using Apify."""

from __future__ import annotations

from datetime import datetime

from watcheye.collector.apify_client import ApifyCollector
from watcheye.collector.base import BaseCollector, RawPost


class InstagramCollector(BaseCollector):
    """Collect Instagram posts via Apify scraper."""

    def __init__(self, apify: ApifyCollector, actor_id: str = "apify/instagram-scraper"):
        self.apify = apify
        self.actor_id = actor_id

    @property
    def platform_name(self) -> str:
        return "instagram"

    def collect(self, account: str, limit: int = 50) -> list[RawPost]:
        run_input = {
            "directUrls": [f"https://www.instagram.com/{account}/"],
            "resultsType": "posts",
            "resultsLimit": limit,
        }
        items = self.apify.run_actor(self.actor_id, run_input)
        return [self._parse_item(item, account) for item in items]

    def _parse_item(self, item: dict, account: str) -> RawPost:
        media_urls = []
        if item.get("displayUrl"):
            media_urls.append(item["displayUrl"])
        if item.get("images"):
            media_urls.extend(item["images"])
        if item.get("videoUrl"):
            media_urls.append(item["videoUrl"])

        posted_at = None
        if item.get("timestamp"):
            try:
                posted_at = datetime.fromisoformat(item["timestamp"])
            except (ValueError, TypeError):
                pass

        post_type = "image"
        if item.get("type") == "Video":
            post_type = "video"
        elif item.get("type") == "Sidecar":
            post_type = "carousel"

        return RawPost(
            platform="instagram",
            platform_id=item.get("id", item.get("shortCode", "")),
            account_handle=account,
            url=item.get("url", f"https://www.instagram.com/p/{item.get('shortCode', '')}/"),
            caption=item.get("caption", "") or "",
            post_type=post_type,
            posted_at=posted_at,
            likes=item.get("likesCount", 0) or 0,
            comments=item.get("commentsCount", 0) or 0,
            shares=0,
            saves=0,
            views=item.get("videoViewCount", 0) or 0,
            followers_at_time=item.get("ownerFollowerCount"),
            media_urls=media_urls,
            raw_data=item,
        )
