#!/usr/bin/env python3
"""
Better Stack Monitor List Script
Lists all monitors with mobula.io URLs that have call setup,
and shows which zobula.xyz duplicates need synchronization.
This is a read-only script that doesn't modify anything.
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
    print("Better Stack Monitor List Tool (Read-Only)")
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

    if mobula_with_call:
        print("List of mobula.io monitors with call setup:")
        for i, monitor in enumerate(mobula_with_call, 1):
            print(f"{i:2d}. {monitor.name}")
            print(f"    URL: {monitor.url}")
            print(f"    ID: {monitor.id}")
            print()

    # Match monitors
    matches = match_monitors(mobula_with_call, zobula_monitors)

    print("=" * 80)
    print("Monitor Matching Results")
    print("=" * 80)
    print()

    matched_count = sum(1 for v in matches.values() if v is not None)
    unmatched_count = sum(1 for v in matches.values() if v is None)

    print(f"Matched pairs: {matched_count}")
    print(f"Unmatched (no zobula.xyz duplicate found): {unmatched_count}")
    print()

    # Display matches and synchronization needs
    needs_sync = []
    already_synced = []
    no_match = []

    for mobula_id, zobula_monitor in matches.items():
        mobula_monitor = next(m for m in mobula_with_call if m.id == mobula_id)

        if zobula_monitor is None:
            no_match.append(mobula_monitor)
        elif zobula_monitor.call != mobula_monitor.call:
            needs_sync.append((mobula_monitor, zobula_monitor))
        else:
            already_synced.append((mobula_monitor, zobula_monitor))

    # Show monitors that need sync
    if needs_sync:
        print("=" * 80)
        print(f"MONITORS NEEDING SYNCHRONIZATION: {len(needs_sync)}")
        print("=" * 80)
        print()
        for i, (mobula_monitor, zobula_monitor) in enumerate(needs_sync, 1):
            print(f"{i:2d}. {mobula_monitor.name}")
            print(f"    Mobula:  {mobula_monitor.url}")
            print(f"             call={mobula_monitor.call}, ID={mobula_monitor.id}")
            print(f"    Zobula:  {zobula_monitor.url}")
            print(f"             call={zobula_monitor.call}, ID={zobula_monitor.id}")
            print()

    # Show monitors already synced
    if already_synced:
        print("=" * 80)
        print(f"ALREADY SYNCHRONIZED: {len(already_synced)}")
        print("=" * 80)
        print()
        for i, (mobula_monitor, zobula_monitor) in enumerate(already_synced, 1):
            print(f"{i:2d}. {mobula_monitor.name}")
            print(f"    Both have call={mobula_monitor.call}")
            print()

    # Show monitors without match
    if no_match:
        print("=" * 80)
        print(f"NO ZOBULA DUPLICATE FOUND: {len(no_match)}")
        print("=" * 80)
        print()
        for i, monitor in enumerate(no_match, 1):
            print(f"{i:2d}. {monitor.name}")
            print(f"    URL: {monitor.url}")
            print(f"    ID: {monitor.id}")
            print()

    # Final summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total mobula.io monitors with call setup: {len(mobula_with_call)}")
    print(f"  - Already synchronized: {len(already_synced)}")
    print(f"  - Need synchronization: {len(needs_sync)}")
    print(f"  - No zobula duplicate: {len(no_match)}")
    print()

    if needs_sync:
        print("To synchronize, run: python3 sync_monitors.py")
    else:
        print("All monitors are synchronized!")

    print("=" * 80)


if __name__ == "__main__":
    main()
