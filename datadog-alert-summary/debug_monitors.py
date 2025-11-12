#!/usr/bin/env python3
"""
Script de debug pour analyser tous les monitors Datadog
"""

import os
import sys
import json
from alert_summary_v2 import DatadogAlertSummary


def main():
    print("=" * 80)
    print("DEBUG: Analyzing all Datadog monitors")
    print("=" * 80)

    summary = DatadogAlertSummary()

    # Récupérer tous les monitors
    print("\n📡 Fetching ALL monitors from Datadog (no filter)...")
    all_monitors = summary.get_all_monitors()
    print(f"   Total monitors returned: {len(all_monitors)}")

    # Séparer par environnement
    monitors_by_env = summary.separate_monitors_by_environment(all_monitors)
    preprod_monitors = monitors_by_env["preprod"]
    prod_monitors = monitors_by_env["prod"]

    print(f"\n📊 Environment split:")
    print(f"   PREPROD: {len(preprod_monitors)}")
    print(f"   PROD: {len(prod_monitors)}")

    # Analyser PROD en détail
    print("\n" + "=" * 80)
    print("PROD MONITORS ANALYSIS")
    print("=" * 80)

    for i, monitor in enumerate(prod_monitors, 1):
        name = monitor.get("name", "Unknown")
        monitor_id = monitor.get("id", "N/A")
        overall_state = monitor.get("overall_state", "Unknown")
        tags = monitor.get("tags", [])
        query = monitor.get("query", "")

        print(f"\n{i}. [{overall_state}] {name}")
        print(f"   ID: {monitor_id}")
        print(f"   Tags: {tags[:3]}..." if len(tags) > 3 else f"   Tags: {tags}")

        # Vérifier la détection d'environnement
        env = summary._detect_environment(monitor)
        print(f"   Detected env: {env}")

        # Vérifier la catégorie de service
        if overall_state in ["Alert", "Warn", "No Data"]:
            service = summary._extract_service_from_monitor(monitor)
            print(f"   Service category: {service}")

            # Vérifier les groupes
            groups = summary._get_monitor_groups_with_values(monitor)
            if groups:
                print(f"   Groups ({len(groups)}):")
                for group in groups[:3]:  # Limiter à 3 pour lisibilité
                    print(f"      - {group['name']}: {group['status']} = {group['value']}")
            else:
                print(f"   Groups: None found")

            # Tester le parsing du nom
            clean_name = summary._parse_template_variables(name, overall_state, monitor)
            if clean_name != name:
                print(f"   Clean name: {clean_name}")

    # Compter les alertes actives
    print("\n" + "=" * 80)
    print("ACTIVE ALERTS SUMMARY")
    print("=" * 80)

    prod_alerts = summary.get_active_alerts(prod_monitors)
    preprod_alerts = summary.get_active_alerts(preprod_monitors)

    print(f"\nPROD: {len(prod_alerts)} active alerts")
    prod_grouped = summary.group_alerts_by_service(prod_alerts)
    for category, alerts in sorted(prod_grouped.items()):
        print(f"   • {category}: {len(alerts)} alerts")

    print(f"\nPREPROD: {len(preprod_alerts)} active alerts")
    preprod_grouped = summary.group_alerts_by_service(preprod_alerts)
    for category, alerts in sorted(preprod_grouped.items()):
        print(f"   • {category}: {len(alerts)} alerts")

    # Sauvegarder les données brutes pour analyse
    print("\n💾 Saving raw data to debug_output.json...")
    debug_data = {
        "total_monitors": len(all_monitors),
        "preprod_count": len(preprod_monitors),
        "prod_count": len(prod_monitors),
        "prod_monitors": [
            {
                "id": m.get("id"),
                "name": m.get("name"),
                "overall_state": m.get("overall_state"),
                "tags": m.get("tags", []),
                "query": m.get("query", "")[:100],  # Limiter la taille
            }
            for m in prod_monitors
        ],
        "preprod_monitors": [
            {
                "id": m.get("id"),
                "name": m.get("name"),
                "overall_state": m.get("overall_state"),
                "tags": m.get("tags", []),
                "query": m.get("query", "")[:100],
            }
            for m in preprod_monitors
        ]
    }

    with open("debug_output.json", "w") as f:
        json.dump(debug_data, f, indent=2)

    print("   ✅ Saved to debug_output.json")

    print("\n" + "=" * 80)
    print("DEBUG COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"💥 Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
