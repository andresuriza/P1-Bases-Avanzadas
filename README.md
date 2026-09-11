# Proyecto 1 - Bases de Datos avanzadas

Prototipo de bases de datos distribuida DDBS que usa CockroachDB como motor en 3 regiones `cr-sj`, `cr-limon`, `us-east`.

## Como ejecutar

### Paso 0 - Requisitos

```bash
test -f .env || cp .env.example .env
docker compose version
make build
```

### Paso 1 - Levantar cluster

```bash
make proy1-up
make proy1-status
```

### Paso 2 - Entrar al cliente SQL

```bash
make proy1-shell
psql -X -v ON_ERROR_STOP=1
```

### Paso 3 - Convertir la base en multi-region

```bash
ALTER DATABASE ti4601 PRIMARY REGION "cr-sj";
ALTER DATABASE ti4601 ADD REGION "cr-limon";
ALTER DATABASE ti4601 ADD REGION "us-east";
SHOW REGIONS FROM DATABASE ti4601;
```

### Paso 4 - Aplicar y leer esquema del ejemplo

```bash
\i sql-scripts/schema.sql
```

## Integrantes

Desarrollado por Andres Alfaro, Andres Uriza y Gabriel Guzman
