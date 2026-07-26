.PHONY: up down logs test test-backend lint build verify migrate makemigrations

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

test: test-backend
	docker compose run --rm frontend npm run lint

lint:
	docker compose exec backend ruff check .

build:
	docker build --target runner -t forgegov-frontend-production ./frontend

verify:
	./VERIFY.command
