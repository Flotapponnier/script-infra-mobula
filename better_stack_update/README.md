# Better Stack Monitor Management Tool

Script bash interactif pour gérer les monitors Better Stack avec 2 modes d'opération.

## Fonctionnalités

### Option 1: Export
- Récupère tous les monitors via l'API Better Stack
- Exporte la configuration complète dans `monitors_config.json`
- Affiche un résumé par type et par domaine

### Option 2: Update Monitors
**Phase 1: Dry-Run**
- Compare le `monitors_config.json` avec l'état actuel
- Affiche tous les changements détectés (CREATE/UPDATE)
- Aucune modification à ce stade

**Phase 2: Confirmation Interactive**
- Demande si vous voulez appliquer les changements
- Option 1: Appliquer maintenant
- Option 2: Retour au menu

**Phase 3: Application (si confirmé)**
- Met à jour les monitors existants avec les nouveaux paramètres
- Crée de nouveaux monitors si absents de Better Stack
- Affiche un résumé des succès/échecs

## Installation

### Prérequis
```bash
# macOS
brew install jq curl

# Linux
apt-get install jq curl
```

### Configuration de l'API Token

Le script a besoin d'un token Better Stack API. Deux méthodes sont supportées :

**Méthode 1 : Fichier .env (Recommandé)**
```bash
cd better_stack_update

# Copier l'exemple et éditer avec votre token
cp .env.example .env
nano .env

# Ou directement :
echo 'BETTERSTACK_API_TOKEN=your-token-here' > .env
```

**Méthode 2 : Variable d'environnement**
```bash
export BETTERSTACK_API_TOKEN='your-token-here'
./manage_monitors.sh
```

Le fichier `.env` est automatiquement ignoré par git pour la sécurité.

## Usage

```bash
cd better_stack_update
./manage_monitors.sh
```

Le script affiche un menu interactif :
```
========================================
Better Stack Monitor Management
========================================

1) Export all monitors to config.json
2) Update monitors from config.json
3) Exit

Select an option (1-3):
```

## Workflow Recommandé

1. **Export initial** : Lancez l'option 1 pour créer `monitors_config.json`
2. **Modification** : Éditez `monitors_config.json` selon vos besoins
3. **Update** : Lancez l'option 2 qui va :
   - Afficher les changements détectés (dry-run)
   - Demander confirmation avant d'appliquer
   - Appliquer les changements si vous confirmez

## Format du Config

Le fichier `monitors_config.json` contient tous les paramètres des monitors :
```json
{
  "monitors": [
    {
      "id": "1234567",
      "url": "https://api.mobula.io/api/1/health",
      "name": "health",
      "monitor_type": "status",
      "check_frequency": 30,
      "call": false,
      "sms": true,
      "email": false,
      "push": false,
      "verify_ssl": true,
      "regions": ["us", "eu", "as", "au"],
      "request_headers": [
        {
          "id": "123",
          "name": "Authorization",
          "value": "..."
        }
      ],
      ...
    }
  ]
}
```

## Paramètres Exportés

Le script exporte tous les paramètres importants :
- `url`, `name`, `monitor_type`
- `check_frequency`, `request_timeout`, `recovery_period`
- `call`, `sms`, `email`, `push`, `critical_alert`
- `verify_ssl`, `follow_redirects`, `remember_cookies`
- `regions`, `request_headers`, `request_body`
- Et plus encore...

## Statut de Développement

- ✅ Option 1: Export - **Complété**
- ✅ Option 2: Update avec dry-run et confirmation - **Complété**

## Exemples d'Utilisation

### Modifier un paramètre pour tous les monitors mobula.io

```bash
# Activer les appels téléphoniques pour tous les monitors mobula.io
jq '.monitors |= map(if .url | contains("mobula.io") then .call = true else . end)' \
    monitors_config.json > temp.json && mv temp.json monitors_config.json

# Lancer l'option 2 pour voir les changements et les appliquer
./manage_monitors.sh
```

### Ajouter un nouveau monitor

```bash
# Éditer le fichier et ajouter un nouveau monitor dans le tableau
# (sans ID ou avec ID null)
nano monitors_config.json

# Lancer l'option 2 - le script détectera le nouveau monitor
./manage_monitors.sh
```

## Sécurité

- Le token API est stocké dans le fichier `.env` (non versionné)
- Fichier `.env.example` fourni comme template
- Le `.gitignore` empêche de commiter accidentellement le token

## Notes

- Le script utilise l'API Better Stack v2
- Tous les monitors sont récupérés (pagination automatique)
- Le fichier de sortie est formaté avec jq pour lisibilité
