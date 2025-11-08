#!/usr/bin/env python3
"""
Better Stack Monitor Auto-Synchronization Script
Automatically synchronizes call setup from mobula.io monitors to their zobula.xyz duplicates.
Runs without user interaction - use with caution!
"""

import requests
import json
from typing import List, Dict, Optional
from dataclasses import dataclass
import sys

# Configuration
API_TOKEN = "aeZ3tcXRJe5ZsMpkBRf5LCWR"
BASE_URL = "https://betteruptime.com/api/v2"

@dataclass
class Monitor:
    """Represents a Better Stack monitor"""
    id: str
    url: str
    name: str
    call: bool

    def __repr__(self):
        return f"Monitor(id={self.id}, url={self.url}, call={self.call})"


class BetterStackAPI:
    """Better Stack API client"""

    def __init__(self, api_token: str):
        self.api_token = api_token
        self.base_url = BASE_URL
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }

    def get_all_monitors(self) -> List[Monitor]:
        """Fetch all monitors from Better Stack"""
        monitors = []
        page = 1

        print("Fetching monitors from Better Stack API...")

        while True:
            url = f"{self.base_url}/monitors"
            params = {"page": page, "per_page": 100}

            try:
                response = requests.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                data = response.json()

                if not data.get("data"):
                    break

                for item in data["data"]:
                    attrs = item.get("attributes", {})
                    monitor = Monitor(
                        id=item.get("id"),
                        url=attrs.get("url", ""),
                        name=attrs.get("pronounceable_name", ""),
                        call=attrs.get("call", False)
                    )
                    monitors.append(monitor)

                print(f"  Page {page}: Fetched {len(data['data'])} monitors")

                # Check if there are more pages
                pagination = data.get("pagination", {})
                next_url = pagination.get("next")
                if not next_url:
                    break

                page += 1

            except requests.exceptions.RequestException as e:
                print(f"Error fetching monitors: {e}")
                sys.exit(1)

        print(f"\nTotal monitors fetched: {len(monitors)}\n")
        return monitors

    def update_monitor_call(self, monitor_id: str, call_value: bool) -> bool:
        """Update the call setting for a monitor"""
        url = f"{self.base_url}/monitors/{monitor_id}"
        payload = {"call": call_value}

        try:
            response = requests.patch(url, headers=self.headers, json=payload)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            print(f"  Error updating monitor {monitor_id}: {e}")
            return False


def extract_path_from_url(url: str) -> str:
    """Extract the path component from a URL (after the domain)"""
    # Remove protocol
    if "://" in url:
        url = url.split("://", 1)[1]

    # Split by first /
    parts = url.split("/", 1)
    if len(parts) > 1:
        return "/" + parts[1]
    return "/"


def match_monitors(mobula_monitors: List[Monitor], zobula_monitors: List[Monitor]) -> Dict[str, Optional[Monitor]]:
    """
    Match mobula.io monitors with their zobula.xyz counterparts based on URL path.
    Returns a dict: {mobula_monitor_id: zobula_monitor or None}
    """
    matches = {}

    for mobula in mobula_monitors:
        mobula_path = extract_path_from_url(mobula.url)
        matched = None

        for zobula in zobula_monitors:
            zobula_path = extract_path_from_url(zobula.url)
            if mobula_path == zobula_path:
                matched = zobula
                break

        matches[mobula.id] = matched

    return matches


def main():
    print("=" * 80)
    print("Better Stack Monitor Auto-Synchronization Tool")
    print("=" * 80)
    print()

    # Initialize API client
    api = BetterStackAPI(API_TOKEN)

    # Fetch all monitors
    all_monitors = api.get_all_monitors()

    # Separate mobula.io and zobula.xyz monitors
    mobula_monitors = [m for m in all_monitors if "mobula.io" in m.url]
    zobula_monitors = [m for m in all_monitors if "zobula.xyz" in m.url]

    print(f"Mobula.io monitors (prod): {len(mobula_monitors)}")
    print(f"Zobula.xyz monitors (duplica): {len(zobula_monitors)}")
    print()

    # Filter mobula monitors that have call setup enabled
    mobula_with_call = [m for m in mobula_monitors if m.call]

    print("=" * 80)
    print(f"Mobula.io monitors with CALL SETUP enabled: {len(mobula_with_call)}")
    print("=" * 80)
    print()

    # Match monitors
    matches = match_monitors(mobula_with_call, zobula_monitors)

    # Find monitors that need sync
    needs_sync = []

    for mobula_id, zobula_monitor in matches.items():
        mobula_monitor = next(m for m in mobula_with_call if m.id == mobula_id)

        if zobula_monitor is not None and zobula_monitor.call != mobula_monitor.call:
            needs_sync.append((mobula_monitor, zobula_monitor))

    if not needs_sync:
        print("All monitors are already synchronized!")
        print("=" * 80)
        return

    print(f"Found {len(needs_sync)} monitor(s) that need synchronization")
    print()

    # Perform synchronization
    print("=" * 80)
    print("STARTING AUTOMATIC SYNCHRONIZATION")
    print("=" * 80)
    print()

    success_count = 0
    fail_count = 0

    for i, (mobula_monitor, zobula_monitor) in enumerate(needs_sync, 1):
        print(f"[{i}/{len(needs_sync)}] Syncing: {zobula_monitor.name}")
        print(f"  Zobula ID: {zobula_monitor.id}")
        print(f"  Setting call={mobula_monitor.call} (currently call={zobula_monitor.call})")

        if api.update_monitor_call(zobula_monitor.id, mobula_monitor.call):
            print(f"  SUCCESS")
            success_count += 1
        else:
            print(f"  FAILED")
            fail_count += 1
        print()

    # Final summary
    print("=" * 80)
    print("SYNCHRONIZATION RESULTS")
    print("=" * 80)
    print(f"Successfully synced: {success_count}")
    print(f"Failed: {fail_count}")
    print(f"Total processed: {len(needs_sync)}")
    print()

    if fail_count == 0:
        print("All monitors synchronized successfully!")
    else:
        print(f"Warning: {fail_count} monitor(s) failed to sync")
        sys.exit(1)

    print("=" * 80)


if __name__ == "__main__":
    main()
