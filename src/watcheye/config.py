"""Config loader and validation using Pydantic."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class PlatformAccount(BaseModel):
    instagram: str = ""
    facebook: str = ""
    xiaohongshu: str = ""
    x_twitter: str = ""
    reddit: str = ""


class BrandConfig(BaseModel):
    name: str
    platforms: PlatformAccount = PlatformAccount()


class ThemeConfig(BaseModel):
    name: str
    keywords: list[str] = []


class MatrixConfig(BaseModel):
    brands: dict[str, list[BrandConfig]] = {}
    themes: list[ThemeConfig] = []


class PlatformSettings(BaseModel):
    apify_actor: str
    max_posts_per_account: int = 50


class ScoringConfig(BaseModel):
    weights: dict[str, float] = Field(default_factory=lambda: {
        "likes": 1.0,
        "comments": 3.0,
        "shares": 5.0,
        "saves": 4.0,
    })
    min_score_threshold: float = 0.5
    velocity_bonus_hours: int = 24
    velocity_bonus_multiplier: float = 1.5


class DatabaseConfig(BaseModel):
    url: str = "postgresql://localhost:5432/watcheye"


class MediaConfig(BaseModel):
    download: bool = True
    storage_path: str = "./media"


class ApifyConfig(BaseModel):
    token: str = ""


class CloneConfig(BaseModel):
    gemini_api_key: str = ""
    model: str = "gemini-3.1-flash-lite-preview"
    image_model: str = "gemini-3.1-flash-image-preview"
    brand_name: str = "Doughnut"
    brand_description: str = "Hong Kong backpack brand (est. 2010). Functional, stylish bags for urban commuters and travelers."
    max_briefs_per_source: int = 3
    products_path: str = "config/products.yaml"


class ProductConfig(BaseModel):
    name: str
    type: str
    capacity: str = ""
    description: str
    best_for: list[str] = []
    keywords: list[str] = []


class AppConfig(BaseModel):
    matrix: MatrixConfig = MatrixConfig()
    platforms: dict[str, PlatformSettings] = {}
    scoring: ScoringConfig = ScoringConfig()
    database: DatabaseConfig = DatabaseConfig()
    media: MediaConfig = MediaConfig()
    apify: ApifyConfig = ApifyConfig()
    clone: CloneConfig = CloneConfig()

    def all_brands(self) -> list[BrandConfig]:
        """Return flat list of all brands across categories."""
        brands: list[BrandConfig] = []
        for category_brands in self.matrix.brands.values():
            brands.extend(category_brands)
        return brands

    def get_brand(self, name: str) -> BrandConfig | None:
        """Find a brand by name (case-insensitive)."""
        for brand in self.all_brands():
            if brand.name.lower() == name.lower():
                return brand
        return None


def load_products(path: str | Path = "config/products.yaml") -> list[ProductConfig]:
    """Load product catalog from YAML."""
    path = Path(path)
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text())
    if not raw or "products" not in raw:
        return []
    return [ProductConfig.model_validate(p) for p in raw["products"]]


def _resolve_env_vars(data: Any) -> Any:
    """Recursively resolve ${ENV_VAR} references in config values."""
    if isinstance(data, str) and data.startswith("${") and data.endswith("}"):
        env_key = data[2:-1]
        return os.environ.get(env_key, "")
    if isinstance(data, dict):
        return {k: _resolve_env_vars(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_resolve_env_vars(item) for item in data]
    return data


def load_config(path: str | Path | None = None) -> AppConfig:
    """Load and validate config from YAML file."""
    if path is None:
        path = Path("config/config.yaml")
    path = Path(path)

    if not path.exists():
        # Fall back to example config
        example = path.parent / "config.example.yaml"
        if example.exists():
            path = example
        else:
            return AppConfig()

    raw = yaml.safe_load(path.read_text())
    if raw is None:
        return AppConfig()

    resolved = _resolve_env_vars(raw)
    return AppConfig.model_validate(resolved)
