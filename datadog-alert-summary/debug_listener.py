#!/usr/bin/env python3
import requests
import os

dd_api_key = os.getenv("DATADOG_API_KEY")
dd_app_key = os.getenv("DATADOG_APP_KEY")
dd_site = "datadoghq.eu"
base_url = f"https://api.{dd_site}"
headers = {
    "DD-API-KEY": dd_api_key,
    "DD-APPLICATION-KEY": dd_app_key,
}

response = requests.get(f"{base_url}/api/v1/monitor", headers=headers)
monitors = response.json()

# Chercher des monitors qui contiennent 'listener' dans le nom
print("=== Monitors contenant 'listener' ===\n")
for monitor in monitors:
    name = monitor.get("name", "")
    if "listener" in name.lower() and "cpu" in name.lower():
        print(f"Monitor: {name[:150]}")
        print(f"  State: {monitor.get('overall_state')}")
        print(f"  Tags: {monitor.get('tags', [])}")
        has_prod = "PROD" in name.upper()
        has_preprod = "PREPROD" in name.upper()
        print(f"  Contains PROD: {has_prod}")
        print(f"  Contains PREPROD: {has_preprod}")
        print()
