#!/usr/bin/env python3
"""
Better Stack Monitor Synchronization Script
Finds all monitors with mobula.io URLs that have call setup,
and ensures their zobula.xyz duplicates have the same call setup configuration.
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
    print("Better Stack Monitor Synchronization Tool")
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
        for monitor in mobula_with_call:
            print(f"  - {monitor.name}")
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

    for mobula_id, zobula_monitor in matches.items():
        mobula_monitor = next(m for m in mobula_with_call if m.id == mobula_id)

        if zobula_monitor is None:
            print(f"⚠️  NO MATCH FOUND for: {mobula_monitor.name}")
            print(f"   Mobula URL: {mobula_monitor.url}")
            print(f"   No corresponding zobula.xyz monitor found")
            print()
        elif zobula_monitor.call != mobula_monitor.call:
            needs_sync.append((mobula_monitor, zobula_monitor))
            print(f"🔄 NEEDS SYNC: {mobula_monitor.name}")
            print(f"   Mobula: {mobula_monitor.url} (call={mobula_monitor.call})")
            print(f"   Zobula: {zobula_monitor.url} (call={zobula_monitor.call})")
            print()
        else:
            already_synced.append((mobula_monitor, zobula_monitor))
            print(f"✅ ALREADY SYNCED: {mobula_monitor.name}")
            print(f"   Mobula: {mobula_monitor.url} (call={mobula_monitor.call})")
            print(f"   Zobula: {zobula_monitor.url} (call={zobula_monitor.call})")
            print()

    # Summary
    print("=" * 80)
    print("Synchronization Summary")
    print("=" * 80)
    print(f"Already synchronized: {len(already_synced)}")
    print(f"Needs synchronization: {len(needs_sync)}")
    print(f"No zobula duplicate found: {unmatched_count}")
    print()

    # Perform synchronization if needed
    if needs_sync:
        print("=" * 80)
        print("Performing Synchronization")
        print("=" * 80)
        print()

        response = input(f"Do you want to sync {len(needs_sync)} monitor(s)? (yes/no): ").strip().lower()

        if response in ["yes", "y"]:
            success_count = 0
            fail_count = 0

            for mobula_monitor, zobula_monitor in needs_sync:
                print(f"Syncing: {zobula_monitor.name}")
                print(f"  Setting call={mobula_monitor.call} on zobula monitor {zobula_monitor.id}")

                if api.update_monitor_call(zobula_monitor.id, mobula_monitor.call):
                    print(f"  ✅ Successfully updated")
                    success_count += 1
                else:
                    print(f"  ❌ Failed to update")
                    fail_count += 1
                print()

            print("=" * 80)
            print("Synchronization Results")
            print("=" * 80)
            print(f"Successfully synced: {success_count}")
            print(f"Failed: {fail_count}")
        else:
            print("Synchronization cancelled.")
    else:
        print("✅ All monitors are already synchronized!")

    print()
    print("=" * 80)
    print("Script completed!")
    print("=" * 80)


if __name__ == "__main__":
    main()
