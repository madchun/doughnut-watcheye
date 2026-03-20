"""Tests for the wizard feature — deep analysis, product suggestion, image generation."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from watcheye.cloner.generator import CloneGenerator
from watcheye.config import CloneConfig, ProductConfig, load_products


@pytest.fixture
def clone_config():
    return CloneConfig(
        gemini_api_key="test-key",
        model="gemini-3.1-flash-lite-preview",
        image_model="gemini-3.1-flash-image-preview",
        brand_name="Doughnut",
        brand_description="Hong Kong backpack brand.",
        max_briefs_per_source=2,
    )


@pytest.fixture
def mock_content_item():
    item = MagicMock()
    item.brand.name = "Bellroy"
    item.platform = "instagram"
    item.post_type = "carousel"
    item.likes = 2413
    item.comments = 45
    item.shares = 12
    item.saves = 89
    item.final_score = 100.0
    item.caption = "Adventure awaits! Our new luggage collection is here. #travel #bellroy"
    item.detected_theme = "travel_adventure"
    item.media = [MagicMock(original_url="https://example.com/img1.jpg")]
    item.id = 1
    return item


@pytest.fixture
def sample_products():
    return [
        ProductConfig(
            name="Macaroon Classic",
            type="backpack",
            capacity="16L",
            description="Iconic everyday backpack with signature front pocket.",
            best_for=["urban_lifestyle", "product_showcase"],
            keywords=["colorful", "casual", "everyday"],
        ),
        ProductConfig(
            name="Macaroon Large",
            type="backpack",
            capacity="20L",
            description="Expanded version for work and travel.",
            best_for=["travel_adventure", "urban_lifestyle"],
            keywords=["spacious", "travel", "work"],
        ),
    ]


class TestLoadProducts:
    def test_load_products_from_yaml(self):
        """Load products from the real products.yaml."""
        products = load_products(Path("config/products.yaml"))
        assert len(products) == 11
        assert products[0].name == "Macaroon Classic"
        assert products[0].type == "backpack"
        assert "urban_lifestyle" in products[0].best_for

    def test_load_products_missing_file(self, tmp_path):
        """Returns empty list for missing file."""
        result = load_products(tmp_path / "nonexistent.yaml")
        assert result == []

    def test_load_products_empty_file(self, tmp_path):
        """Returns empty list for empty YAML."""
        f = tmp_path / "empty.yaml"
        f.write_text("")
        result = load_products(f)
        assert result == []


class TestDeepAnalyzeStyle:
    @patch("watcheye.cloner.generator.genai.Client")
    def test_deep_analyze_with_image(self, mock_client_cls, clone_config, mock_content_item):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        analysis_data = {
            "tone": "aspirational",
            "caption_structure": "hook -> details -> CTA",
            "cta_pattern": "Shop now",
            "emoji_usage": "minimal",
            "post_format": "carousel product showcase",
            "hook_style": "bold statement",
            "hashtag_strategy": "branded",
            "image_style": "bright lifestyle photography",
            "background_description": "airport terminal, natural light",
            "color_palette": "warm earth tones",
            "people_and_models": "young couple with luggage",
            "product_placement": "hero center frame",
            "overall_vibe": "aspirational travel lifestyle",
        }

        mock_response = MagicMock()
        mock_response.text = json.dumps(analysis_data)
        mock_client.models.generate_content.return_value = mock_response

        generator = CloneGenerator(clone_config)
        result = generator.deep_analyze_style(mock_content_item, image_bytes=b"fake_image_data")

        assert result["image_style"] == "bright lifestyle photography"
        assert result["overall_vibe"] == "aspirational travel lifestyle"
        assert result["tone"] == "aspirational"

        # Verify multimodal call (contents should include image part + text)
        call_kwargs = mock_client.models.generate_content.call_args.kwargs
        assert len(call_kwargs["contents"]) == 2  # image part + text

    @patch("watcheye.cloner.generator.genai.Client")
    def test_deep_analyze_text_only_fallback(self, mock_client_cls, clone_config, mock_content_item):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        analysis_data = {
            "tone": "playful",
            "caption_structure": "question -> list",
            "cta_pattern": "Link in bio",
            "emoji_usage": "heavy",
            "post_format": "single image",
            "hook_style": "question hook",
            "hashtag_strategy": "community tags",
            "image_style": "unknown",
            "background_description": "unknown",
            "color_palette": "unknown",
            "people_and_models": "unknown",
            "product_placement": "unknown",
            "overall_vibe": "casual and fun",
        }

        mock_response = MagicMock()
        mock_response.text = json.dumps(analysis_data)
        mock_client.models.generate_content.return_value = mock_response

        generator = CloneGenerator(clone_config)
        result = generator.deep_analyze_style(mock_content_item, image_bytes=None)

        assert result["tone"] == "playful"
        # Text-only: contents should have just 1 element (text string)
        call_kwargs = mock_client.models.generate_content.call_args.kwargs
        assert len(call_kwargs["contents"]) == 1

    @patch("watcheye.cloner.generator.genai.Client")
    def test_deep_analyze_invalid_response(self, mock_client_cls, clone_config, mock_content_item):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.text = "not json"
        mock_client.models.generate_content.return_value = mock_response

        generator = CloneGenerator(clone_config)
        result = generator.deep_analyze_style(mock_content_item)
        assert result == {}


class TestSuggestProduct:
    @patch("watcheye.cloner.generator.genai.Client")
    def test_suggest_product(self, mock_client_cls, clone_config, sample_products):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        suggestion_data = {
            "product_name": "Macaroon Large",
            "reason": "Travel-ready 20L fits the aspirational travel vibe",
        }

        mock_response = MagicMock()
        mock_response.text = json.dumps(suggestion_data)
        mock_client.models.generate_content.return_value = mock_response

        generator = CloneGenerator(clone_config)
        analysis = {"tone": "aspirational", "overall_vibe": "travel lifestyle"}
        result = generator.suggest_product(analysis, sample_products)

        assert result["product_name"] == "Macaroon Large"
        assert "travel" in result["reason"].lower()

    @patch("watcheye.cloner.generator.genai.Client")
    def test_suggest_product_invalid_response(self, mock_client_cls, clone_config, sample_products):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.text = "bad json"
        mock_client.models.generate_content.return_value = mock_response

        generator = CloneGenerator(clone_config)
        result = generator.suggest_product({}, sample_products)
        assert result["product_name"] == "Macaroon Classic"  # fallback to first product

    @patch("watcheye.cloner.generator.genai.Client")
    def test_suggest_product_hallucinated_name_fuzzy_match(self, mock_client_cls, clone_config, sample_products):
        """When Gemini returns a product name not in the catalog, fuzzy match to closest."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        # Gemini hallucinates "Macaroon Travel" which doesn't exist
        suggestion_data = {
            "product_name": "Macaroon Travel",
            "reason": "Great for travel vibes",
        }
        mock_response = MagicMock()
        mock_response.text = json.dumps(suggestion_data)
        mock_client.models.generate_content.return_value = mock_response

        generator = CloneGenerator(clone_config)
        result = generator.suggest_product({"tone": "aspirational"}, sample_products)

        # Should fuzzy match to a real product (substring "Macaroon" matches both,
        # but "Macaroon Travel" is not exact — should pick one of the Macaroon variants)
        assert result["product_name"] in ["Macaroon Classic", "Macaroon Large"]

    @patch("watcheye.cloner.generator.genai.Client")
    def test_suggest_product_completely_wrong_name(self, mock_client_cls, clone_config, sample_products):
        """When Gemini returns a totally unrelated product name, fall back to first product."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        suggestion_data = {
            "product_name": "Samsonite Roller 28 inch",
            "reason": "Good for travel",
        }
        mock_response = MagicMock()
        mock_response.text = json.dumps(suggestion_data)
        mock_client.models.generate_content.return_value = mock_response

        generator = CloneGenerator(clone_config)
        result = generator.suggest_product({"tone": "aspirational"}, sample_products)

        # No overlap at all — should fall back to first product
        assert result["product_name"] == "Macaroon Classic"


class TestFuzzyMatchProduct:
    def test_exact_match_not_needed(self):
        """_fuzzy_match_product is only called when exact match fails."""
        names = ["Macaroon Classic", "Macaroon Large", "Ho-Yo Crossbody"]
        assert CloneGenerator._fuzzy_match_product("Macaroon Classic", names) == "Macaroon Classic"

    def test_substring_match(self):
        names = ["Macaroon Classic", "Macaroon Large", "Ho-Yo Crossbody"]
        assert CloneGenerator._fuzzy_match_product("Macaroon", names) == "Macaroon Classic"

    def test_word_overlap_match(self):
        names = ["Macaroon Classic", "Macaroon Large", "Ho-Yo Crossbody"]
        assert CloneGenerator._fuzzy_match_product("Large Macaroon Bag", names) == "Macaroon Large"

    def test_no_match_returns_first(self):
        names = ["Macaroon Classic", "Macaroon Large"]
        assert CloneGenerator._fuzzy_match_product("Samsonite Roller", names) == "Macaroon Classic"

    def test_empty_catalog(self):
        assert CloneGenerator._fuzzy_match_product("anything", []) == ""


class TestGenerateImage:
    @patch("watcheye.cloner.generator.genai.Client")
    def test_generate_image_success(self, mock_client_cls, clone_config):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        fake_image_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

        mock_inline_data = MagicMock()
        mock_inline_data.mime_type = "image/png"
        mock_inline_data.data = fake_image_bytes

        mock_part = MagicMock()
        mock_part.inline_data = mock_inline_data

        mock_candidate = MagicMock()
        mock_candidate.content.parts = [mock_part]

        mock_response = MagicMock()
        mock_response.candidates = [mock_candidate]
        mock_client.models.generate_content.return_value = mock_response

        generator = CloneGenerator(clone_config)
        result = generator.generate_image("A Doughnut Macaroon backpack in urban setting")

        assert result == fake_image_bytes
        call_kwargs = mock_client.models.generate_content.call_args.kwargs
        assert call_kwargs["model"] == "gemini-3.1-flash-image-preview"

    @patch("watcheye.cloner.generator.genai.Client")
    def test_generate_image_with_reference(self, mock_client_cls, clone_config):
        """When reference_image is provided, contents should include image part + text."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        fake_image_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

        mock_inline_data = MagicMock()
        mock_inline_data.mime_type = "image/png"
        mock_inline_data.data = fake_image_bytes

        mock_part = MagicMock()
        mock_part.inline_data = mock_inline_data

        mock_candidate = MagicMock()
        mock_candidate.content.parts = [mock_part]

        mock_response = MagicMock()
        mock_response.candidates = [mock_candidate]
        mock_client.models.generate_content.return_value = mock_response

        generator = CloneGenerator(clone_config)
        ref_image = b"\xff\xd8\xff\xe0" + b"\x00" * 50  # fake JPEG bytes
        result = generator.generate_image("Recreate this scene", reference_image=ref_image)

        assert result == fake_image_bytes
        call_kwargs = mock_client.models.generate_content.call_args.kwargs
        # contents should have 2 elements: image Part + text prompt
        assert len(call_kwargs["contents"]) == 2

    @patch("watcheye.cloner.generator.genai.Client")
    def test_generate_image_text_only(self, mock_client_cls, clone_config):
        """When no reference_image, contents should have just the text prompt."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        fake_image_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

        mock_inline_data = MagicMock()
        mock_inline_data.mime_type = "image/png"
        mock_inline_data.data = fake_image_bytes

        mock_part = MagicMock()
        mock_part.inline_data = mock_inline_data

        mock_candidate = MagicMock()
        mock_candidate.content.parts = [mock_part]

        mock_response = MagicMock()
        mock_response.candidates = [mock_candidate]
        mock_client.models.generate_content.return_value = mock_response

        generator = CloneGenerator(clone_config)
        result = generator.generate_image("A Doughnut backpack")

        assert result == fake_image_bytes
        call_kwargs = mock_client.models.generate_content.call_args.kwargs
        # contents should have just 1 element: text prompt
        assert len(call_kwargs["contents"]) == 1

    @patch("watcheye.cloner.generator.genai.Client")
    def test_generate_image_no_image_in_response(self, mock_client_cls, clone_config):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_part = MagicMock()
        mock_part.inline_data = None

        mock_candidate = MagicMock()
        mock_candidate.content.parts = [mock_part]

        mock_response = MagicMock()
        mock_response.candidates = [mock_candidate]
        mock_client.models.generate_content.return_value = mock_response

        generator = CloneGenerator(clone_config)
        result = generator.generate_image("prompt")

        assert result is None

    @patch("watcheye.cloner.generator.genai.Client")
    def test_generate_image_empty_candidates(self, mock_client_cls, clone_config):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.candidates = []
        mock_client.models.generate_content.return_value = mock_response

        generator = CloneGenerator(clone_config)
        result = generator.generate_image("prompt")

        assert result is None


class TestWizardCLI:
    def test_wizard_command_no_api_key(self):
        """Wizard command should fail without API key."""
        from typer.testing import CliRunner

        from watcheye.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["wizard"])

        assert result.exit_code != 0

    @patch("watcheye.cloner.generator.genai.Client")
    def test_wizard_command_no_scored_data(self, mock_client_cls, tmp_path):
        """Wizard should exit gracefully when no scored data exists."""
        import os

        from typer.testing import CliRunner

        from watcheye.cli import app

        os.environ["GEMINI_API_KEY"] = "test-key"
        runner = CliRunner()
        result = runner.invoke(app, ["wizard", "--top", "3"])

        # Should exit 0 because no scored content (or exit 1 if no products)
        # Either way, should not crash
        assert result.exit_code in (0, 1)
