"""Tests for config loading and validation."""

from pathlib import Path

from watcheye.config import AppConfig, load_config


def test_load_example_config():
    """Test loading the example config file."""
    cfg = load_config(Path("config/config.example.yaml"))
    assert isinstance(cfg, AppConfig)
    assert len(cfg.matrix.brands) > 0
    assert len(cfg.matrix.themes) > 0


def test_all_brands():
    """Test flattening all brands."""
    cfg = load_config(Path("config/config.example.yaml"))
    brands = cfg.all_brands()
    assert len(brands) > 0
    names = [b.name for b in brands]
    assert "Herschel" in names
    assert "Rains" in names


def test_get_brand():
    """Test finding a brand by name."""
    cfg = load_config(Path("config/config.example.yaml"))
    brand = cfg.get_brand("herschel")
    assert brand is not None
    assert brand.name == "Herschel"
    assert brand.platforms.instagram == "haborherschel"


def test_get_brand_not_found():
    """Test brand not found returns None."""
    cfg = load_config(Path("config/config.example.yaml"))
    assert cfg.get_brand("nonexistent") is None


def test_scoring_config():
    """Test scoring config defaults."""
    cfg = load_config(Path("config/config.example.yaml"))
    assert cfg.scoring.weights["likes"] == 1.0
    assert cfg.scoring.weights["comments"] == 3.0
    assert cfg.scoring.min_score_threshold == 0.5


def test_platform_settings():
    """Test platform settings loaded."""
    cfg = load_config(Path("config/config.example.yaml"))
    assert "instagram" in cfg.platforms
    assert cfg.platforms["instagram"].max_posts_per_account == 50


def test_default_config_when_missing():
    """Test fallback to default when no config file."""
    cfg = load_config(Path("/nonexistent/path.yaml"))
    assert isinstance(cfg, AppConfig)


def test_env_var_resolution():
    """Test environment variable resolution in config."""
    import os
    os.environ["TEST_WATCHEYE_VAR"] = "test_value"
    from watcheye.config import _resolve_env_vars
    result = _resolve_env_vars("${TEST_WATCHEYE_VAR}")
    assert result == "test_value"
    del os.environ["TEST_WATCHEYE_VAR"]


def test_themes_loaded():
    """Test themes are loaded from config."""
    cfg = load_config(Path("config/config.example.yaml"))
    theme_names = [t.name for t in cfg.matrix.themes]
    assert "product_showcase" in theme_names
    assert "travel_adventure" in theme_names
    assert "urban_lifestyle" in theme_names
