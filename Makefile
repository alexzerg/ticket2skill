PROJECT ?= ticket2skill-agentic-26
REGION ?= us-central1
SERVICE ?= ticket2skill

.PHONY: run deploy url

run:
	GOOGLE_CLOUD_PROJECT=$(PROJECT) GOOGLE_CLOUD_LOCATION=global TICKET2SKILL_MODEL=gemini-3.5-flash .venv/bin/uvicorn app.main:app --reload --port 8080

deploy:
	gcloud run deploy $(SERVICE) --source . --project=$(PROJECT) --region=$(REGION) --allow-unauthenticated --min=1 --max=1 --memory=1Gi --timeout=300 --set-env-vars=GOOGLE_CLOUD_PROJECT=$(PROJECT),GOOGLE_CLOUD_LOCATION=global,TICKET2SKILL_MODEL=gemini-3.5-flash,TICKET2SKILL_ARTIFACT_ROOT=/tmp/artifacts

url:
	@gcloud run services describe $(SERVICE) --project=$(PROJECT) --region=$(REGION) --format='value(status.url)'
