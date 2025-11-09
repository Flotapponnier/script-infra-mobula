#!/usr/bin/env python3
"""
Datadog Alert Summary Script
Ce script récupère toutes les alertes actives de Datadog et envoie un résumé sur Slack
"""

import os
import sys
import json
from datetime import datetime
from typing import List, Dict, Any
from collections import defaultdict
import requests


class DatadogAlertSummary:
    def __init__(self):
        self.dd_api_key = os.getenv("DATADOG_API_KEY")
        self.dd_app_key = os.getenv("DATADOG_APP_KEY")
        self.slack_webhook_preprod = os.getenv("SLACK_WEBHOOK_PREPROD")
        self.slack_webhook_prod = os.getenv("SLACK_WEBHOOK_PROD")
        self.dd_site = os.getenv("DATADOG_SITE", "datadoghq.eu")

        if not all([self.dd_api_key, self.dd_app_key, self.slack_webhook_preprod, self.slack_webhook_prod]):
            raise ValueError("Missing required environment variables: DATADOG_API_KEY, DATADOG_APP_KEY, SLACK_WEBHOOK_PREPROD, SLACK_WEBHOOK_PROD")

        self.base_url = f"https://api.{self.dd_site}"
        self.headers = {
            "DD-API-KEY": self.dd_api_key,
            "DD-APPLICATION-KEY": self.dd_app_key,
            "Content-Type": "application/json"
        }

    def get_all_monitors(self) -> List[Dict[str, Any]]:
        """Récupère tous les moniteurs de Datadog (preprod et prod)"""
        url = f"{self.base_url}/api/v1/monitor"

        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            monitors = response.json()

            # Filtrer uniquement les moniteurs contenant PROD ou PREPROD dans le nom
            filtered_monitors = []
            for monitor in monitors:
                name = monitor.get("name", "").upper()
                if "PREPROD" in name or "PROD" in name:
                    filtered_monitors.append(monitor)

            return filtered_monitors
        except requests.exceptions.RequestException as e:
            print(f"Error fetching monitors from Datadog: {e}", file=sys.stderr)
            return []

    def extract_environment_from_name(self, name: str) -> str:
        """Extrait l'environnement depuis le nom du monitor (PREPROD ou PROD)"""
        name_upper = name.upper()

        # Si contient PREPROD, c'est preprod (priorité à PREPROD)
        if "PREPROD" in name_upper:
            return "preprod"
        # Sinon si contient PROD, c'est prod
        elif "PROD" in name_upper:
            return "prod"

        return None

    def separate_monitors_by_environment(self, monitors: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Sépare les moniteurs par environnement (preprod vs prod)"""
        preprod_monitors = []
        prod_monitors = []

        for monitor in monitors:
            name = monitor.get("name", "")

            # Extraire l'environnement depuis le nom uniquement
            env = self.extract_environment_from_name(name)

            # Ajouter au bon groupe
            if env == "preprod":
                preprod_monitors.append(monitor)
            elif env == "prod":
                prod_monitors.append(monitor)

        return {
            "preprod": preprod_monitors,
            "prod": prod_monitors
        }

    def calculate_statistics(self, monitors: List[Dict[str, Any]]) -> Dict[str, int]:
        """Calcule les statistiques des moniteurs"""
        total = len(monitors)
        operational = 0
        down = 0
        paused = 0

        for monitor in monitors:
            overall_state = monitor.get("overall_state", "")

            # Check if monitor is muted/paused
            options = monitor.get("options", {})
            if options.get("silenced", {}):
                paused += 1
            elif overall_state in ["OK"]:
                operational += 1
            elif overall_state in ["Alert", "Warn", "No Data"]:
                down += 1
            else:
                operational += 1  # Default to operational

        uptime = (operational / total * 100) if total > 0 else 100

        return {
            "total": total,
            "operational": operational,
            "down": down,
            "paused": paused,
            "uptime": uptime
        }

    def get_active_alerts(self, monitors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filtre les moniteurs pour ne garder que ceux en alerte"""
        active_alerts = []
        for monitor in monitors:
            if monitor.get("overall_state") in ["Alert", "Warn", "No Data"]:
                active_alerts.append(monitor)
        return active_alerts

    def group_alerts_by_service(self, alerts: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Regroupe les alertes par service/catégorie de manière intelligente"""
        grouped = defaultdict(list)

        for alert in alerts:
            tags = alert.get("tags", [])
            name = alert.get("name", "Unknown")

            # Extraire la catégorie de manière intelligente
            category = None

            # 1. Chercher le tag service:
            for tag in tags:
                if tag.startswith("service:"):
                    category = tag.split(":", 1)[1].upper()
                    break

            # 2. Si pas de service, déduire depuis le nom du monitor
            if not category:
                name_lower = name.lower()
                if "kubernetes" in name_lower or "pod" in name_lower or "deployment" in name_lower:
                    category = "KUBERNETES"
                elif "redis" in name_lower:
                    category = "REDIS"
                elif "postgres" in name_lower or "database" in name_lower:
                    category = "POSTGRES"
                elif "rabbitmq" in name_lower:
                    category = "RABBITMQ"
                elif "disk" in name_lower or "memory" in name_lower or "cpu" in name_lower or "load" in name_lower or "network" in name_lower:
                    category = "SYSTEM"
                else:
                    category = "OTHER"

            alert_data = {
                "name": name,
                "status": alert.get("overall_state", "Unknown"),
                "message": alert.get("message", ""),
                "id": alert.get("id"),
                "query": alert.get("query", ""),
                "tags": tags,
                "monitor": alert  # Garder le monitor complet pour extraire les valeurs
            }

            grouped[category].append(alert_data)

        return dict(grouped)

    def get_monitor_groups(self, monitor: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extrait tous les groupes en alerte d'un monitor"""
        groups_info = []

        try:
            state = monitor.get("state", {})
            if isinstance(state, dict):
                groups = state.get("groups", {})
                if isinstance(groups, dict) and groups:
                    for group_name, group_data in groups.items():
                        if isinstance(group_data, dict):
                            # Ne garder que les groupes en alerte/warn/no data
                            group_status = group_data.get("status")
                            if group_status in ["Alert", "Warn", "No Data"]:
                                # Extraire la valeur si disponible
                                value = None
                                if "last_value" in group_data:
                                    try:
                                        value = round(float(group_data["last_value"]), 2)
                                    except (ValueError, TypeError):
                                        pass

                                groups_info.append({
                                    "name": group_name,
                                    "status": group_status,
                                    "value": value
                                })

            return groups_info
        except (ValueError, TypeError, KeyError):
            return []

    def clean_monitor_name(self, name: str, state: str, monitor: Dict[str, Any] = None) -> str:
        """Nettoie le nom du monitor des templates Datadog et remplace les valeurs si possible"""
        import re

        # Si le nom contient des conditions is_alert/is_recovery/is_warning
        if "{{#is_alert}}" in name and "{{/is_alert}}" in name:
            # Extraire la partie qui correspond à l'état actuel
            if state in ["Alert", "No Data"]:
                # Extraire la partie alert
                match = re.search(r'\{\{#is_alert\}\}(.*?)\{\{/is_alert\}\}', name, re.DOTALL)
                if match:
                    name = match.group(1)
            elif state == "Warn":
                # Essayer d'abord is_warning, puis fallback sur is_alert
                match_warn = re.search(r'\{\{#is_warning\}\}(.*?)\{\{/is_warning\}\}', name, re.DOTALL)
                if match_warn:
                    name = match_warn.group(1)
                else:
                    match = re.search(r'\{\{#is_alert\}\}(.*?)\{\{/is_alert\}\}', name, re.DOTALL)
                    if match:
                        name = match.group(1)
            else:
                # Extraire la partie recovery
                match = re.search(r'\{\{#is_recovery\}\}(.*?)\{\{/is_recovery\}\}', name, re.DOTALL)
                if match:
                    name = match.group(1)

        # Essayer d'obtenir la valeur actuelle du monitor depuis les groupes
        current_value = None
        if monitor:
            groups = self.get_monitor_groups(monitor)
            # Si un seul groupe ou pas de groupes, on peut afficher la valeur dans le titre
            if len(groups) <= 1 and groups:
                current_value = groups[0].get("value")

        # Remplacer {{value}} par la valeur réelle si disponible
        if "{{value}}" in name:
            if current_value is not None:
                name = re.sub(r'\{\{value\}\}', str(current_value), name)
            else:
                # Supprimer SEULEMENT {{value}}, garder le texte autour (bytes, %, etc.)
                name = re.sub(r'\{\{value\}\}', '', name)

        # Supprimer {{threshold}}
        if "{{threshold}}" in name:
            name = re.sub(r'\{\{threshold\}\}', '', name)

        # Supprimer les autres templates Datadog ({{variable.name}}, {{pod_name}}, etc.)
        name = re.sub(r'\{\{[^}]+\.name\}\}', '', name)
        name = re.sub(r'\{\{[^}]+\}\}', '', name)

        # Nettoyer les espaces multiples et tirets mal formés
        name = re.sub(r'\s*-\s*-\s*', ' - ', name)  # Double tirets
        name = re.sub(r'\s+-\s+', ' - ', name)  # Normaliser les tirets avec espaces
        name = re.sub(r'\s+', ' ', name)  # Espaces multiples
        name = re.sub(r'\s*-\s*$', '', name)  # Tiret à la fin

        return name.strip()

    def extract_alert_details(self, alert: Dict[str, Any]) -> str:
        """Extrait les détails importants du message d'alerte"""
        message = alert.get("message", "")
        query = alert.get("query", "")

        # Extraire les informations clés du message
        details = []

        # Chercher des valeurs numériques ou des seuils
        if "{{value}}" in message or "{{threshold}}" in message:
            # L'alerte contient des variables de template
            details.append("Check Datadog for current values")

        # Si le message est court, l'afficher directement
        if message and len(message) < 150:
            # Nettoyer le message des tags Slack/Datadog
            clean_msg = message.split("@webhook")[0].split("@slack")[0].strip()
            if clean_msg:
                details.append(clean_msg)

        return " | ".join(details) if details else ""

    def format_slack_message(self, statistics: Dict[str, int], grouped_alerts: Dict[str, List[Dict[str, Any]]], environment: str = "prod") -> Dict[str, Any]:
        """Formate le message Slack avec le résumé des alertes pour un environnement donné"""
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

        # Header avec statistiques globales
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

        # Statistiques globales dans un format compact
        stats_text = (
            f"*Total Monitors*\n{statistics['total']}\n\n"
            f"*Operational*\n▸ {statistics['operational']}\n\n"
            f"*Down*\n:small_red_triangle_down: {statistics['down']}\n\n"
        )

        if statistics['paused'] > 0:
            stats_text += f"*Paused*\n:double_vertical_bar: {statistics['paused']}\n\n"

        stats_text += f"*Uptime*\n{uptime:.1f}%"

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": stats_text
            }
        })

        blocks.append({"type": "divider"})

        # Si aucune alerte, message positif
        if total_alerts == 0:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":white_check_mark: *{environment.upper()} Environment - All Systems Operational*\n\nNo active alerts. All services are running smoothly!"
                }
            })
        else:
            # Afficher les alertes par service
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":office: *{environment.upper()} Environment*"
                }
            })

            # Ordre de priorité pour les catégories
            category_priority = {
                "REDIS_PUBSUB": 0,
                "REDIS": 1,
                "POSTGRES": 2,
                "RABBITMQ": 3,
                "KUBERNETES": 4,
                "SYSTEM": 5,
                "OTHER": 99
            }

            # Fonction de tri pour les catégories
            def sort_categories(item):
                category = item[0]
                return (category_priority.get(category, 50), category)

            # Section pour chaque catégorie avec alertes
            for category, alerts in sorted(grouped_alerts.items(), key=sort_categories):
                # Header de catégorie
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"🔴 *{category.upper()}*"
                    }
                })

                # Collecter toutes les alertes de cette catégorie
                alert_lines = []
                for alert in alerts:
                    name = alert["name"]
                    state = alert["status"]
                    alert_id = alert.get("id", "")
                    monitor = alert.get("monitor")

                    # Nettoyer le nom du monitor et essayer d'extraire les valeurs
                    clean_name = self.clean_monitor_name(name, state, monitor)

                    # Emoji selon le statut
                    status_emoji = ""
                    if state == "Alert":
                        status_emoji = "🔴"
                    elif state == "Warn":
                        status_emoji = "🟡"
                    elif state == "No Data":
                        status_emoji = "⚪"

                    # Créer le lien hyperlien cliquable
                    if alert_id:
                        monitor_url = f"https://app.{self.dd_site}/monitors/{alert_id}"
                        alert_lines.append(f"• {status_emoji} <{monitor_url}|{clean_name}>")
                    else:
                        alert_lines.append(f"• {status_emoji} {clean_name}")

                    # Afficher les groupes si présents
                    groups = self.get_monitor_groups(monitor)
                    if len(groups) > 1:  # Seulement si plusieurs groupes
                        for group in groups:
                            group_name = group["name"]
                            group_value = group["value"]
                            # Formater le nom du groupe (enlever les préfixes techniques)
                            display_name = group_name.replace("_", " ").title()
                            if group_value is not None:
                                alert_lines.append(f"  ↳ {display_name}: {group_value}")
                            else:
                                alert_lines.append(f"  ↳ {display_name}")

                # Ajouter toutes les alertes dans un seul bloc
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

    def send_to_slack(self, message: Dict[str, Any], environment: str = "prod") -> bool:
        """Envoie le message sur Slack pour l'environnement donné"""
        # Sélectionner le bon webhook selon l'environnement
        webhook_url = self.slack_webhook_prod if environment == "prod" else self.slack_webhook_preprod

        try:
            response = requests.post(
                webhook_url,
                json=message,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            print(f"Message sent to Slack ({environment}) successfully")
            return True
        except requests.exceptions.RequestException as e:
            print(f"Error sending message to Slack ({environment}): {e}", file=sys.stderr)
            return False

    def run(self):
        """Execute le processus complet pour preprod et prod"""
        print("Starting Datadog Alert Summary for PREPROD and PROD environments")

        # Récupérer tous les moniteurs (preprod + prod)
        print("Fetching all monitors from Datadog...")
        all_monitors = self.get_all_monitors()
        print(f"Found {len(all_monitors)} total monitors")

        # Séparer les moniteurs par environnement
        monitors_by_env = self.separate_monitors_by_environment(all_monitors)
        preprod_monitors = monitors_by_env["preprod"]
        prod_monitors = monitors_by_env["prod"]
        print(f"Split: {len(preprod_monitors)} preprod monitors, {len(prod_monitors)} prod monitors")

        # Traiter chaque environnement séparément
        success_preprod = self._process_environment("preprod", preprod_monitors)
        success_prod = self._process_environment("prod", prod_monitors)

        # Retourner succès si au moins un environnement a réussi
        if success_preprod or success_prod:
            print("✅ Alert summaries sent successfully!")
            return 0
        else:
            print("❌ Failed to send alert summaries", file=sys.stderr)
            return 1

    def _process_environment(self, environment: str, monitors: List[Dict[str, Any]]) -> bool:
        """Traite un environnement spécifique"""
        print(f"\n--- Processing {environment.upper()} environment ---")

        if not monitors:
            print(f"No monitors found for {environment}")
            return True

        # Calculer les statistiques
        statistics = self.calculate_statistics(monitors)
        print(f"[{environment.upper()}] Statistics: {statistics['operational']} operational, {statistics['down']} down, {statistics['paused']} paused")

        # Récupérer uniquement les alertes actives
        active_alerts = self.get_active_alerts(monitors)
        print(f"[{environment.upper()}] Found {len(active_alerts)} active alerts")

        # Grouper par service
        grouped_alerts = self.group_alerts_by_service(active_alerts)
        print(f"[{environment.upper()}] Alerts grouped by {len(grouped_alerts)} services")

        # Formatter le message Slack
        slack_message = self.format_slack_message(statistics, grouped_alerts, environment)

        # Envoyer à Slack
        print(f"[{environment.upper()}] Sending summary to Slack...")
        success = self.send_to_slack(slack_message, environment)

        if success:
            print(f"[{environment.upper()}] ✅ Summary sent successfully!")
        else:
            print(f"[{environment.upper()}] ❌ Failed to send summary", file=sys.stderr)

        return success


if __name__ == "__main__":
    try:
        summary = DatadogAlertSummary()
        sys.exit(summary.run())
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)
