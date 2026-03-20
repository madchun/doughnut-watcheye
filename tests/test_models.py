"""Tests for database models."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from watcheye.storage.models import Base, Brand, ContentItem, ContentMedia, Tag, ContentTag


def _setup_db():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def test_create_brand():
    """Test creating a brand."""
    engine = _setup_db()
    with Session(engine) as session:
        brand = Brand(name="TestBrand", category="direct_competitors")
        session.add(brand)
        session.commit()

        result = session.query(Brand).first()
        assert result.name == "TestBrand"
        assert result.category == "direct_competitors"


def test_create_content_item():
    """Test creating a content item linked to a brand."""
    engine = _setup_db()
    with Session(engine) as session:
        brand = Brand(name="TestBrand", category="test")
        session.add(brand)
        session.flush()

        item = ContentItem(
            brand_id=brand.id,
            platform="instagram",
            platform_id="abc123",
            account_handle="testaccount",
            likes=100,
            comments=10,
        )
        session.add(item)
        session.commit()

        result = session.query(ContentItem).first()
        assert result.platform == "instagram"
        assert result.likes == 100
        assert result.brand.name == "TestBrand"


def test_content_media_relationship():
    """Test media linked to content."""
    engine = _setup_db()
    with Session(engine) as session:
        brand = Brand(name="TestBrand", category="test")
        session.add(brand)
        session.flush()

        item = ContentItem(
            brand_id=brand.id,
            platform="instagram",
            platform_id="abc123",
            account_handle="testaccount",
        )
        session.add(item)
        session.flush()

        media = ContentMedia(
            content_id=item.id,
            media_type="image",
            original_url="https://example.com/img.jpg",
        )
        session.add(media)
        session.commit()

        result = session.query(ContentItem).first()
        assert len(result.media) == 1
        assert result.media[0].original_url == "https://example.com/img.jpg"


def test_tagging():
    """Test tag and content-tag relationship."""
    engine = _setup_db()
    with Session(engine) as session:
        brand = Brand(name="TestBrand", category="test")
        session.add(brand)
        session.flush()

        item = ContentItem(
            brand_id=brand.id,
            platform="instagram",
            platform_id="abc123",
            account_handle="testaccount",
        )
        session.add(item)

        tag = Tag(name="inspiration")
        session.add(tag)
        session.flush()

        ct = ContentTag(content_id=item.id, tag_id=tag.id)
        session.add(ct)
        session.commit()

        result = session.query(ContentItem).first()
        assert len(result.tags) == 1
        assert result.tags[0].tag.name == "inspiration"


def test_unique_platform_post():
    """Test unique constraint on platform + platform_id."""
    engine = _setup_db()
    with Session(engine) as session:
        brand = Brand(name="TestBrand", category="test")
        session.add(brand)
        session.flush()

        item1 = ContentItem(
            brand_id=brand.id, platform="instagram",
            platform_id="same_id", account_handle="a",
        )
        session.add(item1)
        session.commit()

        item2 = ContentItem(
            brand_id=brand.id, platform="instagram",
            platform_id="same_id", account_handle="b",
        )
        session.add(item2)
        try:
            session.commit()
            assert False, "Should have raised IntegrityError"
        except Exception:
            session.rollback()
