resource "kubernetes_secret" "betterstack_slack_secrets" {
  metadata {
    name      = "betterstack-slack-secrets"
    namespace = var.namespace
  }

  data = {
    SLACK_WEBHOOK_URL_PRODUCTION = var.slack_webhook_url_production
    SLACK_WEBHOOK_URL_STAGING    = var.slack_webhook_url_staging
    BETTERSTACK_API_TOKEN        = var.betterstack_api_token
  }

  type = "Opaque"
}

resource "kubernetes_cron_job_v1" "betterstack_monitor" {
  metadata {
    name      = "betterstack-monitor"
    namespace = var.namespace
  }

  spec {
    schedule                      = "0 * * * *" # Every hour
    concurrency_policy            = "Forbid"
    successful_jobs_history_limit = 3
    failed_jobs_history_limit     = 3

    job_template {
      metadata {
        labels = {
          app = "betterstack-monitor"
        }
      }

      spec {
        template {
          metadata {
            labels = {
              app = "betterstack-monitor"
            }
          }

          spec {
            restart_policy = "OnFailure"

            container {
              name  = "monitor"
              image = var.docker_image

              env {
                name = "SLACK_WEBHOOK_URL_PRODUCTION"
                value_from {
                  secret_key_ref {
                    name = kubernetes_secret.betterstack_slack_secrets.metadata[0].name
                    key  = "SLACK_WEBHOOK_URL_PRODUCTION"
                  }
                }
              }

              env {
                name = "SLACK_WEBHOOK_URL_STAGING"
                value_from {
                  secret_key_ref {
                    name = kubernetes_secret.betterstack_slack_secrets.metadata[0].name
                    key  = "SLACK_WEBHOOK_URL_STAGING"
                  }
                }
              }

              env {
                name = "BETTERSTACK_API_TOKEN"
                value_from {
                  secret_key_ref {
                    name = kubernetes_secret.betterstack_slack_secrets.metadata[0].name
                    key  = "BETTERSTACK_API_TOKEN"
                  }
                }
              }

              resources {
                requests = {
                  cpu    = "100m"
                  memory = "128Mi"
                }
                limits = {
                  cpu    = "200m"
                  memory = "256Mi"
                }
              }
            }
          }
        }
      }
    }
  }
}
