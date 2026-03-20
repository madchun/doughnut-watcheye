"""SQLAlchemy models for Watcheye."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Brand(Base):
    __tablename__ = "brands"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    instagram: Mapped[str | None] = mapped_column(String(255))
    facebook: Mapped[str | None] = mapped_column(String(255))
    xiaohongshu: Mapped[str | None] = mapped_column(String(255))
    x_twitter: Mapped[str | None] = mapped_column(String(255))
    reddit: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    contents: Mapped[list[ContentItem]] = relationship(back_populates="brand")


class ContentItem(Base):
    __tablename__ = "content_items"
    __table_args__ = (
        UniqueConstraint("platform", "platform_id", name="uq_platform_post"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    platform_id: Mapped[str] = mapped_column(String(255), nullable=False)
    account_handle: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str | None] = mapped_column(Text)
    caption: Mapped[str | None] = mapped_column(Text)
    post_type: Mapped[str | None] = mapped_column(String(50))  # image, video, carousel, reel
    posted_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Engagement metrics
    likes: Mapped[int] = mapped_column(Integer, default=0)
    comments: Mapped[int] = mapped_column(Integer, default=0)
    shares: Mapped[int] = mapped_column(Integer, default=0)
    saves: Mapped[int] = mapped_column(Integer, default=0)
    views: Mapped[int] = mapped_column(Integer, default=0)
    followers_at_time: Mapped[int | None] = mapped_column(Integer)

    # Scoring
    engagement_score: Mapped[float | None] = mapped_column(Float)
    engagement_rate: Mapped[float | None] = mapped_column(Float)
    velocity_score: Mapped[float | None] = mapped_column(Float)
    final_score: Mapped[float | None] = mapped_column(Float)

    # Theme classification
    detected_theme: Mapped[str | None] = mapped_column(String(100))

    # User actions
    starred: Mapped[bool] = mapped_column(default=False)
    notes: Mapped[str | None] = mapped_column(Text)

    collected_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    brand: Mapped[Brand] = relationship(back_populates="contents")
    media: Mapped[list[ContentMedia]] = relationship(back_populates="content")
    tags: Mapped[list[ContentTag]] = relationship(back_populates="content")
    briefs: Mapped[list[ContentBrief]] = relationship(back_populates="source_content")


class ContentMedia(Base):
    __tablename__ = "content_media"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content_id: Mapped[int] = mapped_column(ForeignKey("content_items.id"), nullable=False)
    media_type: Mapped[str] = mapped_column(String(50))  # image, video, thumbnail
    original_url: Mapped[str | None] = mapped_column(Text)
    local_path: Mapped[str | None] = mapped_column(Text)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)

    content: Mapped[ContentItem] = relationship(back_populates="media")


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ContentTag(Base):
    __tablename__ = "content_tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content_id: Mapped[int] = mapped_column(ForeignKey("content_items.id"), nullable=False)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id"), nullable=False)

    content: Mapped[ContentItem] = relationship(back_populates="tags")
    tag: Mapped[Tag] = relationship()


class ContentBrief(Base):
    __tablename__ = "content_briefs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_content_id: Mapped[int] = mapped_column(ForeignKey("content_items.id"), nullable=False)

    # Style analysis from Claude
    style_analysis: Mapped[dict | None] = mapped_column(JSON)

    # Generated brief fields
    headline: Mapped[str | None] = mapped_column(String(500))
    caption_draft: Mapped[str | None] = mapped_column(Text)
    suggested_post_type: Mapped[str | None] = mapped_column(String(50))
    suggested_theme: Mapped[str | None] = mapped_column(String(100))
    slide_count: Mapped[int | None] = mapped_column(Integer)
    visual_direction: Mapped[str | None] = mapped_column(Text)
    cta_suggestion: Mapped[str | None] = mapped_column(Text)
    hashtag_suggestions: Mapped[str | None] = mapped_column(Text)

    # Workflow
    status: Mapped[str] = mapped_column(String(50), default="draft")  # draft, approved, rejected
    editor_notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Wizard additions
    suggested_product: Mapped[str | None] = mapped_column(String(100))
    deep_analysis: Mapped[dict | None] = mapped_column(JSON)

    source_content: Mapped[ContentItem] = relationship(back_populates="briefs")
    generated_media: Mapped[list[GeneratedMedia]] = relationship(back_populates="brief")


class GeneratedMedia(Base):
    __tablename__ = "generated_media"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    brief_id: Mapped[int] = mapped_column(ForeignKey("content_briefs.id"), nullable=False)
    media_type: Mapped[str] = mapped_column(String(50))  # "image"
    local_path: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    brief: Mapped[ContentBrief] = relationship(back_populates="generated_media")


class CollectionRun(Base):
    __tablename__ = "collection_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(50), default="running")  # running, completed, failed
    brands_collected: Mapped[int] = mapped_column(Integer, default=0)
    items_collected: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[str | None] = mapped_column(Text)
