terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

provider "google" {
  project = var.project
  region  = var.region
}

variable "project" { type = string }
variable "region" {
  type    = string
  default = "us-west1"
}

# Events in, one subscription for the worker, a dead-letter topic for messages that keep failing.
resource "google_pubsub_topic" "events" {
  name = "events"
}

resource "google_pubsub_topic" "events_dead" {
  name = "events-dead"
}

resource "google_pubsub_subscription" "worker" {
  name                 = "events-worker"
  topic                = google_pubsub_topic.events.id
  ack_deadline_seconds = 20

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.events_dead.id
    max_delivery_attempts = 5
  }

  retry_policy {
    minimum_backoff = "5s"
    maximum_backoff = "300s"
  }
}

resource "google_redis_instance" "features" {
  name           = "personalization-features"
  tier           = "STANDARD_HA"
  memory_size_gb = 1
  region         = var.region
}

# Separate service accounts: the API can publish, the worker can subscribe. Neither can do both.
resource "google_service_account" "api" {
  account_id = "personalization-api"
}

resource "google_service_account" "worker" {
  account_id = "personalization-worker"
}

resource "google_pubsub_topic_iam_member" "api_publish" {
  topic  = google_pubsub_topic.events.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_service_account.api.email}"
}

resource "google_pubsub_subscription_iam_member" "worker_subscribe" {
  subscription = google_pubsub_subscription.worker.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${google_service_account.worker.email}"
}

resource "google_pubsub_topic_iam_member" "worker_dead_letter" {
  topic  = google_pubsub_topic.events_dead.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_service_account.worker.email}"
}

resource "google_cloud_run_v2_service" "api" {
  name     = "personalization-api"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"

  template {
    service_account = google_service_account.api.email
    scaling {
      min_instance_count = 1
      max_instance_count = 10
    }
    containers {
      image = "us-docker.pkg.dev/${var.project}/personalization/api:latest"
      env {
        name  = "REDIS_URL"
        value = "redis://${google_redis_instance.features.host}:6379/0"
      }
      env {
        name  = "GCP_PROJECT"
        value = var.project
      }
      startup_probe {
        http_get {
          path = "/readyz"
        }
      }
      liveness_probe {
        http_get {
          path = "/healthz"
        }
      }
    }
  }
}
