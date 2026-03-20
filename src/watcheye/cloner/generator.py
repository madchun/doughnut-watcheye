"""CloneGenerator — analyze competitor post style and generate Doughnut content briefs via Gemini."""

from __future__ import annotations

import json
from enum import Enum

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from watcheye.config import CloneConfig, ProductConfig
from watcheye.storage.models import ContentItem


class StyleAnalysis(BaseModel):
    """Structured style analysis of a social media post."""

    tone: str = Field(description="Overall tone (e.g. aspirational, playful, informative, urgent)")
    caption_structure: str = Field(description="How the caption is structured (e.g. hook -> details -> CTA)")
    cta_pattern: str = Field(description="Call-to-action pattern used (e.g. 'Shop now', 'Link in bio', question)")
    emoji_usage: str = Field(description="How emojis are used (e.g. heavy, minimal, as bullet points)")
    post_format: str = Field(description="Content format (e.g. carousel product showcase, single hero image)")
    hook_style: str = Field(description="How the post opens to grab attention")
    hashtag_strategy: str = Field(description="How hashtags are used (e.g. branded, community, hidden in comments)")


class DeepStyleAnalysis(BaseModel):
    """Deep style analysis including visual elements."""

    # Caption analysis
    tone: str = Field(description="Overall tone")
    caption_structure: str = Field(description="Caption structure pattern")
    cta_pattern: str = Field(description="Call-to-action pattern")
    emoji_usage: str = Field(description="Emoji usage style")
    post_format: str = Field(description="Content format")
    hook_style: str = Field(description="Opening hook style")
    hashtag_strategy: str = Field(description="Hashtag strategy")
    # Visual analysis
    image_style: str = Field(description="Image style, e.g. bright lifestyle photography, studio flat-lay")
    background_description: str = Field(description="Background setting description")
    color_palette: str = Field(description="Dominant color palette")
    people_and_models: str = Field(description="People in image, e.g. young woman with backpack, or none")
    product_placement: str = Field(description="How product is shown, e.g. hero center frame, in-use lifestyle")
    overall_vibe: str = Field(description="One-sentence mood summary")


class ProductSuggestion(BaseModel):
    """Product suggestion for a content brief."""

    product_name: str = Field(description="Name of the suggested Doughnut product")
    reason: str = Field(description="Why this product fits the content style")


class PostType(str, Enum):
    image = "image"
    carousel = "carousel"
    video = "video"
    reel = "reel"


class ContentBriefSchema(BaseModel):
    """A content brief for Doughnut brand."""

    headline: str = Field(description="Brief headline summarizing the content concept")
    caption_draft: str = Field(description="Full draft caption ready for editing")
    suggested_post_type: PostType = Field(description="Recommended post format")
    suggested_theme: str = Field(description="Content theme (e.g. product_showcase, travel_adventure)")
    slide_count: int = Field(description="Number of slides/images if carousel, 1 for single image")
    visual_direction: str = Field(description="Art direction notes for the visual content")
    cta_suggestion: str = Field(description="Suggested call-to-action")
    hashtag_suggestions: str = Field(description="Suggested hashtags, comma-separated")


class BriefsList(BaseModel):
    """List of content briefs."""

    briefs: list[ContentBriefSchema]


class CloneGenerator:
    """Analyze competitor posts and generate Doughnut content briefs via Gemini."""

    def __init__(self, config: CloneConfig):
        self.config = config
        self.client = genai.Client(api_key=config.gemini_api_key)

    def analyze_style(self, item: ContentItem) -> dict:
        """Analyze the style of a source content item using Gemini."""
        prompt = (
            f"Analyze this social media post from {item.brand.name} ({item.platform}).\n\n"
            f"Post type: {item.post_type or 'unknown'}\n"
            f"Likes: {item.likes:,} | Comments: {item.comments:,} | "
            f"Shares: {item.shares:,} | Saves: {item.saves:,}\n"
            f"Score: {item.final_score or 0:.1f}\n\n"
            f"Caption:\n{item.caption or '(no caption)'}\n\n"
            "Analyze the style, tone, structure, and engagement patterns of this post."
        )

        response = self.client.models.generate_content(
            model=self.config.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=StyleAnalysis,
            ),
        )

        try:
            return json.loads(response.text)
        except (json.JSONDecodeError, ValueError):
            return {}

    def generate_briefs(self, item: ContentItem, analysis: dict, count: int = 3) -> list[dict]:
        """Generate content briefs inspired by the source post style via Gemini."""
        prompt = (
            f"You are a social media strategist for {self.config.brand_name}.\n"
            f"Brand: {self.config.brand_description}\n\n"
            f"A competitor post from {item.brand.name} performed very well "
            f"({item.likes:,} likes, score {item.final_score or 0:.1f}).\n\n"
            f"Style analysis of that post:\n{json.dumps(analysis, indent=2)}\n\n"
            f"Original caption:\n{item.caption or '(no caption)'}\n\n"
            f"Generate exactly {count} content brief(s) for {self.config.brand_name} "
            f"that adapt this successful style to our brand. "
            f"Each brief should be unique and capture a different angle. "
            f"Do NOT copy the original — adapt the style and structure for our brand."
        )

        response = self.client.models.generate_content(
            model=self.config.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=BriefsList,
            ),
        )

        try:
            data = json.loads(response.text)
            return data.get("briefs", [])
        except (json.JSONDecodeError, ValueError):
            return []

    def deep_analyze_style(self, item: ContentItem, image_bytes: bytes | None = None) -> dict:
        """Deep analysis of post style including visual elements via multimodal Gemini."""
        text_prompt = (
            f"Analyze this social media post from {item.brand.name} ({item.platform}).\n\n"
            f"Post type: {item.post_type or 'unknown'}\n"
            f"Likes: {item.likes:,} | Comments: {item.comments:,} | "
            f"Shares: {item.shares:,} | Saves: {item.saves:,}\n"
            f"Score: {item.final_score or 0:.1f}\n\n"
            f"Caption:\n{item.caption or '(no caption)'}\n\n"
            "Analyze BOTH the caption style AND the visual style of this post in detail."
        )

        contents: list = []
        if image_bytes:
            contents.append(types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"))
        contents.append(text_prompt)

        response = self.client.models.generate_content(
            model=self.config.model,
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=DeepStyleAnalysis,
            ),
        )

        try:
            return json.loads(response.text)
        except (json.JSONDecodeError, ValueError):
            return {}

    def deep_analyze_carousel(self, item: ContentItem, images: list[bytes]) -> dict:
        """Analyze all images in a carousel post, then synthesize a combined analysis.

        Returns {"per_image_analyses": [...], "combined_analysis": {...}}
        """
        per_image = []
        for img in images:
            analysis = self.deep_analyze_style(item, img)
            per_image.append(analysis)

        combined = self._synthesize_carousel_analysis(item, per_image)
        return {
            "per_image_analyses": per_image,
            "combined_analysis": combined,
        }

    def _synthesize_carousel_analysis(self, item: ContentItem, analyses: list[dict]) -> dict:
        """Synthesize per-image analyses into a unified carousel analysis via Gemini."""
        prompt = (
            f"You are analyzing a carousel post from {item.brand.name} ({item.platform}) "
            f"with {len(analyses)} slides.\n\n"
            f"Here are the per-slide visual analyses:\n"
        )
        for i, a in enumerate(analyses, 1):
            prompt += f"\n--- Slide {i} ---\n{json.dumps(a, indent=2)}\n"

        prompt += (
            "\n\nSynthesize these into a unified carousel analysis. Focus on:\n"
            "1. The overall visual narrative across all slides\n"
            "2. Transition patterns between slides (how the story flows)\n"
            "3. Unified style characteristics (colors, lighting, composition)\n"
            "4. IMPORTANT: Study the STYLE and VISUAL ELEMENTS only. "
            "Do NOT copy backgrounds, models, or specific scenes. "
            "The goal is to understand the visual language so Doughnut can create "
            "their OWN original content with a similar level of craft.\n\n"
            "Return a JSON object with these keys:\n"
            "- visual_narrative: overall story told across slides\n"
            "- transition_pattern: how slides relate to each other\n"
            "- unified_style: consistent style elements across the carousel\n"
            "- color_palette: dominant colors used throughout\n"
            "- composition_pattern: how shots are framed across slides\n"
            "- mood_progression: how the mood evolves from first to last slide\n"
            "- key_takeaways: what makes this carousel effective, as style lessons for Doughnut"
        )

        response = self.client.models.generate_content(
            model=self.config.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )

        try:
            return json.loads(response.text)
        except (json.JSONDecodeError, ValueError):
            return {}

    def suggest_product(self, analysis: dict, products: list[ProductConfig]) -> dict:
        """Suggest the best Doughnut product based on deep analysis and product catalog.

        The returned product_name is validated against the catalog. If Gemini
        hallucinates a name not in the catalog, we fuzzy-match to the closest
        real product or fall back to the first product.
        """
        product_names = [p.name for p in products]
        products_desc = "\n".join(
            f"- {p.name} ({p.type}, {p.capacity}): {p.description} "
            f"Best for: {', '.join(p.best_for)}. Keywords: {', '.join(p.keywords)}"
            for p in products
        )

        prompt = (
            f"Based on this content style analysis:\n{json.dumps(analysis, indent=2)}\n\n"
            f"Which Doughnut product would best showcase the SAME vibe, mood, and aesthetic?\n\n"
            f"IMPORTANT: Doughnut ONLY makes backpacks, crossbody bags, and duffel bags. "
            f"They do NOT sell luggage, suitcases, or trolleys. "
            f"Do NOT try to match the competitor's product category — instead, pick the "
            f"Doughnut product that best captures the same lifestyle and mood.\n\n"
            f"You MUST pick the product_name EXACTLY as written below (copy-paste the name).\n\n"
            f"Product catalog:\n{products_desc}\n\n"
            f"Pick exactly ONE product and explain why it fits the vibe."
        )

        response = self.client.models.generate_content(
            model=self.config.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ProductSuggestion,
            ),
        )

        try:
            result = json.loads(response.text)
        except (json.JSONDecodeError, ValueError):
            return {"product_name": products[0].name if products else "", "reason": "Default suggestion"}

        # Validate product_name against catalog
        if result.get("product_name") not in product_names:
            result["product_name"] = self._fuzzy_match_product(
                result.get("product_name", ""), product_names
            )

        return result

    @staticmethod
    def _fuzzy_match_product(name: str, product_names: list[str]) -> str:
        """Find the closest product name in the catalog via simple substring/similarity match."""
        if not product_names:
            return ""
        name_lower = name.lower()
        # Try substring match first
        for pn in product_names:
            if pn.lower() in name_lower or name_lower in pn.lower():
                return pn
        # Try word overlap
        name_words = set(name_lower.split())
        best, best_score = product_names[0], 0
        for pn in product_names:
            pn_words = set(pn.lower().split())
            overlap = len(name_words & pn_words)
            if overlap > best_score:
                best, best_score = pn, overlap
        return best

    def generate_final_caption(self, item: ContentItem, analysis: dict, product: dict) -> dict:
        """Generate a ready-to-post caption for Doughnut featuring the suggested product."""
        prompt = (
            f"You are a social media copywriter for {self.config.brand_name}.\n"
            f"Brand: {self.config.brand_description}\n\n"
            f"Inspired by this competitor post from {item.brand.name}:\n"
            f"Caption: {item.caption or '(no caption)'}\n\n"
            f"Style analysis:\n{json.dumps(analysis, indent=2)}\n\n"
            f"Featured product: {product.get('product_name', 'Macaroon Classic')}\n"
            f"Reason for product choice: {product.get('reason', '')}\n\n"
            f"Write a COMPLETE, ready-to-post Instagram caption for {self.config.brand_name} "
            f"featuring this product. Adapt the competitor's successful style but make it 100% original.\n\n"
            f"Return JSON with: headline, caption, hashtags (comma-separated), cta"
        )

        response = self.client.models.generate_content(
            model=self.config.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )

        try:
            return json.loads(response.text)
        except (json.JSONDecodeError, ValueError):
            return {"headline": "", "caption": "", "hashtags": "", "cta": ""}

    def generate_image(
        self, prompt_text: str, reference_image: bytes | None = None, max_retries: int = 3,
    ) -> bytes | None:
        """Generate a single image using the image model. Returns image bytes or None.

        When reference_image is provided, sends it as a multimodal input so the
        generated image mirrors the composition and style of the original.

        Retries with exponential backoff on rate limit errors.
        """
        import time

        contents: list = []
        if reference_image:
            contents.append(types.Part.from_bytes(data=reference_image, mime_type="image/jpeg"))
        contents.append(prompt_text)

        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.config.image_model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        response_modalities=["TEXT", "IMAGE"],
                    ),
                )

                if response.candidates:
                    for part in response.candidates[0].content.parts:
                        if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                            return part.inline_data.data
                return None
            except Exception as e:
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    wait = 30 * (attempt + 1)
                    if attempt < max_retries - 1:
                        time.sleep(wait)
                        continue
                return None
        return None
