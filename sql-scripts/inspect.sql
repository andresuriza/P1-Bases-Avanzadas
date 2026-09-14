-- Consultas de inspección para evidencia de E2 (locality/particionamiento).
-- Uso: psql -X -v ON_ERROR_STOP=1 -f sql-scripts/inspect.sql

SHOW REGIONS FROM DATABASE ti4601;

SHOW CREATE TABLE cliente;
SHOW CREATE TABLE cuenta;
SHOW CREATE TABLE movimiento;
SHOW CREATE TABLE controldisponibilidad;

SELECT region_cliente, count(*) FROM cliente GROUP BY region_cliente ORDER BY region_cliente;
SELECT region_cuenta, count(*) FROM cuenta GROUP BY region_cuenta ORDER BY region_cuenta;
SELECT region_movimiento, count(*) FROM movimiento GROUP BY region_movimiento ORDER BY region_movimiento;

SHOW RANGES FROM TABLE controldisponibilidad WITH DETAILS;
