# Instituto Tecnológico de Costa Rica — TI-4601

.PHONY: help up down down-v build shell test-tx lab-concurrency \
	proy1-up proy1-down proy1-down-v proy1-shell proy1-status proy1-check reset-pg

COMPOSE := docker compose
ISOLATION ?= READ_COMMITTED
WORKERS ?= 40
RETRIES ?= 8

help:
	@echo "TI-4601 · entorno"
	@echo "  make up | down | down-v | build | shell | reset-pg"
	@echo "  make test-tx"
	@echo "  make lab-concurrency ISOLATION=READ_COMMITTED|SERIALIZABLE"
	@echo "  Proyecto 1: make proy1-up | proy1-status | proy1-shell | proy1-check"
	@echo "         make proy1-down | proy1-down-v"
	@echo ""
	@echo "Docs: README.md" 

up:
	$(COMPOSE) up -d postgres

down:
	$(COMPOSE) down --remove-orphans

down-v:
	$(COMPOSE) down -v --remove-orphans

build:
	$(COMPOSE) build app

shell: up
	$(COMPOSE) run --rm app bash

reset-pg: down-v up
	@echo "Volumen recreado; initdb volvió a cargar CSV."

test-tx: up
	$(COMPOSE) run --rm app python3 transactions/read.py
	$(COMPOSE) run --rm app python3 transactions/transform.py
	$(COMPOSE) run --rm app python3 transactions/aggregate.py
	$(COMPOSE) run --rm app python3 transactions/join.py
	$(COMPOSE) run --rm app python3 transactions/answer.py

proy1-up: build
	$(COMPOSE) --profile proy1 up -d crdb-1 crdb-2 crdb-3
	$(COMPOSE) --profile proy1 up crdb-init

proy1-down:
	$(COMPOSE) --profile proy1 down

proy1-down-v:
	$(COMPOSE) --profile proy1 down -v

proy1-shell:
	$(COMPOSE) --profile proy1 run --rm app-crdb bash

proy1-status:
	$(COMPOSE) --profile proy1 ps
	docker exec ti4601-crdb-1 cockroach node status --insecure

proy1-check:
	$(COMPOSE) --profile proy1 run --rm --no-deps app-crdb \
		python3 scripts/verify_cluster.py
