# Proje kokunden: make help | make smoke

.PHONY: help up down ps smoke monitoring-build

help:
	@echo "Targets:"
	@echo "  make up     - docker compose up -d"
	@echo "  make down   - docker compose down"
	@echo "  make ps     - docker compose ps"
	@echo "  make smoke  - scripts/smoke-test.sh (API_URL=http://127.0.0.1:8000 varsayilan)"
	@echo "  make monitoring-build - docker compose build monitoring"

up:
	docker compose up -d

down:
	docker compose down

ps:
	docker compose ps

smoke:
	bash scripts/smoke-test.sh

monitoring-build:
	docker compose build monitoring
