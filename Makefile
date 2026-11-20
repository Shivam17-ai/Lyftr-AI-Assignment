.PHONY: up down logs test restart clean help

help:
	@echo "Available commands:"
	@echo "  make up       - Start services in background (backend :8000, frontend :3000)"
	@echo "  make down     - Stop services"
	@echo "  make logs     - Follow container logs"
	@echo "  make test     - Run backend pytest suite"
	@echo "  make restart  - Restart containers"
	@echo "  make clean    - Stop services and remove SQLite data volumes"

up:
	@if [ ! -f .env ]; then \
		echo "Warning: .env not found. Copying from .env.example..."; \
		cp .env.example .env; \
		echo "PLEASE EDIT .env AND ADD YOUR REAL GROQ API KEYS!"; \
	fi
	docker compose up --build -d
	@echo "Services started successfully:"
	@echo "  Frontend: http://localhost:3000"
	@echo "  Backend:  http://localhost:8000"
	@echo "  Health:   http://localhost:8000/health"

down:
	docker compose down

logs:
	docker compose logs -f

test:
	@if [ -d backend/.venv ]; then \
		backend/.venv/bin/pytest backend/tests -v || backend/.venv/Scripts/pytest.exe -c backend/pytest.ini backend/tests -v -p no:asyncio; \
	else \
		docker compose run --rm backend pytest tests -v; \
	fi

restart:
	docker compose restart

clean:
	docker compose down -v
