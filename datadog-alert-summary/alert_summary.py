#!/usr/bin/env python3
"""
Datadog Alert Summary Script - Version 3 (Final)
Utilise l'API search pour récupérer toutes les alertes actives
Simplifié sans extraction des group values (pour l'instant)
"""

import os
import sys
import json
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from collections import defaultdict
from urllib.parse import quote
import requests


class DatadogAlertSummary:
    def __init__(self):
        self.dd_api_key = os.getenv("DATADOG_API_KEY")
        self.dd_app_key = os.getenv("DATADOG_APP_KEY")
        self.slack_webhook_preprod = os.getenv("SLACK_WEBHOOK_PREPROD")
        self.slack_webhook_prod = os.getenv("SLACK_WEBHOOK_PROD")
        self.dd_site = os.getenv("DATADOG_SITE", "datadoghq.eu")

        if not all([self.dd_api_key, self.dd_app_key, self.slack_webhook_preprod, self.slack_webhook_prod]):
            raise ValueError("Missing required environment variables")

        self.base_url = f"https://api.{self.dd_site}"
        self.headers = {
            "DD-API-KEY": self.dd_api_key,
            "DD-APPLICATION-KEY": self.dd_app_key,
            "Content-Type": "application/json"
        }

    def get_all_monitors_search(self) -> List[Dict[str, Any]]:
        """Récupère tous les moniteurs via l'API search (plus fiable)"""
        url = f"{self.base_url}/api/v1/monitor/search"
        params = {
            "query": "(env:prod OR env:preprod OR env:staging)"
        }

        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json()
            return data.get("monitors", [])
        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching monitors from Datadog: {e}", file=sys.stderr)
            return []

    def get_active_alerts_search(self) -> List[Dict[str, Any]]:
        """Récupère uniquement les alertes actives via l'API search"""
        url = f"{self.base_url}/api/v1/monitor/search"
        params = {
            "query": 'status:(Alert OR Warn OR "No Data") AND (env:prod OR env:preprod OR env:staging)'
        }

        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json()
            monitors = data.get("monitors", [])

            # Enrichir chaque monitor avec ses group_states
            print(f"   Fetching group states for {len(monitors)} alerts...")
            for monitor in monitors:
                monitor_id = monitor.get("id")
                if monitor_id:
                    groups = self._get_monitor_group_states(monitor_id)
                    monitor["group_states"] = groups

            return monitors
        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching active alerts from Datadog: {e}", file=sys.stderr)
            return []

    def _get_monitor_group_states(self, monitor_id: int) -> List[Dict[str, Any]]:
        """Récupère les group states d'un monitor spécifique"""
        url = f"{self.base_url}/api/v1/monitor/{monitor_id}"
        params = {"group_states": "all"}

        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json()

            # Extraire les groupes en alerte
            state = data.get("state", {})
            groups = state.get("groups", {})

            result = []
            if isinstance(groups, dict):
                for group_name, group_data in groups.items():
                    if isinstance(group_data, dict):
                        status = group_data.get("status")
                        # Ne garder que les groupes en alerte/warn/no data
                        if status in ["Alert", "Warn", "No Data"]:
                            result.append({
                                "name": group_name,
                                "status": status,
                                "last_nodata_ts": group_data.get("last_nodata_ts")
                            })

            return result
        except requests.exceptions.RequestException as e:
            # Ne pas bloquer si l'appel échoue
            return []

    def _detect_environment(self, monitor: Dict[str, Any]) -> Optional[str]:
        """Détecte l'environnement: tags > scopes > query > nom"""
        # 1. Tags
        tags = monitor.get("tags", [])
        for tag in tags:
            tag_lower = tag.lower()
            if tag_lower.startswith("env:"):
                env_value = tag_lower.split(":", 1)[1]
                if "preprod" in env_value or "pre-prod" in env_value or env_value == "staging":
                    return "preprod"
                elif env_value == "prod" or env_value == "production":
                    return "prod"

        # 2. Scopes (nouveau dans search API)
        scopes = monitor.get("scopes", [])
        for scope in scopes:
            scope_lower = scope.lower()
            if "env:preprod" in scope_lower or "env:staging" in scope_lower:
                return "preprod"
            elif "env:prod" in scope_lower:
                return "prod"

        # 3. Query
        query = monitor.get("query", "").lower()
        if "env:preprod" in query or "env:staging" in query:
            return "preprod"
        elif "env:prod" in query:
            return "prod"

        # 4. Nom (fallback)
        name = monitor.get("name", "").upper()
        if "PREPROD" in name or "PRE-PROD" in name:
            return "preprod"
        elif "PROD" in name and "PREPROD" not in name:
            return "prod"

        return None

    def _extract_service(self, monitor: Dict[str, Any]) -> str:
        """Extrait le service depuis les tags"""
        tags = monitor.get("tags", [])
        for tag in tags:
            if tag.startswith("service:"):
                service = tag.split(":", 1)[1]
                if service == "all":
                    # Si service:all, essayer de déduire depuis les métriques
                    metrics = monitor.get("metrics", [])
                    if any("kubernetes" in m for m in metrics):
                        return "KUBERNETES"
                    return "SYSTEM"
                return service.upper()

        # Fallback: déduire depuis les métriques ou le nom
        metrics = monitor.get("metrics", [])
        name = monitor.get("name", "").lower()
        query = monitor.get("query", "").lower()

        if any("redis" in m for m in metrics) or "redis" in name or "redis" in query:
            return "REDIS"
        elif any("postgres" in m for m in metrics) or "postgres" in name or "database" in name:
            return "POSTGRESQL"
        elif any("kubernetes" in m for m in metrics) or "pod" in name or "container" in name:
            return "KUBERNETES"
        elif "disk" in name or "memory" in name or "cpu" in name:
            return "SYSTEM"
        else:
            return "OTHER"

    def separate_by_environment(self, monitors: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Sépare les moniteurs par environnement"""
        preprod = []
        prod = []

        for monitor in monitors:
            env = self._detect_environment(monitor)
            if env == "preprod":
                preprod.append(monitor)
            elif env == "prod":
                prod.append(monitor)

        return {"preprod": preprod, "prod": prod}

    def group_by_service(self, monitors: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Groupe les moniteurs par service"""
        grouped = defaultdict(list)
        for monitor in monitors:
            service = self._extract_service(monitor)
            grouped[service].append(monitor)
        return dict(grouped)

    def calculate_statistics(self, all_monitors: List[Dict[str, Any]], active_alerts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calcule les statistiques"""
        total = len(all_monitors)
        down = len(active_alerts)
        operational = total - down
        uptime = (operational / total * 100) if total > 0 else 100

        return {
            "total": total,
            "operational": operational,
            "down": down,
            "paused": 0,  # TODO: extraire depuis muted_until_ts
            "uptime": uptime
        }

    def _format_group_name(self, group_name: str) -> str:
        """Formate un nom de groupe pour l'affichage (ex: 'host:server1' -> 'Host: server1')"""
        if ':' in group_name:
            parts = group_name.split(':', 1)
            key = parts[0].replace('_', ' ').title()
            value = parts[1]
            return f"{key}: {value}"
        else:
            return group_name.replace('_', ' ').title()

    def _clean_monitor_name(self, monitor: Dict[str, Any]) -> str:
        """Nettoie le nom du monitor des templates Datadog"""
        name = monitor.get("name", "Unknown")
        status = monitor.get("status", "Unknown")

        # Extraire la bonne section selon le statut
        if "{{#is_alert}}" in name:
            if status in ["Alert", "No Data"]:
                match = re.search(r'\{\{#is_alert\}\}(.*?)\{\{/is_alert\}\}', name, re.DOTALL)
                if match:
                    name = match.group(1)
            elif status == "Warn":
                match_warn = re.search(r'\{\{#is_warning\}\}(.*?)\{\{/is_warning\}\}', name, re.DOTALL)
                if match_warn:
                    name = match_warn.group(1)
                else:
                    match = re.search(r'\{\{#is_alert\}\}(.*?)\{\{/is_alert\}\}', name, re.DOTALL)
                    if match:
                        name = match.group(1)

        # Supprimer tous les templates {{xxx}}
        name = re.sub(r'\{\{[^}]+\}\}', '', name)

        # Nettoyer le formatting
        name = re.sub(r'\s*-\s*-\s*', ' - ', name)
        name = re.sub(r'\s+-\s+', ' - ', name)
        name = re.sub(r'\s+', ' ', name)
        name = re.sub(r'\s*-\s*$', '', name)
        name = re.sub(r'^\s*-\s*', '', name)

        return name.strip()

    def format_slack_message(self, statistics: Dict[str, Any], grouped_alerts: Dict[str, List[Dict[str, Any]]], environment: str) -> Dict[str, Any]:
        """Formate le message Slack"""
        total_alerts = sum(len(alerts) for alerts in grouped_alerts.values())
        uptime = statistics["uptime"]

        # Emoji basé sur l'uptime
        if uptime >= 95:
            status_emoji = "✅"
            status_text = "Operational"
        elif uptime >= 80:
            status_emoji = "⚠️"
            status_text = "Issues Detected"
        else:
            status_emoji = "🚨"
            status_text = "Critical Issues"

        blocks = []

        # Header
        blocks.append({
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{status_emoji} Infrastructure Health - {uptime:.1f}% Operational"
            }
        })

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f":bar_chart: *System Overview - {status_text}*"
            }
        })

        # Statistiques
        stats_text = (
            f"*Total Monitors*\n{statistics['total']}\n\n"
            f"*Operational*\n▸ {statistics['operational']}\n\n"
            f"*Down*\n:small_red_triangle_down: {statistics['down']}\n\n"
            f"*Uptime*\n{uptime:.1f}%"
        )

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": stats_text
            }
        })

        blocks.append({"type": "divider"})

        # Alertes
        if total_alerts == 0:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":white_check_mark: *{environment.upper()} Environment - All Systems Operational*\n\nNo active alerts!"
                }
            })
        else:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":office: *{environment.upper()} Environment*"
                }
            })

            # Séparer les alertes par statut: Alert/Warn vs No Data
            regular_alerts = {}
            no_data_alerts = {}

            for category, alerts in grouped_alerts.items():
                regular = []
                no_data = []
                for alert in alerts:
                    if alert.get("status") == "No Data":
                        no_data.append(alert)
                    else:
                        regular.append(alert)

                if regular:
                    regular_alerts[category] = regular
                if no_data:
                    no_data_alerts[category] = no_data

            # Priorités
            category_priority = {
                "REDIS": 0,
                "POSTGRESQL": 1,
                "RABBITMQ": 2,
                "KUBERNETES": 3,
                "SYSTEM": 4,
                "OTHER": 99
            }

            # Afficher d'abord les alertes régulières (Alert/Warn)
            if regular_alerts:
                sorted_categories = sorted(
                    regular_alerts.items(),
                    key=lambda x: (category_priority.get(x[0], 50), x[0])
                )

                for category, alerts in sorted_categories:
                    blocks.append({
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"🔴 *{category}*"
                        }
                    })

                    # Créer un bloc séparé pour chaque alerte
                    for monitor in alerts:
                        alert_lines = []
                        clean_name = self._clean_monitor_name(monitor)
                        status = monitor.get("status", "Unknown")
                        monitor_id = monitor.get("id", "")

                        # Emoji
                        if status == "Alert":
                            emoji = "🔴"
                        elif status == "Warn":
                            emoji = "🟡"
                        else:
                            emoji = "⚫"

                        # Lien vers Datadog
                        if monitor_id:
                            url = f"https://app.{self.dd_site}/monitors/{monitor_id}"
                            alert_lines.append(f"• {emoji} <{url}|{clean_name}>")
                        else:
                            alert_lines.append(f"• {emoji} {clean_name}")

                        # Afficher les sous-groupes si présents (limité à 5 max)
                        group_states = monitor.get("group_states", [])
                        if group_states:
                            total_groups = len(group_states)
                            # Limiter à 5 groupes max
                            for group in group_states[:5]:
                                group_name = self._format_group_name(group["name"])
                                group_status = group["status"]

                                # Emoji pour le groupe
                                if group_status == "Alert":
                                    group_emoji = "🔴"
                                elif group_status == "Warn":
                                    group_emoji = "🟡"
                                elif group_status == "No Data":
                                    group_emoji = "⚪"
                                else:
                                    group_emoji = "⚫"

                                # Créer l'URL pour ce groupe spécifique
                                if monitor_id:
                                    encoded_group = quote(group['name'], safe='')
                                    group_url = f"https://app.{self.dd_site}/monitors/{monitor_id}?group={encoded_group}"
                                    alert_lines.append(f"  ↳ {group_emoji} <{group_url}|{group_name}>")
                                else:
                                    alert_lines.append(f"  ↳ {group_emoji} {group_name}")

                            # Si plus de 5, afficher le compte avec lien vers le monitor
                            if total_groups > 5:
                                remaining = total_groups - 5
                                if monitor_id:
                                    all_groups_url = f"https://app.{self.dd_site}/monitors/{monitor_id}"
                                    alert_lines.append(f"  ↳ <{all_groups_url}|... and {remaining} more>")
                                else:
                                    alert_lines.append(f"  ↳ ... and {remaining} more")

                        # Un bloc par alerte (au lieu de toutes les alertes dans un seul bloc)
                        blocks.append({
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": "\n".join(alert_lines)
                            }
                        })

            # Ajouter une section séparée pour les No Data
            if no_data_alerts:
                blocks.append({"type": "divider"})
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "⚪ *[Alerts with No Data]*"
                    }
                })

                sorted_no_data = sorted(
                    no_data_alerts.items(),
                    key=lambda x: (category_priority.get(x[0], 50), x[0])
                )

                for category, alerts in sorted_no_data:
                    blocks.append({
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"⚪ *{category}*"
                        }
                    })

                    # Créer un bloc séparé pour chaque alerte No Data
                    for monitor in alerts:
                        alert_lines = []
                        clean_name = self._clean_monitor_name(monitor)
                        monitor_id = monitor.get("id", "")

                        # Lien vers Datadog
                        if monitor_id:
                            url = f"https://app.{self.dd_site}/monitors/{monitor_id}"
                            alert_lines.append(f"• ⚪ <{url}|{clean_name}>")
                        else:
                            alert_lines.append(f"• ⚪ {clean_name}")

                        # Afficher les sous-groupes si présents (limité à 5 max)
                        group_states = monitor.get("group_states", [])
                        if group_states:
                            total_groups = len(group_states)
                            for group in group_states[:5]:
                                group_name = self._format_group_name(group["name"])

                                # Créer l'URL pour ce groupe spécifique
                                if monitor_id:
                                    encoded_group = quote(group['name'], safe='')
                                    group_url = f"https://app.{self.dd_site}/monitors/{monitor_id}?group={encoded_group}"
                                    alert_lines.append(f"  ↳ ⚪ <{group_url}|{group_name}>")
                                else:
                                    alert_lines.append(f"  ↳ ⚪ {group_name}")

                            if total_groups > 5:
                                remaining = total_groups - 5
                                if monitor_id:
                                    all_groups_url = f"https://app.{self.dd_site}/monitors/{monitor_id}"
                                    alert_lines.append(f"  ↳ <{all_groups_url}|... and {remaining} more>")
                                else:
                                    alert_lines.append(f"  ↳ ... and {remaining} more")

                        # Un bloc par alerte
                        blocks.append({
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": "\n".join(alert_lines)
                            }
                        })

        blocks.append({"type": "divider"})

        # Footer
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Mobula Monitoring System | {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"
                }
            ]
        })

        return {"blocks": blocks}

    def send_to_slack(self, message: Dict[str, Any], environment: str) -> bool:
        """Envoie le message sur Slack"""
        webhook_url = self.slack_webhook_prod if environment == "prod" else self.slack_webhook_preprod

        try:
            # Debug: afficher la taille du message
            message_json = json.dumps(message)
            print(f"   Message size: {len(message_json)} bytes, {len(message.get('blocks', []))} blocks")

            response = requests.post(webhook_url, json=message, headers={"Content-Type": "application/json"})
            response.raise_for_status()
            print(f"✅ Message sent to Slack ({environment}) successfully")
            return True
        except requests.exceptions.RequestException as e:
            print(f"❌ Error sending to Slack ({environment}): {e}", file=sys.stderr)
            # Sauvegarder le message pour debug
            with open(f"slack_message_{environment}_error.json", "w") as f:
                json.dump(message, f, indent=2)
            print(f"   Message saved to slack_message_{environment}_error.json for debugging")
            return False

    def run(self):
        """Execute le processus complet"""
        print("=" * 60)
        print("Datadog Alert Summary v3")
        print("=" * 60)

        # Récupérer tous les monitors
        print("\n📡 Fetching all monitors...")
        all_monitors = self.get_all_monitors_search()
        print(f"   Found {len(all_monitors)} total monitors")

        # Récupérer les alertes actives
        print("\n🚨 Fetching active alerts...")
        active_alerts = self.get_active_alerts_search()
        print(f"   Found {len(active_alerts)} active alerts")

        # Séparer par environnement
        all_by_env = self.separate_by_environment(all_monitors)
        alerts_by_env = self.separate_by_environment(active_alerts)

        print(f"\n📊 Environment split:")
        print(f"   PREPROD: {len(all_by_env['preprod'])} total, {len(alerts_by_env['preprod'])} alerts")
        print(f"   PROD: {len(all_by_env['prod'])} total, {len(alerts_by_env['prod'])} alerts")

        # Traiter chaque environnement
        success_preprod = self._process_environment("preprod", all_by_env["preprod"], alerts_by_env["preprod"])
        success_prod = self._process_environment("prod", all_by_env["prod"], alerts_by_env["prod"])

        print("\n" + "=" * 60)
        if success_preprod or success_prod:
            print("✅ Alert summaries sent successfully!")
            return 0
        else:
            print("❌ Failed to send summaries")
            return 1

    def _process_environment(self, environment: str, all_monitors: List[Dict[str, Any]], active_alerts: List[Dict[str, Any]]) -> bool:
        """Traite un environnement spécifique"""
        print(f"\n--- Processing {environment.upper()} ---")

        if not all_monitors:
            print(f"   ⚠️  No monitors found")
            return True

        # Statistiques
        statistics = self.calculate_statistics(all_monitors, active_alerts)
        print(f"   📈 Stats: {statistics['operational']} OK | {statistics['down']} Down")

        # Grouper par service
        grouped_alerts = self.group_by_service(active_alerts)
        if grouped_alerts:
            for category, alerts in grouped_alerts.items():
                print(f"      • {category}: {len(alerts)} alerts")

        # Formatter et envoyer
        slack_message = self.format_slack_message(statistics, grouped_alerts, environment)
        print(f"   📤 Sending to Slack...")
        return self.send_to_slack(slack_message, environment)


if __name__ == "__main__":
    try:
        summary = DatadogAlertSummary()
        sys.exit(summary.run())
    except Exception as e:
        print(f"💥 Fatal error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
