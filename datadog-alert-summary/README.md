# Datadog Alert Summary

Python script that fetches active Datadog alerts and sends hourly summaries to Slack.

## Description

This script:
- Fetches all monitors from Datadog (preprod + prod environments)
- Separates alerts by environment
- Groups alerts by service category
- Sends formatted summaries to separate Slack channels (preprod & prod)

## Features

- **Environment Separation**: Automatically separates preprod and prod alerts
- **Service Grouping**: Groups alerts by Redis, PostgreSQL, RabbitMQ, Kubernetes, etc.
- **Clean Formatting**: Removes template variables like `{{value}}` when values are unavailable
- **Dual Webhooks**: Sends to both preprod and prod Slack channels

## Requirements

- Python 3.11+
- `requests` library

## Environment Variables

Required environment variables:

```bash
DATADOG_API_KEY          # Datadog API key
DATADOG_APP_KEY          # Datadog application key
DATADOG_SITE             # Datadog site (e.g., datadoghq.eu)
SLACK_WEBHOOK_PREPROD    # Slack webhook URL for preprod alerts
SLACK_WEBHOOK_PROD       # Slack webhook URL for prod alerts
```

## Usage

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DATADOG_API_KEY="your-api-key"
export DATADOG_APP_KEY="your-app-key"
export DATADOG_SITE="datadoghq.eu"
export SLACK_WEBHOOK_PREPROD="https://hooks.slack.com/..."
export SLACK_WEBHOOK_PROD="https://hooks.slack.com/..."

# Run the script
python3 alert_summary.py
```

### Docker

```bash
# Build the image
docker build -t ftapponn/datadog-alert-summary:latest .

# Run the container
docker run --rm \
  -e DATADOG_API_KEY="your-api-key" \
  -e DATADOG_APP_KEY="your-app-key" \
  -e DATADOG_SITE="datadoghq.eu" \
  -e SLACK_WEBHOOK_PREPROD="https://hooks.slack.com/..." \
  -e SLACK_WEBHOOK_PROD="https://hooks.slack.com/..." \
  ftapponn/datadog-alert-summary:latest
```

### Multi-platform Build

```bash
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t ftapponn/datadog-alert-summary:latest \
  --push .
```

## Deployment

This script is deployed as a Kubernetes CronJob in the `kube-infra-app` repository.

See: `kube-infra-app/infra-OVH/datadog/terraform/alert-summary-cronjob.tf`

## Output Example

```
✅ Infrastructure Health - 70.5% Operational
📊 System Overview - Critical Issues

Total Monitors: 61
Operational: ▸ 43
Down: 🔻 18
Uptime: 70.5%

🏢 PREPROD Environment
🔴 REDIS
• Redis pod restarting
• Redis pod memory high
• Redis PVC full

🔴 KUBERNETES
• Node Memory High
• Pod restarting frequently
```

## Recent Changes

- Removed `?%` placeholders when metric values are unavailable
- Cleaner alert titles by removing template variables without values
- Improved formatting for Slack messages
