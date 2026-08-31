PROJECT ?= ticket2skill-agentic-26
REGION ?= us-central1
SERVICE ?= ticket2skill

.PHONY: run deploy url

run:
	GOOGLE_CLOUD_PROJECT=$(PROJECT) GOOGLE_CLOUD_LOCATION=global TICKET2SKILL_MODEL=gemini-3.5-flash .venv/bin/uvicorn app.main:app --reload --port 8080

deploy:
	@PROJECT=$(PROJECT) REGION=$(REGION) SERVICE=$(SERVICE) ./scripts/deploy.sh

url:
	@gcloud run services describe $(SERVICE) --project=$(PROJECT) --region=$(REGION) --format='value(status.url)'
