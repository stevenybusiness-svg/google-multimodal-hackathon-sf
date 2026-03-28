#!/usr/bin/env bash
# Deploy meeting-agent to Google Cloud Run with all env vars from .env
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_DIR/.env"

if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: .env file not found at $ENV_FILE"
  exit 1
fi

# Create a YAML env-vars file (handles special chars in values)
TMP_ENV=$(mktemp /tmp/env-vars-XXXXXX.yaml)
trap "rm -f $TMP_ENV" EXIT

while IFS='=' read -r key value; do
  [[ -z "$key" || "$key" =~ ^# ]] && continue
  # YAML: quote the value to handle special chars
  echo "$key: '$value'" >> "$TMP_ENV"
done < "$ENV_FILE"

echo "Deploying meeting-agent to Cloud Run..."
cd "$PROJECT_DIR"

gcloud run deploy meeting-agent \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --env-vars-file "$TMP_ENV"

echo ""
echo "Deploy complete. URL:"
gcloud run services describe meeting-agent --region us-central1 --format='value(status.url)'
