# Better Stack Monitor Synchronization Scripts

Scripts pour synchroniser les configurations de "call setup" entre les monitors Better Stack de production (mobula.io) et leurs duplicatas (zobula.xyz).

## Scripts disponibles

### 1. `list_monitors.py` - Liste et rapport (lecture seule)
Script en lecture seule qui affiche tous les monitors mobula.io avec call setup activé et identifie lesquels ont besoin de synchronisation.

**Usage:**
```bash
python3 list_monitors.py
```

**Ce script affiche:**
- Tous les monitors mobula.io avec call setup activé
- Les monitors zobula.xyz correspondants
- Lesquels sont déjà synchronisés
- Lesquels ont besoin de synchronisation
- Les monitors mobula.io sans duplicata zobula.xyz

### 2. `sync_monitors.py` - Synchronisation interactive
Script interactif qui demande confirmation avant de synchroniser les monitors.

**Usage:**
```bash
python3 sync_monitors.py
```

**Ce script:**
- Affiche tous les monitors qui ont besoin de synchronisation
- Demande confirmation avant chaque action
- Met à jour les monitors zobula.xyz pour avoir le même paramètre `call` que mobula.io

### 3. `sync_monitors_auto.py` - Synchronisation automatique
Script automatique qui synchronise tous les monitors sans demander de confirmation. **Utiliser avec précaution!**

**Usage:**
```bash
python3 sync_monitors_auto.py
```

**Ce script:**
- Identifie automatiquement les monitors à synchroniser
- Applique les changements sans confirmation
- Affiche un rapport détaillé des changements effectués

## Configuration

La clé API Better Stack est configurée dans chaque script:
```python
API_TOKEN = "aeZ3tcXRJe5ZsMpkBRf5LCWR"
```

## Fonctionnement

Les scripts:
1. Récupèrent tous les monitors via l'API Better Stack
2. Filtrent les monitors `mobula.io` (production) et `zobula.xyz` (duplicata)
3. Identifient les monitors mobula.io avec `call: true`
4. Associent chaque monitor mobula.io à son duplicata zobula.xyz basé sur le chemin de l'URL
5. Synchronisent le paramètre `call` du monitor mobula.io vers le monitor zobula.xyz correspondant

## Exemple de sortie

```
================================================================================
Better Stack Monitor List Tool (Read-Only)
================================================================================

Fetching monitors from Better Stack API...
  Page 1: Fetched 100 monitors
  Page 2: Fetched 100 monitors
  Page 3: Fetched 100 monitors
  Page 4: Fetched 5 monitors

Total monitors fetched: 305

Mobula.io monitors (prod): 205
Zobula.xyz monitors (duplica): 95

================================================================================
Mobula.io monitors with CALL SETUP enabled: 22
================================================================================

================================================================================
MONITORS NEEDING SYNCHRONIZATION: 17
================================================================================

 1. Explorer - health-lastTrade 1 (2-5-30)
    Mobula:  https://explorer-api.mobula.io/health/last-trades?...
             call=True, ID=3473208
    Zobula:  https://explorer-api.zobula.xyz/health/last-trades?...
             call=False, ID=3473210

...

================================================================================
SUMMARY
================================================================================
Total mobula.io monitors with call setup: 22
  - Already synchronized: 0
  - Need synchronization: 17
  - No zobula duplicate: 5
```

## Prérequis

```bash
pip install requests
```

## Notes importantes

- Les scripts utilisent l'API Better Stack v2
- Le matching entre mobula.io et zobula.xyz se fait sur le chemin de l'URL (partie après le domaine)
- Seuls les monitors avec `call: true` sur mobula.io sont traités
- Les monitors zobula.xyz sont automatiquement mis à jour pour correspondre à mobula.io
