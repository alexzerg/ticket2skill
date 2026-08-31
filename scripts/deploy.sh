#!/usr/bin/env bash
set -euo pipefail

PROJECT=${PROJECT:-ticket2skill-agentic-26}
REGION=${REGION:-us-central1}
SERVICE=${SERVICE:-ticket2skill}
VERSION=$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")
IMAGE="$REGION-docker.pkg.dev/$PROJECT/ticket2skill/app:$VERSION"

gcloud builds submit --project="$PROJECT" --tag="$IMAGE" --timeout=900s --quiet .
gcloud run deploy "$SERVICE" \
  --image="$IMAGE" \
  --project="$PROJECT" \
  --region="$REGION" \
  --platform=managed \
  --allow-unauthenticated \
  --min=1 --max=1 --memory=1Gi --timeout=300 \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=$PROJECT,GOOGLE_CLOUD_LOCATION=global,TICKET2SKILL_MODEL=gemini-3.5-flash,TICKET2SKILL_ARTIFACT_ROOT=/tmp/artifacts" \
  --quiet

gcloud run services describe "$SERVICE" --project="$PROJECT" --region="$REGION" --format='value(status.url)'
