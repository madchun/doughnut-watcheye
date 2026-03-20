"""Tests for the cloner module."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from watcheye.cloner.generator import CloneGenerator
from watcheye.config import CloneConfig


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
    return item


class TestCloneGenerator:
    @patch("watcheye.cloner.generator.genai.Client")
    def test_analyze_style(self, mock_client_cls, clone_config, mock_content_item):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        analysis_data = {
            "tone": "aspirational",
            "caption_structure": "hook -> details -> CTA",
            "cta_pattern": "Shop the collection — link in bio",
            "emoji_usage": "minimal, strategic placement",
            "post_format": "carousel product showcase",
            "hook_style": "bold statement opening",
            "hashtag_strategy": "branded + community tags",
        }

        mock_response = MagicMock()
        mock_response.text = json.dumps(analysis_data)
        mock_client.models.generate_content.return_value = mock_response

        generator = CloneGenerator(clone_config)
        result = generator.analyze_style(mock_content_item)

        assert result["tone"] == "aspirational"
        assert result["post_format"] == "carousel product showcase"
        mock_client.models.generate_content.assert_called_once()
        call_kwargs = mock_client.models.generate_content.call_args.kwargs
        assert call_kwargs["model"] == "gemini-3.1-flash-lite-preview"

    @patch("watcheye.cloner.generator.genai.Client")
    def test_generate_briefs(self, mock_client_cls, clone_config, mock_content_item):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        briefs_data = {
            "briefs": [
                {
                    "headline": "Doughnut x City Explorer Collection",
                    "caption_draft": "Your next adventure starts here...",
                    "suggested_post_type": "carousel",
                    "suggested_theme": "travel_adventure",
                    "slide_count": 8,
                    "visual_direction": "Lifestyle shots in urban HK settings",
                    "cta_suggestion": "Explore the collection — link in bio",
                    "hashtag_suggestions": "#doughnut, #hkstyle, #travelready",
                },
                {
                    "headline": "Pack Light, Go Far",
                    "caption_draft": "Minimalist packing for maximum adventure...",
                    "suggested_post_type": "carousel",
                    "suggested_theme": "product_showcase",
                    "slide_count": 6,
                    "visual_direction": "Flat lay product shots, clean background",
                    "cta_suggestion": "Shop now at doughnutofficial.com",
                    "hashtag_suggestions": "#doughnut, #packlight, #urbancarry",
                },
            ]
        }

        mock_response = MagicMock()
        mock_response.text = json.dumps(briefs_data)
        mock_client.models.generate_content.return_value = mock_response

        analysis = {"tone": "aspirational", "post_format": "carousel"}
        generator = CloneGenerator(clone_config)
        result = generator.generate_briefs(mock_content_item, analysis, count=2)

        assert len(result) == 2
        assert result[0]["headline"] == "Doughnut x City Explorer Collection"
        assert result[1]["suggested_post_type"] == "carousel"

    @patch("watcheye.cloner.generator.genai.Client")
    def test_analyze_style_empty_response(self, mock_client_cls, clone_config, mock_content_item):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.text = "not valid json"
        mock_client.models.generate_content.return_value = mock_response

        generator = CloneGenerator(clone_config)
        result = generator.analyze_style(mock_content_item)

        assert result == {}

    @patch("watcheye.cloner.generator.genai.Client")
    def test_generate_briefs_empty_response(self, mock_client_cls, clone_config, mock_content_item):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.text = "invalid"
        mock_client.models.generate_content.return_value = mock_response

        generator = CloneGenerator(clone_config)
        result = generator.generate_briefs(mock_content_item, {}, count=2)

        assert result == []


    @patch("watcheye.cloner.generator.genai.Client")
    def test_deep_analyze_carousel(self, mock_client_cls, clone_config, mock_content_item):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        # First 3 calls: per-image deep_analyze_style, last call: _synthesize_carousel_analysis
        per_image_data = {
            "tone": "adventurous",
            "caption_structure": "hook -> story -> CTA",
            "cta_pattern": "Swipe for more",
            "emoji_usage": "moderate",
            "post_format": "carousel",
            "hook_style": "visual hook",
            "hashtag_strategy": "community tags",
            "image_style": "bright lifestyle photography",
            "background_description": "outdoor mountain trail",
            "color_palette": "earth tones, warm greens",
            "people_and_models": "young woman hiking",
            "product_placement": "backpack hero shot",
            "overall_vibe": "adventure lifestyle",
        }
        combined_data = {
            "visual_narrative": "journey from city to nature",
            "transition_pattern": "zoom progression",
            "unified_style": "warm outdoor photography",
            "color_palette": "earth tones throughout",
            "composition_pattern": "subject centered",
            "mood_progression": "calm to adventurous",
            "key_takeaways": "strong visual storytelling across slides",
        }

        responses = []
        for _ in range(3):
            r = MagicMock()
            r.text = json.dumps(per_image_data)
            responses.append(r)
        synth_response = MagicMock()
        synth_response.text = json.dumps(combined_data)
        responses.append(synth_response)

        mock_client.models.generate_content.side_effect = responses

        generator = CloneGenerator(clone_config)
        fake_images = [b"img1", b"img2", b"img3"]
        result = generator.deep_analyze_carousel(mock_content_item, fake_images)

        assert "per_image_analyses" in result
        assert "combined_analysis" in result
        assert len(result["per_image_analyses"]) == 3
        assert result["per_image_analyses"][0]["tone"] == "adventurous"
        assert result["combined_analysis"]["visual_narrative"] == "journey from city to nature"
        # 3 deep_analyze_style calls + 1 synthesize call = 4
        assert mock_client.models.generate_content.call_count == 4

    @patch("watcheye.cloner.generator.genai.Client")
    def test_deep_analyze_carousel_empty_synthesis(self, mock_client_cls, clone_config, mock_content_item):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        per_image_data = {"tone": "playful", "image_style": "flat lay"}

        per_img_resp = MagicMock()
        per_img_resp.text = json.dumps(per_image_data)

        synth_resp = MagicMock()
        synth_resp.text = "invalid json"

        mock_client.models.generate_content.side_effect = [per_img_resp, synth_resp]

        generator = CloneGenerator(clone_config)
        result = generator.deep_analyze_carousel(mock_content_item, [b"img1"])

        assert len(result["per_image_analyses"]) == 1
        assert result["combined_analysis"] == {}


class TestCloneCLI:
    def test_clone_command_no_api_key(self):
        """Clone command should fail without API key."""
        from typer.testing import CliRunner

        from watcheye.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["clone", "--brand", "Bellroy"])

        # Should fail because GEMINI_API_KEY is not set
        assert result.exit_code != 0
