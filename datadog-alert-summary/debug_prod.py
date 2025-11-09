#!/usr/bin/env python3
import requests
import json
import os
import re

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

# Chercher moniteurs avec [PROD] dans le nom
prod_monitors = []
for monitor in monitors:
    name = monitor.get("name", "")
    if re.search(r'\[PROD(?:\s+[^\]]+)?\]', name, re.IGNORECASE):
        if not re.search(r'\[PREPROD', name, re.IGNORECASE):
            prod_monitors.append(monitor)
            print(f"PROD Monitor: {name[:100]}")
            print(f"  State: {monitor.get('overall_state')}")
            print(f"  Tags: {monitor.get('tags', [])}")

            # Afficher les groupes
            state = monitor.get('state', {})
            if isinstance(state, dict):
                groups = state.get('groups', {})
                if groups:
                    print(f"  Groups ({len(groups)}): {list(groups.keys())[:5]}")
                    # Afficher le premier groupe en détail
                    first_group = list(groups.items())[0]
                    print(f"  Premier groupe détails:")
                    print(json.dumps(first_group[1], indent=4))
            print()

print(f"\nTotal PROD monitors trouvés: {len(prod_monitors)}")
