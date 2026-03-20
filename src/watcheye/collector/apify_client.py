"""Apify API wrapper for running actors and retrieving results."""

from __future__ import annotations

import time

from apify_client import ApifyClient as _ApifyClient


class ApifyCollector:
    """Wrapper around the Apify API client."""

    def __init__(self, token: str):
        self.client = _ApifyClient(token)

    def run_actor(
        self,
        actor_id: str,
        run_input: dict,
        timeout_secs: int = 300,
        poll_interval: int = 5,
    ) -> list[dict]:
        """Run an Apify actor and return its dataset items."""
        run = self.client.actor(actor_id).call(
            run_input=run_input,
            timeout_secs=timeout_secs,
        )

        # Wait for the run to finish
        run_client = self.client.run(run["id"])
        while True:
            info = run_client.get()
            if info and info.get("status") in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
                break
            time.sleep(poll_interval)

        if info.get("status") != "SUCCEEDED":
            raise RuntimeError(f"Apify actor run failed with status: {info.get('status')}")

        dataset_id = run.get("defaultDatasetId")
        if not dataset_id:
            return []

        items = list(self.client.dataset(dataset_id).iterate_items())
        return items
