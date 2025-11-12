#!/usr/bin/env python3
"""
Test de l'API /api/v1/monitor/search
"""

import os
import json
import requests

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
print("Testing /api/v1/monitor/search endpoint")
print("=" * 80)

# Search pour monitors en alerte
url = f"{base_url}/api/v1/monitor/search"
params = {
    "query": "status:(Alert OR Warn OR \"No Data\") AND (env:prod OR env:preprod)"
}

print(f"\nURL: {url}")
print(f"Params: {params}")

response = requests.get(url, headers=headers, params=params)
print(f"\nStatus Code: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    print(f"\n📊 Results:")
    print(json.dumps(data, indent=2)[:2000])  # Limiter la sortie

    # Sauvegarder
    with open("search_api_response.json", "w") as f:
        json.dump(data, f, indent=2)
    print("\n✅ Saved to search_api_response.json")
else:
    print(f"\n❌ Error: {response.text}")
