.PHONY: up down logs test test-backend typecheck lint build verify migrate makemigrations live-web open-source-ai

up:
	docker compose up -d --build

down:
	docker compose down --remove-orphans

logs:
	docker compose logs -f

migrate:
	docker compose exec backend python manage.py migrate

makemigrations:
	docker compose exec backend python manage.py makemigrations

test-backend:
	docker compose exec backend python manage.py test core

typecheck:
	docker compose exec frontend npm run typecheck

lint:
	docker compose exec frontend npm run lint

test: test-backend typecheck lint

build:
	docker compose exec frontend npm run build

live-web:
	./scripts/enable_live_web.sh

open-source-ai:
	./scripts/enable_open_source_ai.sh

verify:
	./scripts/validate_release.sh
