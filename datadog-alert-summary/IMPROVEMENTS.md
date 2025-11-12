# Améliorations V2 du Script Datadog Alert Summary

## Résumé

La version 2 du script corrige plusieurs problèmes majeurs de parsing, d'extraction de données et de formatting.

## Problèmes Résolus

### 1. **Détection d'Environnement Améliorée**

**Avant (V1):**
- Ne regardait que le nom du monitor
- Ne détectait pas `env:staging` ou `env:production`
- Manquait les monitors sans PROD/PREPROD dans le nom

**Après (V2):**
- Priorité intelligente: **Tags > Query > Nom**
- Détecte `env:prod`, `env:production`, `env:preprod`, `env:staging`
- Plus fiable et moins d'erreurs de classification

```python
# Exemple
Monitor: "High Redis Memory"
Tags: ["env:prod", "service:redis"]
V1: None (pas détecté)
V2: "prod" (détecté via tags)
```

---

### 2. **Parsing des Templates Datadog**

**Avant (V1):**
- Supprimait simplement `{{value}}` et `{{threshold}}`
- Ne remplaçait jamais par les valeurs réelles
- Titres avec des espaces vides: "Memory usage:  % (threshold:  %)"

**Après (V2):**
- Remplace `{{value}}` par la vraie valeur (ex: 95.5)
- Remplace `{{threshold}}` par le seuil configuré (ex: 90)
- Gère les conditions `{{#is_alert}}`, `{{#is_warning}}`, `{{#is_recovery}}`
- Nettoie proprement les templates non remplaçables

```python
# Exemple
Nom: "{{#is_alert}}High memory: {{value}}% (threshold: {{threshold}}%){{/is_alert}}"
État: Alert
Valeur: 95.5
Threshold: 90

V1: "High memory: % (threshold: %)"
V2: "High memory: 95.5% (threshold: 90%)"
```

---

### 3. **Extraction des Groupes avec Valeurs**

**Avant (V1):**
- N'extrayait que les noms et valeurs basiques
- Pas d'information sur les thresholds
- Affichait les groupes seulement si > 1 groupe

**Après (V2):**
- Extrait: nom, status, valeur actuelle, threshold
- Gère le cas "No Data" spécifiquement
- **Affiche toujours les groupes** (même pour 1 seul groupe)
- Affiche clairement: `Pod: api-server: 0 (threshold: 1)`

```python
# Exemple - Monitor avec avg by host
V1: Affiche uniquement si plusieurs hosts en alerte
V2: Affiche toujours tous les hosts avec leurs valeurs:
  ↳ Host: server1: 95.5 (threshold: 90)
  ↳ Host: server2: 85.2 (threshold: 80)
```

---

### 4. **Formatting et Nettoyage**

**Avant (V1):**
- Tirets et espaces mal formés
- "Redis - - Memory" au lieu de "Redis - Memory"
- Templates laissant des espaces vides

**Après (V2):**
- Nettoie proprement les doubles tirets
- Supprime les espaces multiples
- Résultat final toujours propre et lisible

---

### 5. **Messages d'Erreur et Logging**

**Avant (V1):**
- Messages de log basiques
- Pas d'emojis pour la clarté

**Après (V2):**
- Messages avec emojis pour meilleure lisibilité
- Structure claire: `📡 Fetching...`, `✅ Success`, `❌ Error`
- Meilleur debugging avec affichage des statistiques par catégorie

---

## Comparaison Visuelle

### Exemple de Sortie Slack

**Monitor Datadog:**
```
Name: "{{#is_alert}}Pod {{pod_name.name}} has {{value}} replicas (threshold: {{threshold}}){{/is_alert}}"
Query: "avg by (pod) of kubernetes.pods.running{env:prod}"
State: Alert
Groups:
  - pod:api-server: value=0, threshold=1
  - pod:worker: value=0, threshold=1
```

**V1 Output:**
```
🔴 Pod has replicas (threshold: )
```
❌ Pas de noms de pods, pas de valeurs, titre cassé

**V2 Output:**
```
🔴 Pod has 0 replicas (threshold: 1)
  ↳ Pod: api-server: 0 (threshold: 1)
  ↳ Pod: worker: 0 (threshold: 1)
```
✅ Titre propre + détails complets de tous les pods en alerte

---

## Tests

Pour tester les différences entre V1 et V2:

```bash
python3 test_comparison.py
```

Ce script compare:
- Détection d'environnement
- Parsing des templates
- Extraction des groupes

---

## Migration

### Pour tester V2:

```bash
# Tester sans envoyer sur Slack (ajoutez un flag de dry-run si nécessaire)
python3 alert_summary_v2.py
```

### Pour déployer en production:

1. Tester d'abord sur preprod
2. Vérifier la sortie Slack
3. Si tout est OK, remplacer l'ancien script:

```bash
cp alert_summary.py alert_summary_v1_backup.py
cp alert_summary_v2.py alert_summary.py
```

---

## Améliorations Futures Possibles

1. **Cache des monitors**: Éviter de refetch si déjà en cache (< 1 min)
2. **Retry logic**: Retry automatique en cas d'échec Slack
3. **Filtres personnalisés**: Permettre de filtrer par service/tag
4. **Mode verbose**: Flag `--verbose` pour debugging
5. **Export JSON**: Sauvegarder les données brutes en JSON pour analytics

---

## Structure du Code

### Méthodes Principales V2

| Méthode | Description |
|---------|-------------|
| `_detect_environment()` | Détection intelligente de l'environnement (tags > query > nom) |
| `_get_monitor_groups_with_values()` | Extraction complète des groupes avec valeurs et thresholds |
| `_parse_template_variables()` | Parsing et remplacement des templates Datadog |
| `_format_group_name()` | Formatage propre des noms de groupes |
| `_format_alert_block()` | Formatage d'un bloc d'alerte complet |

---

## FAQ

**Q: Pourquoi V2 affiche toujours les groupes, même pour 1 seul groupe?**
A: Pour la cohérence et la clarté. Cela permet de toujours voir les valeurs exactes et les thresholds, même pour les monitors simples.

**Q: Que se passe-t-il si un monitor n'a pas de tags env:?**
A: V2 fallback sur la query, puis sur le nom du monitor (comme V1).

**Q: Les URLs Datadog fonctionnent toujours?**
A: Oui, les liens cliquables vers les monitors sont préservés.

---

## Contact

Pour toute question ou bug, ouvrir une issue ou contacter l'équipe infra.
