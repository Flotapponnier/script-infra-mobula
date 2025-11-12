variable "namespace" {
  description = "Kubernetes namespace for the CronJob"
  type        = string
  default     = "default"
}

variable "docker_image" {
  description = "Docker image for the Better Stack monitor"
  type        = string
  default     = "ftapponn/betterstack-monitor:latest"
}

variable "slack_webhook_url_production" {
  description = "Slack webhook URL for production alerts"
  type        = string
  sensitive   = true
}

variable "slack_webhook_url_staging" {
  description = "Slack webhook URL for staging alerts"
  type        = string
  sensitive   = true
}

variable "betterstack_api_token" {
  description = "Better Stack API token"
  type        = string
  sensitive   = true
}
