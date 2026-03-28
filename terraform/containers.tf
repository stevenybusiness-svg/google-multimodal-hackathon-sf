resource "google_cloud_run_v2_service" "web-api-1-d71a11" {
  name                = "web-api-1-d71a11"
  location            = "us-central1"
  deletion_protection = false

  template {
    scaling {
      min_instance_count = 0
      max_instance_count = 1
    }

    containers {
      image = "us-docker.pkg.dev/cloudrun/container/hello"

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          memory = "512Mi"
          cpu    = "1"
        }
      }
    }
  }
}

resource "google_cloud_run_v2_service_iam_member" "web-api-1-d71a11-public" {
  project  = google_cloud_run_v2_service.web-api-1-d71a11.project
  location = google_cloud_run_v2_service.web-api-1-d71a11.location
  name     = google_cloud_run_v2_service.web-api-1-d71a11.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
resource "google_cloud_run_v2_service" "web-api-2-bdd1fc" {
  name                = "web-api-2-bdd1fc"
  location            = "us-central1"
  deletion_protection = false

  template {
    scaling {
      min_instance_count = 0
      max_instance_count = 1
    }

    containers {
      image = "us-docker.pkg.dev/cloudrun/container/hello"

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          memory = "512Mi"
          cpu    = "1"
        }
      }
    }
  }
}

resource "google_cloud_run_v2_service_iam_member" "web-api-2-bdd1fc-public" {
  project  = google_cloud_run_v2_service.web-api-2-bdd1fc.project
  location = google_cloud_run_v2_service.web-api-2-bdd1fc.location
  name     = google_cloud_run_v2_service.web-api-2-bdd1fc.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
