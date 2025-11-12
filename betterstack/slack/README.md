# Better Stack Slack Monitor

Surveillance automatique des endpoints Better Stack avec notifications Slack.

## Fichiers

- `monitor-uptimes-endpoint.js` - Script Node.js de monitoring
- `Dockerfile` - Image Docker multi-architecture (AMD64/ARM64)
- `cronjob.tf` - Configuration Terraform pour CronJob Kubernetes
- `variables.tf` - Variables Terraform
- `.env.example` - Exemple de fichier de configuration

## Configuration locale

1. Copier `.env.example` vers `.env`
2. Remplir les variables d'environnement
3. Installer les dépendances : `npm install`
4. Lancer le script : `node monitor-uptimes-endpoint.js`

## Build et Push de l'image Docker (multi-architecture)

```bash
# Build pour AMD64 et ARM64
docker buildx build --platform linux/amd64,linux/arm64 \
  -t your-registry/betterstack-monitor:latest \
  --push .

# Ou build local pour test
docker build -t betterstack-monitor:latest .
```

## Déploiement Kubernetes avec Terraform

1. Créer un fichier `terraform.tfvars` :

```hcl
namespace                    = "monitoring"
docker_image                 = "your-registry/betterstack-monitor:latest"
slack_webhook_url_production = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
slack_webhook_url_staging    = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
betterstack_api_token        = "your-betterstack-api-token"
```

2. Déployer :

```bash
terraform init
terraform plan
terraform apply
```

## Fonctionnalités

- Récupère tous les monitors Better Stack
- Catégorise par environnement (Production, Staging, Explorer Preprod)
- Envoie des rapports de statut sur Slack toutes les heures
- Notifications détaillées des services down
- Support multi-architecture (AMD64 et ARM64)

## CronJob Schedule

Par défaut, le CronJob s'exécute **toutes les heures** (`0 * * * *`).

Pour modifier la fréquence, éditer la ligne `schedule` dans `cronjob.tf`.
