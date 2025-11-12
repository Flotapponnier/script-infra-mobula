#!/usr/bin/env python3
"""
Datadog Alert Summary Script - Version 2 (Improved)
Ce script récupère toutes les alertes actives de Datadog et envoie un résumé sur Slack
Améliorations: Meilleure gestion des templates, extraction des valeurs, et détection d'environnement
"""

import os
import sys
import json
import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
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
        """Récupère tous les moniteurs de Datadog avec leurs group_states"""
        url = f"{self.base_url}/api/v1/monitor"
        params = {
            "group_states": "all",  # IMPORTANT: récupérer tous les états des groupes
            "with_downtimes": "true"
        }

        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            monitors = response.json()

            # Filtrer uniquement les moniteurs PROD ou PREPROD
            filtered_monitors = []
            for monitor in monitors:
                env = self._detect_environment(monitor)
                if env in ["prod", "preprod"]:
                    filtered_monitors.append(monitor)

            return filtered_monitors
        except requests.exceptions.RequestException as e:
            print(f"Error fetching monitors from Datadog: {e}", file=sys.stderr)
            return []

    def _detect_environment(self, monitor: Dict[str, Any]) -> Optional[str]:
        """
        Détecte l'environnement d'un monitor (preprod ou prod)
        Priorité: tags > query > nom
        """
        # 1. Chercher dans les tags (le plus fiable)
        tags = monitor.get("tags", [])
        for tag in tags:
            tag_lower = tag.lower()
            if tag_lower.startswith("env:"):
                env_value = tag_lower.split(":", 1)[1]
                if "preprod" in env_value or "pre-prod" in env_value or env_value == "staging":
                    return "preprod"
                elif env_value == "prod" or env_value == "production":
                    return "prod"

        # 2. Chercher dans la query
        query = monitor.get("query", "").lower()
        if "env:preprod" in query or "env:pre-prod" in query or "env:staging" in query:
            return "preprod"
        elif "env:prod" in query or "env:production" in query:
            return "prod"

        # 3. Fallback sur le nom (moins fiable)
        name = monitor.get("name", "").upper()
        if "PREPROD" in name or "PRE-PROD" in name:
            return "preprod"
        elif "PROD" in name and "PREPROD" not in name:
            return "prod"

        return None

    def separate_monitors_by_environment(self, monitors: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Sépare les moniteurs par environnement (preprod vs prod)"""
        preprod_monitors = []
        prod_monitors = []

        for monitor in monitors:
            env = self._detect_environment(monitor)
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
            elif overall_state == "OK":
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

    def _extract_service_from_monitor(self, monitor: Dict[str, Any]) -> str:
        """Extrait le service/catégorie d'un monitor de manière intelligente"""
        tags = monitor.get("tags", [])
        name = monitor.get("name", "").lower()
        query = monitor.get("query", "").lower()

        # 1. Chercher le tag service:
        for tag in tags:
            if tag.startswith("service:"):
                return tag.split(":", 1)[1].upper()

        # 2. Détecter depuis la query ou le nom
        if "redis" in query or "redis" in name:
            if "pubsub" in query or "pubsub" in name:
                return "REDIS_PUBSUB"
            return "REDIS"
        elif "postgres" in query or "postgres" in name or "postgresql" in query or "database" in name:
            return "POSTGRES"
        elif "rabbitmq" in query or "rabbitmq" in name:
            return "RABBITMQ"
        elif "kubernetes" in name or "pod" in name or "deployment" in name or "k8s" in query:
            return "KUBERNETES"
        elif any(keyword in name for keyword in ["disk", "memory", "cpu", "load", "network", "filesystem"]):
            return "SYSTEM"
        else:
            return "OTHER"

    def group_alerts_by_service(self, alerts: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Regroupe les alertes par service/catégorie"""
        grouped = defaultdict(list)

        for alert in alerts:
            category = self._extract_service_from_monitor(alert)
            grouped[category].append(alert)

        return dict(grouped)

    def _get_monitor_groups_with_values(self, monitor: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extrait tous les groupes en alerte d'un monitor avec leurs valeurs
        Retourne: [{"name": "pod:xxx", "status": "Alert", "value": 95.5, "threshold": 90}, ...]
        """
        groups_info = []

        try:
            state = monitor.get("state", {})
            if not isinstance(state, dict):
                return []

            groups = state.get("groups", {})
            if not isinstance(groups, dict) or not groups:
                return []

            # Récupérer les thresholds depuis options
            options = monitor.get("options", {})
            thresholds = options.get("thresholds", {})
            critical_threshold = thresholds.get("critical")
            warning_threshold = thresholds.get("warning")

            for group_name, group_data in groups.items():
                if not isinstance(group_data, dict):
                    continue

                group_status = group_data.get("status")

                # Ne garder que les groupes en alerte/warn/no data
                if group_status not in ["Alert", "Warn", "No Data"]:
                    continue

                # Extraire la valeur
                value = None
                last_nodata_ts = group_data.get("last_nodata_ts")

                if last_nodata_ts:
                    # No Data state
                    value = "No Data"
                elif "last_triggered_ts" in group_data:
                    # Essayer d'extraire la valeur
                    if "last_value" in group_data:
                        try:
                            value = round(float(group_data["last_value"]), 2)
                        except (ValueError, TypeError):
                            value = group_data.get("last_value")

                # Déterminer le threshold applicable
                threshold = None
                if group_status == "Alert" and critical_threshold is not None:
                    threshold = critical_threshold
                elif group_status == "Warn" and warning_threshold is not None:
                    threshold = warning_threshold

                groups_info.append({
                    "name": group_name,
                    "status": group_status,
                    "value": value,
                    "threshold": threshold
                })

            return groups_info
        except (ValueError, TypeError, KeyError) as e:
            print(f"Warning: Error extracting groups: {e}", file=sys.stderr)
            return []

    def _parse_template_variables(self, text: str, state: str, monitor: Dict[str, Any]) -> str:
        """
        Parse et remplace les templates Datadog dans le texte
        Gère: {{#is_alert}}, {{value}}, {{threshold}}, {{variable.name}}, etc.
        """
        if not text:
            return ""

        # 1. Gérer les conditions is_alert/is_warning/is_recovery
        if "{{#is_alert}}" in text:
            if state in ["Alert", "No Data"]:
                match = re.search(r'\{\{#is_alert\}\}(.*?)\{\{/is_alert\}\}', text, re.DOTALL)
                if match:
                    text = match.group(1)
            elif state == "Warn":
                match_warn = re.search(r'\{\{#is_warning\}\}(.*?)\{\{/is_warning\}\}', text, re.DOTALL)
                if match_warn:
                    text = match_warn.group(1)
                else:
                    match = re.search(r'\{\{#is_alert\}\}(.*?)\{\{/is_alert\}\}', text, re.DOTALL)
                    if match:
                        text = match.group(1)
            else:
                match = re.search(r'\{\{#is_recovery\}\}(.*?)\{\{/is_recovery\}\}', text, re.DOTALL)
                if match:
                    text = match.group(1)

        # 2. Obtenir les groupes et leurs valeurs
        groups = self._get_monitor_groups_with_values(monitor)

        # 3. Remplacer {{value}} et {{threshold}}
        # Si un seul groupe, on peut remplacer directement
        if len(groups) == 1:
            group = groups[0]

            # Remplacer {{value}}
            if "{{value}}" in text and group["value"] is not None:
                text = text.replace("{{value}}", str(group["value"]))

            # Remplacer {{threshold}}
            if "{{threshold}}" in text and group["threshold"] is not None:
                text = text.replace("{{threshold}}", str(group["threshold"]))

        # 4. Supprimer les templates restants
        # Supprimer {{value}} et {{threshold}} non remplacés
        text = re.sub(r'\{\{value\}\}', '', text)
        text = re.sub(r'\{\{threshold\}\}', '', text)

        # Supprimer {{variable.name}} (ex: {{pod_name.name}}, {{host.name}})
        text = re.sub(r'\{\{[^}]+\.name\}\}', '', text)

        # Supprimer tous les autres templates {{xxx}}
        text = re.sub(r'\{\{[^}]+\}\}', '', text)

        # 5. Nettoyer le formatting
        # Nettoyer les tirets et espaces mal formés
        text = re.sub(r'\s*-\s*-\s*', ' - ', text)  # Double tirets
        text = re.sub(r'\s+-\s+', ' - ', text)      # Normaliser tirets
        text = re.sub(r'\s+', ' ', text)             # Espaces multiples
        text = re.sub(r'\s*-\s*$', '', text)         # Tiret à la fin
        text = re.sub(r'^\s*-\s*', '', text)         # Tiret au début

        return text.strip()

    def _format_group_name(self, group_name: str) -> str:
        """Formate un nom de groupe pour l'affichage (ex: 'pod:api-server' -> 'Pod: api-server')"""
        # Si le groupe contient ':', c'est un tag
        if ':' in group_name:
            parts = group_name.split(':', 1)
            key = parts[0].replace('_', ' ').title()
            value = parts[1]
            return f"{key}: {value}"
        else:
            # Sinon, juste formatter
            return group_name.replace('_', ' ').title()

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

        # Statistiques globales
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

        # Si aucune alerte
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

            # Trier les catégories
            sorted_categories = sorted(
                grouped_alerts.items(),
                key=lambda x: (category_priority.get(x[0], 50), x[0])
            )

            # Section pour chaque catégorie
            for category, alerts in sorted_categories:
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"🔴 *{category}*"
                    }
                })

                # Collecter toutes les alertes de cette catégorie
                alert_lines = []
                for monitor in alerts:
                    alert_lines.extend(self._format_alert_block(monitor))

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

    def _format_alert_block(self, monitor: Dict[str, Any]) -> List[str]:
        """
        Formate un bloc d'alerte avec son titre et ses groupes
        Retourne une liste de lignes à afficher
        """
        lines = []

        name = monitor.get("name", "Unknown")
        state = monitor.get("overall_state", "Unknown")
        monitor_id = monitor.get("id", "")

        # Parser et nettoyer le nom
        clean_name = self._parse_template_variables(name, state, monitor)

        # Emoji selon le statut
        if state == "Alert":
            status_emoji = "🔴"
        elif state == "Warn":
            status_emoji = "🟡"
        elif state == "No Data":
            status_emoji = "⚪"
        else:
            status_emoji = "⚫"

        # Créer le lien hyperlien cliquable vers Datadog
        if monitor_id:
            monitor_url = f"https://app.{self.dd_site}/monitors/{monitor_id}"
            main_line = f"• {status_emoji} <{monitor_url}|{clean_name}>"
        else:
            main_line = f"• {status_emoji} {clean_name}"

        lines.append(main_line)

        # Obtenir les groupes avec leurs valeurs
        groups = self._get_monitor_groups_with_values(monitor)

        # Afficher les groupes (toujours, même si 1 seul groupe)
        for group in groups:
            group_name = self._format_group_name(group["name"])
            group_value = group["value"]
            group_threshold = group["threshold"]

            # Formatter l'affichage du groupe
            if group_value == "No Data":
                group_line = f"  ↳ {group_name}: No Data"
            elif group_value is not None and group_threshold is not None:
                group_line = f"  ↳ {group_name}: {group_value} (threshold: {group_threshold})"
            elif group_value is not None:
                group_line = f"  ↳ {group_name}: {group_value}"
            else:
                group_line = f"  ↳ {group_name}"

            lines.append(group_line)

        return lines

    def send_to_slack(self, message: Dict[str, Any], environment: str = "prod") -> bool:
        """Envoie le message sur Slack pour l'environnement donné"""
        webhook_url = self.slack_webhook_prod if environment == "prod" else self.slack_webhook_preprod

        try:
            response = requests.post(
                webhook_url,
                json=message,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            print(f"✅ Message sent to Slack ({environment}) successfully")
            return True
        except requests.exceptions.RequestException as e:
            print(f"❌ Error sending message to Slack ({environment}): {e}", file=sys.stderr)
            return False

    def run(self):
        """Execute le processus complet pour preprod et prod"""
        print("=" * 60)
        print("Starting Datadog Alert Summary v2")
        print("=" * 60)

        # Récupérer tous les moniteurs
        print("\n📡 Fetching all monitors from Datadog...")
        all_monitors = self.get_all_monitors()
        print(f"   Found {len(all_monitors)} monitors (PREPROD + PROD)")

        # Séparer par environnement
        monitors_by_env = self.separate_monitors_by_environment(all_monitors)
        preprod_monitors = monitors_by_env["preprod"]
        prod_monitors = monitors_by_env["prod"]
        print(f"   Split: {len(preprod_monitors)} preprod, {len(prod_monitors)} prod")

        # Traiter chaque environnement
        success_preprod = self._process_environment("preprod", preprod_monitors)
        success_prod = self._process_environment("prod", prod_monitors)

        print("\n" + "=" * 60)
        if success_preprod or success_prod:
            print("✅ Alert summaries sent successfully!")
            return 0
        else:
            print("❌ Failed to send alert summaries")
            return 1

    def _process_environment(self, environment: str, monitors: List[Dict[str, Any]]) -> bool:
        """Traite un environnement spécifique"""
        print(f"\n📊 Processing {environment.upper()} environment")
        print("-" * 60)

        if not monitors:
            print(f"   ⚠️  No monitors found for {environment}")
            return True

        # Calculer les statistiques
        statistics = self.calculate_statistics(monitors)
        print(f"   📈 Stats: {statistics['operational']} OK | {statistics['down']} Down | {statistics['paused']} Paused")

        # Récupérer les alertes actives
        active_alerts = self.get_active_alerts(monitors)
        print(f"   🚨 Active alerts: {len(active_alerts)}")

        # Grouper par service
        grouped_alerts = self.group_alerts_by_service(active_alerts)
        if grouped_alerts:
            for category, alerts in grouped_alerts.items():
                print(f"      • {category}: {len(alerts)} alerts")

        # Formatter et envoyer
        slack_message = self.format_slack_message(statistics, grouped_alerts, environment)

        print(f"   📤 Sending summary to Slack...")
        success = self.send_to_slack(slack_message, environment)

        return success


if __name__ == "__main__":
    try:
        summary = DatadogAlertSummary()
        sys.exit(summary.run())
    except Exception as e:
        print(f"💥 Fatal error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
