"""CLI integration tests using CliRunner and temp SQLite."""

from __future__ import annotations

import tempfile
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from watcheye.cli import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _reset_db_globals():
    """Reset database module globals between tests."""
    import watcheye.storage.database as db_mod
    db_mod._engine = None
    db_mod._SessionLocal = None
    yield
    db_mod._engine = None
    db_mod._SessionLocal = None


def _patch_config_db_url(db_path: str):
    """Patch load_config to use a file-based SQLite at db_path."""
    from watcheye.config import load_config as _original_load

    url = f"sqlite:///{db_path}"

    def patched_load(path=None):
        cfg = _original_load(path)
        cfg.database.url = url
        return cfg

    return patch("watcheye.cli.load_config", side_effect=patched_load)


class TestInitCommand:
    def test_init_creates_database(self, tmp_path):
        db = str(tmp_path / "test.db")
        with _patch_config_db_url(db):
            result = runner.invoke(app, ["init"])
        assert result.exit_code == 0
        assert "initialized" in result.stdout.lower() or "Initializing" in result.stdout

    def test_init_adds_brands(self, tmp_path):
        db = str(tmp_path / "test.db")
        with _patch_config_db_url(db):
            result = runner.invoke(app, ["init"])
        assert result.exit_code == 0
        assert "Herschel" in result.stdout or "Added brand" in result.stdout


class TestSeedCommand:
    def test_seed_after_init(self, tmp_path):
        """Seed inserts fake data after init."""
        db = str(tmp_path / "test.db")
        with _patch_config_db_url(db):
            runner.invoke(app, ["init"])
            result = runner.invoke(app, ["seed", "--count", "3"])
        assert result.exit_code == 0
        assert "Seeded" in result.stdout

    def test_seed_creates_content(self, tmp_path):
        db = str(tmp_path / "test.db")
        with _patch_config_db_url(db):
            runner.invoke(app, ["init"])
            result = runner.invoke(app, ["seed", "--count", "2"])
        assert result.exit_code == 0
        assert "fake posts" in result.stdout


class TestScoreCommand:
    def test_score_with_no_data(self, tmp_path):
        db = str(tmp_path / "test.db")
        with _patch_config_db_url(db):
            runner.invoke(app, ["init"])
            result = runner.invoke(app, ["score"])
        assert result.exit_code == 0
        assert "Scored" in result.stdout

    def test_score_after_seed(self, tmp_path):
        db = str(tmp_path / "test.db")
        with _patch_config_db_url(db):
            runner.invoke(app, ["init"])
            runner.invoke(app, ["seed", "--count", "3"])
            result = runner.invoke(app, ["score"])
        assert result.exit_code == 0
        assert "Scored" in result.stdout


class TestStatsCommand:
    def test_stats_empty(self, tmp_path):
        db = str(tmp_path / "test.db")
        with _patch_config_db_url(db):
            runner.invoke(app, ["init"])
            result = runner.invoke(app, ["stats"])
        assert result.exit_code == 0

    def test_stats_with_data(self, tmp_path):
        db = str(tmp_path / "test.db")
        with _patch_config_db_url(db):
            runner.invoke(app, ["init"])
            runner.invoke(app, ["seed", "--count", "2"])
            runner.invoke(app, ["score"])
            result = runner.invoke(app, ["stats"])
        assert result.exit_code == 0


class TestCollectCommandMocked:
    def test_collect_with_mocked_apify(self, tmp_path):
        """Test collect command with mocked Apify responses."""
        fake_items = [
            {
                "id": "mock_ig_1",
                "shortCode": "MOCK1",
                "displayUrl": "https://example.com/mock.jpg",
                "caption": "Mock post for testing",
                "type": "Image",
                "timestamp": "2025-12-01T10:00:00",
                "likesCount": 100,
                "commentsCount": 10,
            }
        ]
        db = str(tmp_path / "test.db")
        with _patch_config_db_url(db), \
             patch("watcheye.collector.apify_client.ApifyCollector") as MockApify:
            mock_instance = MockApify.return_value
            mock_instance.run_actor.return_value = fake_items

            runner.invoke(app, ["init"])
            result = runner.invoke(app, ["collect", "--brand", "Herschel", "--platform", "instagram"])

        assert result.exit_code == 0

    def test_collect_unknown_brand(self, tmp_path):
        db = str(tmp_path / "test.db")
        with _patch_config_db_url(db):
            runner.invoke(app, ["init"])
            result = runner.invoke(app, ["collect", "--brand", "NonexistentBrand"])
        assert result.exit_code == 1
