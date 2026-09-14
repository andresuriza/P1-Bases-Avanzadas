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

### Paso 4 - Aplicar el esquema

```bash
\i sql-scripts/schema.sql
```

Crea `Cliente`, `Cuenta`, `Movimiento` (las tres `REGIONAL BY ROW`) y
`ControlDisponibilidad` (sin locality regional, usa el factor de
replicación por defecto del cluster — ver comentario en
`sql-scripts/schema.sql` sobre por qué existe esta tabla aparte).

### Paso 5 - Cargar los datos

```bash
\i sql-scripts/seed.sql
```

Debe insertar 4 clientes (uno por región, con un segundo cliente en
`cr-sj`), 4 cuentas, 2 movimientos (uno local, uno que cruza región) y la
fila de `ControlDisponibilidad`.

Salga de `psql` y del contenedor:

```bash
\q
exit
```

### Paso 6 - Verificar la configuración

Desde el **host** (fuera del contenedor):

```bash
make proy1-check
```

Corre `scripts/verify_cluster.py`, que revisa de forma **solo lectura**:
nodos vivos, regiones configuradas, locality de las tablas, cobertura de
regiones en el seed, el movimiento que cruza región, y que
`ControlDisponibilidad` tenga sus 3 réplicas votantes (una por nodo). La
meta es `6/6`. Si algo sale `[FAIL]`, el mensaje trae una pista; corrija
con los pasos anteriores y repita — el verificador no modifica nada.

### Para repetir desde cero

```bash
make proy1-down-v   # borra los volúmenes; solo si quiere reiniciar limpio
make proy1-up
make proy1-status
```

Y vuelva a los Pasos 2-6.

## Integrantes

Desarrollado por Andres Alfaro, Andres Uriza y Gabriel Guzman
