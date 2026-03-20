"""Tests for platform collectors using mocked Apify responses."""

from __future__ import annotations

from unittest.mock import MagicMock

from watcheye.collector.facebook import FacebookCollector
from watcheye.collector.instagram import InstagramCollector
from watcheye.collector.reddit import RedditCollector
from watcheye.collector.x_twitter import XTwitterCollector
from watcheye.collector.xiaohongshu import XiaohongshuCollector


def _mock_apify(return_items: list[dict]) -> MagicMock:
    """Create a mock ApifyCollector that returns given items."""
    apify = MagicMock()
    apify.run_actor.return_value = return_items
    return apify


# --- Instagram ---

class TestInstagramCollector:
    def test_parse_image_post(self):
        item = {
            "id": "ig_123",
            "shortCode": "ABC123",
            "displayUrl": "https://example.com/img.jpg",
            "caption": "New product launch!",
            "type": "Image",
            "timestamp": "2025-12-01T10:00:00",
            "likesCount": 500,
            "commentsCount": 42,
            "videoViewCount": 0,
            "ownerFollowerCount": 100000,
        }
        apify = _mock_apify([item])
        collector = InstagramCollector(apify, "apify/instagram-scraper")
        posts = collector.collect("testaccount", limit=10)

        assert len(posts) == 1
        post = posts[0]
        assert post.platform == "instagram"
        assert post.platform_id == "ig_123"
        assert post.likes == 500
        assert post.comments == 42
        assert post.post_type == "image"
        assert "https://example.com/img.jpg" in post.media_urls
        assert post.followers_at_time == 100000

    def test_parse_video_post(self):
        item = {
            "id": "ig_456",
            "type": "Video",
            "videoUrl": "https://example.com/video.mp4",
            "caption": "Watch this!",
            "likesCount": 1200,
            "commentsCount": 88,
            "videoViewCount": 50000,
        }
        apify = _mock_apify([item])
        collector = InstagramCollector(apify, "apify/instagram-scraper")
        posts = collector.collect("testaccount")

        assert posts[0].post_type == "video"
        assert posts[0].views == 50000
        assert "https://example.com/video.mp4" in posts[0].media_urls

    def test_parse_carousel_post(self):
        item = {
            "id": "ig_789",
            "type": "Sidecar",
            "images": ["https://example.com/1.jpg", "https://example.com/2.jpg"],
            "caption": "Carousel post",
            "likesCount": 300,
            "commentsCount": 15,
        }
        apify = _mock_apify([item])
        collector = InstagramCollector(apify, "apify/instagram-scraper")
        posts = collector.collect("testaccount")

        assert posts[0].post_type == "carousel"
        assert len(posts[0].media_urls) == 2

    def test_empty_response(self):
        apify = _mock_apify([])
        collector = InstagramCollector(apify, "apify/instagram-scraper")
        posts = collector.collect("testaccount")
        assert posts == []

    def test_run_actor_called_with_correct_input(self):
        apify = _mock_apify([])
        collector = InstagramCollector(apify, "apify/instagram-scraper")
        collector.collect("herschel", limit=25)
        apify.run_actor.assert_called_once_with(
            "apify/instagram-scraper",
            {
                "directUrls": ["https://www.instagram.com/herschel/"],
                "resultsType": "posts",
                "resultsLimit": 25,
            },
        )


# --- Facebook ---

class TestFacebookCollector:
    def test_parse_image_post(self):
        item = {
            "postId": "fb_123",
            "postUrl": "https://facebook.com/post/123",
            "text": "Check out our new bags!",
            "imageUrl": "https://example.com/fb.jpg",
            "time": "2025-11-15T08:30:00",
            "likesCount": 800,
            "commentsCount": 60,
            "sharesCount": 25,
        }
        apify = _mock_apify([item])
        collector = FacebookCollector(apify, "apify/facebook-posts-scraper")
        posts = collector.collect("TestBrand")

        post = posts[0]
        assert post.platform == "facebook"
        assert post.platform_id == "fb_123"
        assert post.likes == 800
        assert post.shares == 25
        assert "https://example.com/fb.jpg" in post.media_urls

    def test_parse_video_post(self):
        item = {
            "postId": "fb_456",
            "videoUrl": "https://example.com/fb_video.mp4",
            "text": "Video post",
            "likesCount": 200,
            "commentsCount": 10,
            "sharesCount": 5,
        }
        apify = _mock_apify([item])
        collector = FacebookCollector(apify, "apify/facebook-posts-scraper")
        posts = collector.collect("TestBrand")

        assert posts[0].post_type == "video"


# --- X/Twitter ---

class TestXTwitterCollector:
    def test_parse_tweet(self):
        item = {
            "id_str": "tw_789",
            "full_text": "Explore with our travel backpack #adventure",
            "created_at": "2025-10-20T14:00:00",
            "favorite_count": 350,
            "reply_count": 20,
            "retweet_count": 45,
            "bookmark_count": 12,
            "views_count": 8000,
            "media": [{"url": "https://example.com/tw.jpg", "type": "photo"}],
            "user": {"followers_count": 50000},
        }
        apify = _mock_apify([item])
        collector = XTwitterCollector(apify, "apidojo/twitter-scraper-v2")
        posts = collector.collect("testbrand")

        post = posts[0]
        assert post.platform == "x_twitter"
        assert post.platform_id == "tw_789"
        assert post.likes == 350
        assert post.shares == 45
        assert post.saves == 12
        assert post.followers_at_time == 50000

    def test_parse_video_tweet(self):
        item = {
            "id_str": "tw_video",
            "text": "Video tweet",
            "media": [{"url": "https://example.com/tw_v.mp4", "type": "video"}],
            "favorite_count": 100,
            "reply_count": 5,
            "retweet_count": 10,
        }
        apify = _mock_apify([item])
        collector = XTwitterCollector(apify, "apidojo/twitter-scraper-v2")
        posts = collector.collect("testbrand")

        assert posts[0].post_type == "video"


# --- Xiaohongshu ---

class TestXiaohongshuCollector:
    def test_parse_note(self):
        item = {
            "noteId": "xhs_001",
            "title": "好用嘅背包推介",
            "content": "呢個背包真係好正",
            "url": "https://xiaohongshu.com/note/001",
            "type": "image",
            "publishTime": "2025-09-10T12:00:00",
            "likeCount": 2000,
            "commentCount": 150,
            "shareCount": 80,
            "collectCount": 300,
            "images": ["https://example.com/xhs1.jpg", "https://example.com/xhs2.jpg"],
        }
        apify = _mock_apify([item])
        collector = XiaohongshuCollector(apify, "epctex/xiaohongshu-scraper")
        posts = collector.collect("user123")

        post = posts[0]
        assert post.platform == "xiaohongshu"
        assert post.platform_id == "xhs_001"
        assert post.likes == 2000
        assert post.saves == 300
        assert len(post.media_urls) == 2

    def test_parse_images_as_dicts(self):
        item = {
            "noteId": "xhs_002",
            "title": "",
            "content": "",
            "images": [{"url": "https://example.com/xhs3.jpg"}],
            "likeCount": 10,
            "commentCount": 1,
            "shareCount": 0,
            "collectCount": 2,
        }
        apify = _mock_apify([item])
        collector = XiaohongshuCollector(apify, "epctex/xiaohongshu-scraper")
        posts = collector.collect("user456")

        assert len(posts[0].media_urls) == 1


# --- Reddit ---

class TestRedditCollector:
    def test_parse_image_post(self):
        item = {
            "id": "reddit_001",
            "title": "Just got my new backpack!",
            "selftext": "It's amazing for daily commute",
            "permalink": "/r/bags/comments/abc/new_backpack/",
            "thumbnail": "https://example.com/thumb.jpg",
            "url": "https://example.com/full.jpg",
            "created_utc": 1700000000,
            "ups": 420,
            "num_comments": 35,
        }
        apify = _mock_apify([item])
        collector = RedditCollector(apify, "trudax/reddit-scraper")
        posts = collector.collect("testuser")

        post = posts[0]
        assert post.platform == "reddit"
        assert post.platform_id == "reddit_001"
        assert post.likes == 420
        assert post.comments == 35
        assert post.post_type == "image"
        assert len(post.media_urls) == 2  # thumbnail + full image

    def test_parse_text_post(self):
        item = {
            "id": "reddit_002",
            "title": "Discussion: best bags for travel",
            "selftext": "What do you recommend?",
            "permalink": "/r/bags/comments/def/discussion/",
            "ups": 50,
            "num_comments": 80,
        }
        apify = _mock_apify([item])
        collector = RedditCollector(apify, "trudax/reddit-scraper")
        posts = collector.collect("testuser")

        assert posts[0].post_type == "text"
        assert posts[0].media_urls == []
