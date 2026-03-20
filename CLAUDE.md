# Doughnut Social Media Content Watcheye

## Project Scope
Automated social media content curation tool for Doughnut (Hong Kong backpack brand, est. 2010).
Monitors competitor and lifestyle brand social media for high-engagement content inspiration.

## Tech Stack
- Python 3.11+, managed with uv
- Typer CLI, SQLAlchemy 2.0, Alembic, Pydantic v2
- Apify for social media data collection
- PostgreSQL for storage
- Streamlit for web viewer

## Conventions
- Source code in `src/watcheye/`
- Config in `config/config.yaml`
- Use Pydantic models for all config/data validation
- SQLAlchemy 2.0 style (mapped_column, DeclarativeBase)
- Tests in `tests/` using pytest
- All CLI commands via Typer app in `cli.py`

## Commands
- `uv run watcheye init` — setup DB
- `uv run watcheye collect` — run collection
- `uv run watcheye score` — score content
- `uv run watcheye serve` — launch Streamlit
- `uv run pytest` — run tests
