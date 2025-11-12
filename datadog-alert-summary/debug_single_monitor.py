#!/usr/bin/env python3
"""
Script pour analyser un monitor en détail
"""

import os
import sys
import json
import requests


def main():
    # ID d'un monitor en alerte (Node Memory High)
    monitor_id = 93160257  # [Alert] Node Memory High

    dd_api_key = os.getenv("DATADOG_API_KEY")
    dd_app_key = os.getenv("DATADOG_APP_KEY")
    dd_site = "datadoghq.eu"

    base_url = f"https://api.{dd_site}"
    headers = {
        "DD-API-KEY": dd_api_key,
        "DD-APPLICATION-KEY": dd_app_key,
        "Content-Type": "application/json"
    }

    print("=" * 80)
    print(f"Fetching monitor ID: {monitor_id}")
    print("=" * 80)

    # Récupérer le monitor
    url = f"{base_url}/api/v1/monitor/{monitor_id}"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    monitor = response.json()

    print("\n📋 FULL MONITOR DATA:")
    print("=" * 80)
    print(json.dumps(monitor, indent=2))

    print("\n" + "=" * 80)
    print("🔍 KEY FIELDS ANALYSIS:")
    print("=" * 80)

    print(f"\nName: {monitor.get('name')}")
    print(f"ID: {monitor.get('id')}")
    print(f"Overall State: {monitor.get('overall_state')}")
    print(f"Query: {monitor.get('query')}")

    print("\n📊 STATE OBJECT:")
    state = monitor.get('state', {})
    print(json.dumps(state, indent=2))

    print("\n⚙️  OPTIONS OBJECT:")
    options = monitor.get('options', {})
    print(json.dumps(options, indent=2))

    # Sauvegarder
    with open(f"monitor_{monitor_id}_full.json", "w") as f:
        json.dump(monitor, f, indent=2)
    print(f"\n✅ Saved to monitor_{monitor_id}_full.json")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"💥 Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
