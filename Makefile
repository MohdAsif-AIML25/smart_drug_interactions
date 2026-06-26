# ============================================
# Smart Drug Interaction Platform — Makefile
# ============================================

.PHONY: up down build restart logs ps clean backend frontend

## Start all services
up:
	docker compose up -d

## Build and start all services
build:
	docker compose up --build -d

## Stop all services
down:
	docker compose down

## Restart all services
restart:
	docker compose restart

## View logs (all services)
logs:
	docker compose logs -f

## View logs for a specific service: make log s=backend
log:
	docker compose logs -f $(s)

## Show running containers
ps:
	docker compose ps

## Rebuild and restart backend only
backend:
	docker compose up --build -d backend

## Rebuild and restart frontend only
frontend:
	docker compose up --build -d frontend

## Stop and remove volumes (full reset)
clean:
	docker compose down -v --remove-orphans
	docker system prune -f

## Open app in browser
open:
	start http://localhost:3002

## Check backend health
health:
	curl -s http://localhost:8000/api/v1/health | python -m json.tool
