#!/usr/bin/env python3
"""
Script de test pour comparer les deux versions du script d'alertes Datadog
"""

import os
import sys
import json
from alert_summary import DatadogAlertSummary as V1
from alert_summary_v2 import DatadogAlertSummary as V2


def test_environment_detection():
    """Test de la détection d'environnement"""
    print("=" * 60)
    print("TEST: Environment Detection")
    print("=" * 60)

    test_monitors = [
        {
            "name": "[PROD] Redis High Memory",
            "tags": ["service:redis", "env:prod"],
            "query": "avg(last_5m):avg:redis.mem.used{env:prod} > 90"
        },
        {
            "name": "[PREPROD] API Response Time",
            "tags": ["env:preprod"],
            "query": "avg(last_5m):avg:http.response_time{env:preprod} > 1000"
        },
        {
            "name": "Production Database Connections",
            "tags": [],
            "query": "avg(last_5m):avg:postgres.connections{env:production} > 100"
        },
        {
            "name": "Staging Redis Down",
            "tags": ["env:staging"],
            "query": "avg(last_5m):avg:redis.can_connect{*} < 1"
        }
    ]

    v1 = V1()
    v2 = V2()

    print("\nTest monitors:")
    for i, monitor in enumerate(test_monitors, 1):
        name = monitor["name"]
        tags = monitor.get("tags", [])

        # V1 detection (nom uniquement)
        env_v1 = v1.extract_environment_from_name(name)

        # V2 detection (tags > query > nom)
        env_v2 = v2._detect_environment(monitor)

        print(f"\n{i}. {name}")
        print(f"   Tags: {tags}")
        print(f"   V1 detection: {env_v1}")
        print(f"   V2 detection: {env_v2}")
        if env_v1 != env_v2:
            print(f"   ⚠️  DIFFERENCE DETECTED")


def test_template_parsing():
    """Test du parsing des templates Datadog"""
    print("\n" + "=" * 60)
    print("TEST: Template Parsing")
    print("=" * 60)

    test_cases = [
        {
            "name": "{{#is_alert}}High memory usage: {{value}}% (threshold: {{threshold}}%){{/is_alert}}{{#is_recovery}}Memory back to normal{{/is_recovery}}",
            "state": "Alert",
            "monitor": {
                "state": {
                    "groups": {
                        "host:server1": {
                            "status": "Alert",
                            "last_value": 95.5,
                            "last_triggered_ts": 1234567890
                        }
                    }
                },
                "options": {
                    "thresholds": {
                        "critical": 90,
                        "warning": 80
                    }
                }
            }
        },
        {
            "name": "Pod {{pod_name.name}} is down - {{value}} replicas",
            "state": "Alert",
            "monitor": {
                "state": {
                    "groups": {
                        "pod:api-server": {
                            "status": "Alert",
                            "last_value": 0,
                            "last_triggered_ts": 1234567890
                        }
                    }
                },
                "options": {"thresholds": {"critical": 1}}
            }
        }
    ]

    v1 = V1()
    v2 = V2()

    for i, test in enumerate(test_cases, 1):
        name = test["name"]
        state = test["state"]
        monitor = test["monitor"]

        print(f"\n{i}. Original: {name}")

        # V1 cleaning
        clean_v1 = v1.clean_monitor_name(name, state, monitor)
        print(f"   V1 result: {clean_v1}")

        # V2 parsing
        clean_v2 = v2._parse_template_variables(name, state, monitor)
        print(f"   V2 result: {clean_v2}")

        if clean_v1 != clean_v2:
            print(f"   ⚠️  DIFFERENCE DETECTED")


def test_groups_extraction():
    """Test de l'extraction des groupes avec valeurs"""
    print("\n" + "=" * 60)
    print("TEST: Groups Extraction")
    print("=" * 60)

    test_monitor = {
        "name": "High CPU usage",
        "state": {
            "groups": {
                "host:server1": {
                    "status": "Alert",
                    "last_value": 95.5,
                    "last_triggered_ts": 1234567890
                },
                "host:server2": {
                    "status": "Warn",
                    "last_value": 85.2,
                    "last_triggered_ts": 1234567890
                },
                "host:server3": {
                    "status": "OK",
                    "last_value": 45.0,
                    "last_triggered_ts": 1234567890
                }
            }
        },
        "options": {
            "thresholds": {
                "critical": 90,
                "warning": 80
            }
        }
    }

    v1 = V1()
    v2 = V2()

    print("\nTest monitor with multiple groups:")
    print(f"Monitor: {test_monitor['name']}")

    # V1 groups
    groups_v1 = v1.get_monitor_groups(test_monitor)
    print(f"\nV1 groups extracted: {len(groups_v1)}")
    for group in groups_v1:
        print(f"  - {group}")

    # V2 groups
    groups_v2 = v2._get_monitor_groups_with_values(test_monitor)
    print(f"\nV2 groups extracted: {len(groups_v2)}")
    for group in groups_v2:
        print(f"  - {group}")


def main():
    """Execute tous les tests"""
    print("\n🧪 Datadog Alert Summary - Comparison Test Suite")
    print("Comparing V1 (old) vs V2 (new)\n")

    try:
        test_environment_detection()
        test_template_parsing()
        test_groups_extraction()

        print("\n" + "=" * 60)
        print("✅ All tests completed!")
        print("=" * 60)
        print("\nKey improvements in V2:")
        print("  • Better environment detection (tags > query > name)")
        print("  • Improved template parsing with value replacement")
        print("  • Better groups extraction with thresholds")
        print("  • Cleaner output formatting")
        print("  • Always shows groups (even for single group monitors)")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
