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

# Trouver le monitor Listener CPU PROD
for monitor in monitors:
    name = monitor.get("name", "")
    if "listener" in name.lower() and "cpu" in name.lower():
        name_upper = name.upper()

        # Logique actuelle du script
        if "PREPROD" in name_upper:
            env = "preprod"
        elif "PROD" in name_upper:
            env = "prod"
        else:
            env = None

        print(f"Monitor: {name[:80]}")
        print(f"  State: {monitor.get('overall_state')}")
        print(f"  Detected env: {env}")
        print(f"  PROD in name: {'PROD' in name_upper}")
        print(f"  PREPROD in name: {'PREPROD' in name_upper}")
        print()
