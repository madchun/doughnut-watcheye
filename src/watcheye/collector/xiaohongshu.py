"""Xiaohongshu (小紅書) collector using Apify."""

from __future__ import annotations

from datetime import datetime

from watcheye.collector.apify_client import ApifyCollector
from watcheye.collector.base import BaseCollector, RawPost


class XiaohongshuCollector(BaseCollector):
    """Collect Xiaohongshu posts via Apify scraper."""

    def __init__(self, apify: ApifyCollector, actor_id: str = "epctex/xiaohongshu-scraper"):
        self.apify = apify
        self.actor_id = actor_id

    @property
    def platform_name(self) -> str:
        return "xiaohongshu"

    def collect(self, account: str, limit: int = 30) -> list[RawPost]:
        run_input = {
            "userUrls": [f"https://www.xiaohongshu.com/user/profile/{account}"],
            "maxItems": limit,
        }
        items = self.apify.run_actor(self.actor_id, run_input)
        return [self._parse_item(item, account) for item in items]

    def _parse_item(self, item: dict, account: str) -> RawPost:
        media_urls = []
        for img in item.get("images", []):
            if isinstance(img, str):
                media_urls.append(img)
            elif isinstance(img, dict) and img.get("url"):
                media_urls.append(img["url"])

        posted_at = None
        if item.get("publishTime"):
            try:
                posted_at = datetime.fromisoformat(item["publishTime"])
            except (ValueError, TypeError):
                pass

        return RawPost(
            platform="xiaohongshu",
            platform_id=item.get("noteId", item.get("id", "")),
            account_handle=account,
            url=item.get("url", ""),
            caption=item.get("title", "") + "\n" + item.get("content", ""),
            post_type=item.get("type", "image"),
            posted_at=posted_at,
            likes=item.get("likeCount", 0) or 0,
            comments=item.get("commentCount", 0) or 0,
            shares=item.get("shareCount", 0) or 0,
            saves=item.get("collectCount", 0) or 0,
            media_urls=media_urls,
            raw_data=item,
        )
