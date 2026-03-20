# Watcheye — Doughnut Social Media Content Monitor

Automated social media content curation tool for **Doughnut** (Hong Kong backpack brand).
Monitors competitor and lifestyle brand social media for high-engagement content inspiration.

## Setup

```bash
# Install dependencies
uv sync

# Copy and edit config
cp config/config.example.yaml config/config.yaml
# Edit config/config.yaml with your API keys and database URL

# Set Apify token
export APIFY_TOKEN=your_token_here

# Initialize database
uv run watcheye init

# Run collection
uv run watcheye collect

# Score content
uv run watcheye score

# Launch web viewer
uv run watcheye serve
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `watcheye init` | Initialize database and sync brands |
| `watcheye collect` | Collect posts from all configured brands |
| `watcheye collect --brand Herschel --platform instagram` | Targeted collection |
| `watcheye score` | Score/re-score all content |
| `watcheye research` | Generate competitor research queries |
| `watcheye stats` | Show collection statistics |
| `watcheye serve` | Launch Streamlit web dashboard |

## Architecture

```
config.yaml → Collector (Apify) → Scorer → PostgreSQL → Streamlit Web Viewer
```

## Supported Platforms

- Instagram
- Facebook
- Xiaohongshu (小紅書)
- X/Twitter
- Reddit
