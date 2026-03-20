"""Shared pytest fixtures for Watcheye tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from watcheye.config import AppConfig, load_config
from watcheye.storage.models import Base, Brand


@pytest.fixture
def config() -> AppConfig:
    """Load the example config."""
    return load_config(Path("config/config.example.yaml"))


@pytest.fixture
def db_session():
    """Provide an in-memory SQLite session for tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def sample_brand(db_session: Session) -> Brand:
    """Insert and return a sample brand."""
    brand = Brand(
        name="TestBrand",
        category="direct_competitors",
        instagram="testbrand_ig",
        facebook="testbrand_fb",
        x_twitter="testbrand_tw",
    )
    db_session.add(brand)
    db_session.flush()
    return brand
