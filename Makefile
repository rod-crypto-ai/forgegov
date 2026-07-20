.PHONY: up down logs test migrate makemigrations lint

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

migrate:
	docker compose exec backend python manage.py migrate

makemigrations:
	docker compose exec backend python manage.py makemigrations

test:
	docker compose exec backend python manage.py test
	docker compose exec frontend npm test -- --runInBand

lint:
	docker compose exec backend ruff check .
	docker compose exec frontend npm run lint
