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
`ControlDisponibilidad` (sin fragmentar; usa el factor de replicación por
defecto del cluster — ver comentario en `sql-scripts/schema.sql` sobre por
qué existe esta tabla aparte).

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

### Paso 7 - Capturar evidencia (E2)

Con el clúster ya configurado, desde el **host**:

```bash
mkdir -p evidence
date --iso-8601=seconds | tee evidence/cluster-start.txt
make proy1-status > evidence/node-status.txt
make proy1-check > evidence/config-check.txt
docker compose --profile proy1 run --rm --no-deps app-crdb \
  psql -X -v ON_ERROR_STOP=1 -f sql-scripts/inspect.sql \
  > evidence/cluster-inspect.txt
```

`sql-scripts/inspect.sql` corre `SHOW REGIONS`, `SHOW CREATE TABLE` de las
4 tablas, el conteo de filas por región y `SHOW RANGES` de
`ControlDisponibilidad` (debe mostrar `voting_replicas` con 3 IDs, uno por
nodo). Esa evidencia es la que sustenta E2 y la precondición de E4.

### Paso 8 - Medición de latencias local y remota (E3)

Desde el **host**, ejecute el script de benchmarking para capturar el rendimiento (mediana p50 y percentil p99) de las operaciones locales y remotas (lecturas y escrituras) cumpliendo con el mínimo de 30 corridas y descarte de _cold start_ mediante las rondas de warm-up:

```bash
docker compose --profile proy1 run --rm --no-deps app-crdb \
  python3 scripts/measure_latency.py \
    --gateway crdb-1 \
    --runs 50 \
    --warmup 5 \
    --csv evidence/e3-latencias.csv \
  | tee evidence/e3-latencias.txt
```

Esto imprimirá el resumen de latencias en la terminal y guardará las muestras detalladas en `evidence/e3-latencias.csv` para adjuntarlas como evidencia en el reporte.

### Paso 9 - Falla de nodo (E4)

Necesitan **dos terminales** en el host. `ControlDisponibilidad` es la
tabla verificada con 3 réplicas votantes (Paso 7); es la única sobre la
que se debe correr este experimento (ver comentario en
`sql-scripts/schema.sql`).

**Terminal A - arranca la sonda de escritura:**

```bash
rm -f evidence/falla-nodo-stop.epoch
docker compose --profile proy1 run --rm --no-deps app-crdb \
  python3 scripts/falla_nodo.py \
    --duration 90 \
    --signal-file evidence/falla-nodo-stop.epoch \
    --csv evidence/falla-nodo.csv \
  | tee evidence/falla-nodo.txt
```

Espere ver 3-5 líneas `before-stop ok` (unos 2 segundos) y pase enseguida
a la Terminal B — no deje correr mucho baseline, o se queda sin ventana
para observar la recuperación.

**Terminal B - provoca la falla:**

```bash
docker stop --timeout 0 ti4601-crdb-1
date +%s.%N > evidence/falla-nodo-stop.epoch
date --iso-8601=ns | tee evidence/falla-nodo-stop.txt
sleep 15
docker start ti4601-crdb-1
```

Se detiene `crdb-1` porque, según `evidence/cluster-inspect.txt`, es el
`lease_holder` de `ControlDisponibilidad` — matarlo fuerza una elección
real de líder Raft. Rescate si algo falla:
`docker start ti4601-crdb-1 ti4601-crdb-2 ti4601-crdb-3`.

**Al terminar, guarde el estado final y calcule RTO/RPO:**

```bash
make proy1-status > evidence/falla-nodo-node-status.txt
docker compose --profile proy1 run --rm --no-deps app-crdb \
  psql -X -v ON_ERROR_STOP=1 -c \
  "SELECT id, version, actualizado_en FROM controldisponibilidad WHERE id=1;" \
  > evidence/falla-nodo-rpo.txt
```

- **RTO**: `scripts/falla_nodo.py` lo imprime al final (tiempo entre la
  señal y el primer `after-stop ok`). Los intentos con error entre medio
  no son escrituras confirmadas ni perdidas: son intentos que nunca
  llegaron a comprometerse (`intento fallido ≠ commit perdido`).
- **RPO**: revise `evidence/falla-nodo-rpo.txt` — `version` debe seguir
  subiendo respecto al valor previo a la falla, nunca retroceder.

### Paso 10 - Evaluación de la arquitectura alternativa (primario + réplica para E5)

Para obtener la comparativa cuantitativa frente a la arquitectura distribuida, esta sección cubre dos experimentos sobre la arquitectura primario + réplica: la medición de latencias (lecturas contra la réplica, escrituras contra el primario) y unas pruebas de concurrencia (lost update vs. `SERIALIZABLE`) sobre el primario.

#### 1. Levantar el primario y la réplica

```bash
docker compose up -d postgres postgres-replica
docker compose ps   # confirma "healthy" en ambos
```

`postgres` y `postgres-replica` son dos contenedores Postgres **independientes**: no hay streaming replication real entre ellos, así que hay que sembrar el esquema y los datos en **ambos**.

#### 2. Aplicar el esquema y cargar los datos de prueba en ambos nodos

```bash
for host in postgres postgres-replica; do
  docker compose exec -T "$host" psql -U ti4601 -d ti4601 -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
  docker compose exec -T "$host" psql -U ti4601 -d ti4601 < sql-scripts/schema_postgres.sql
  docker compose exec -T "$host" psql -U ti4601 -d ti4601 < sql-scripts/seed.sql
done
```

#### 3. Verificar los servicios

```bash
docker compose ps
```

Opcionalmente, confirma que ambos nodos terminaron con las mismas filas (mismos `id`):

```bash
docker compose exec -T postgres psql -U ti4601 -d ti4601 -c "SELECT id, region_cuenta FROM cuenta ORDER BY region_cuenta;"
docker compose exec -T postgres-replica psql -U ti4601 -d ti4601 -c "SELECT id, region_cuenta FROM cuenta ORDER BY region_cuenta;"
```

#### 4. Ejecutar el script de medición de latencias

```bash
docker compose --profile client run --rm --no-deps app python3 scripts/measure_latency_single_node.py \
  --primary-host postgres \
  --replica-host postgres-replica \
  --port 5432 \
  --user ti4601 \
  --password ti4601 \
  --dbname ti4601 \
  --runs 50 \
  --warmup 5 \
  --csv evidence/e3-latencias-primario-replica.csv \
| tee evidence/e3-latencias-primario-replica.txt
```

Esto mide el rendimiento (p50 y p99) de lecturas (siempre contra la réplica) y escrituras (siempre contra el primario), guardando las muestras detalladas en `evidence/e3-latencias-primario-replica.csv`. La salida trae 2 filas — una por operación (`read`/`write`) con su `node` (`replica`/`primario`) — porque en esta arquitectura el nodo que atiende cada operación nunca cambia, a diferencia del clúster de 3 regiones de CockroachDB.

#### 5. Ejecutar el laboratorio de concurrencia (lost update vs. SERIALIZABLE)

Este experimento mide qué pasa cuando varias transacciones escriben la misma cuenta al mismo tiempo en el **primario** (la réplica no participa: el fenómeno es de contención entre escrituras, no de enrutamiento lectura/escritura). Se corre dos veces, con distinto nivel de aislamiento, y cada corrida va a su propio archivo de evidencia:

```bash
# READ_COMMITTED: expone actualizaciones perdidas (lost update) sin errores visibles
docker compose --profile client run --rm --no-deps app python3 scripts/stress_single_node.py \
  --isolation READ_COMMITTED --workers 40 --retries 8 \
| tee evidence/e5-concurrencia-read-committed.txt

# SERIALIZABLE: aborta las carreras (SerializationFailure) y reintenta
docker compose --profile client run --rm --no-deps app python3 scripts/stress_single_node.py \
  --isolation SERIALIZABLE --workers 40 --retries 8 \
| tee evidence/e5-concurrencia-serializable.txt
```

Cada corrida lanza 40 hilos que leen el saldo de la misma cuenta, esperan un instante y escriben `saldo - 1`, reportando cuántos commits fueron exitosos, cuántos abortos por serialización hubo, y el saldo final observado contra el esperado (`1000 − Commits OK`). Bajo `READ_COMMITTED` es normal ver 0 errores pero un saldo final muy por encima de lo esperado (las escrituras se pisan entre sí en silencio); bajo `SERIALIZABLE` es normal ver varios `SerializationFailure` pero un saldo final que sí cuadra con lo esperado. El script pisa el saldo de la cuenta objetivo (lo fija en 1000 antes de cada ráfaga).

### Para repetir desde cero

```bash
make proy1-down-v   # borra los volúmenes; solo si quiere reiniciar limpio
make proy1-up
make proy1-status
```

Y vuelva a los Pasos 2-6.

## Integrantes

Desarrollado por Andres Alfaro, Andres Uriza y Gabriel Guzman
