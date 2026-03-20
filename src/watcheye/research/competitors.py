"""Web search for competitor social media accounts."""

from __future__ import annotations

import httpx


PLATFORMS = {
    "instagram": "instagram.com",
    "facebook": "facebook.com",
    "x_twitter": "x.com OR twitter.com",
    "xiaohongshu": "xiaohongshu.com",
}

DEFAULT_BRANDS = [
    # Direct competitors
    "Herschel Supply Co",
    "Fjällräven",
    "Eastpak",
    "Anello",
    "CabinZero",
    "Millican",
    "Bellroy",
    # Lifestyle
    "The North Face",
    "Patagonia",
    "Columbia Sportswear",
    "Arc'teryx",
    # Fashion bag
    "Rains bags",
    "Sandqvist",
    "Côte&Ciel",
    "FREITAG bags",
]


def search_brand_accounts(brand_name: str, platform: str) -> list[dict]:
    """Search for a brand's social media account on a given platform.

    Returns a list of potential matches with url and description.
    This is a helper that uses web search — requires manual verification.
    """
    site = PLATFORMS.get(platform, platform)
    query = f'site:{site} "{brand_name}" official'

    # This is a stub — in production, integrate with a web search API
    # (e.g., SerpAPI, Google Custom Search, or Apify Google Search actor)
    return [{"query": query, "note": "Manual search required — use web search tool"}]


def generate_research_report(brands: list[str] | None = None) -> str:
    """Generate a report of brands to research with suggested search queries."""
    if brands is None:
        brands = DEFAULT_BRANDS

    lines = ["# Competitor Social Media Research", ""]
    for brand in brands:
        lines.append(f"## {brand}")
        for platform, site in PLATFORMS.items():
            query = f'site:{site} "{brand}" official'
            lines.append(f"  - {platform}: search `{query}`")
        lines.append("")

    return "\n".join(lines)
