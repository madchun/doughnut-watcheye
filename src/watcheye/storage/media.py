"""Media file download and storage."""

from __future__ import annotations

from pathlib import Path

import httpx


def download_media(url: str, storage_path: str, filename: str) -> str | None:
    """Download a media file and return the local path."""
    dest_dir = Path(storage_path)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename

    if dest.exists():
        return str(dest)

    try:
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
            dest.write_bytes(resp.content)
            return str(dest)
    except httpx.HTTPError:
        return None
