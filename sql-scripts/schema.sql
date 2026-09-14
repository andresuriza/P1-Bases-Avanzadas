-- Fragmentación horizontal primaria por region_cliente (residencia de PII):
-- region_cliente = 'cr-sj' | region_cliente = 'cr-limon' | region_cliente = 'us-east'
-- Cada fila vive en la región de apertura del cliente (nombre/documento no
-- salen de esa región).
CREATE TABLE Cliente(
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre STRING NOT NULL,
    documento INTEGER NOT NULL UNIQUE,
    region_cliente crdb_internal_region NOT NULL
) LOCALITY REGIONAL BY ROW AS region_cliente;

-- Fragmentación horizontal derivada de Cliente por region_cuenta:
-- region_cuenta = 'cr-sj' | region_cuenta = 'cr-limon' | region_cuenta = 'us-east'
-- Convención del equipo: region_cuenta coincide con la region_cliente del
-- dueño (no se fuerza con CHECK/trigger; se respeta al insertar).
CREATE TABLE Cuenta(
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    monto DECIMAL NOT NULL DEFAULT 0,
    tipo STRING NOT NULL,
    cliente_id UUID NOT NULL REFERENCES Cliente(id),
    region_cuenta crdb_internal_region NOT NULL
) LOCALITY REGIONAL BY ROW AS region_cuenta;

-- Fragmentación horizontal derivada de Cuenta por region_movimiento:
-- region_movimiento = 'cr-sj' | region_movimiento = 'cr-limon' | region_movimiento = 'us-east'
-- Convención del equipo: region_movimiento toma la region_cuenta de la
-- cuenta_origen (el movimiento "vive" donde se origina). Un movimiento entre
-- cuentas de regiones distintas es, por lo tanto, una escritura que cruza
-- región para la cuenta_destino.
CREATE TABLE Movimiento(
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cuenta_origen UUID NOT NULL REFERENCES Cuenta(id),
    cuenta_destino UUID NOT NULL REFERENCES Cuenta(id),
    monto DECIMAL NOT NULL,
    fecha TIMESTAMP NOT NULL DEFAULT now(),
    region_movimiento crdb_internal_region NOT NULL
) LOCALITY REGIONAL BY ROW AS region_movimiento;

-- Esta tabla NO es parte del dominio bancario (no representa clientes,
-- cuentas ni movimientos). La agregamos aparte para el E4 (falla de nodo).
-- Motivo: Cliente/Cuenta/Movimiento son REGIONAL BY ROW, y en nuestro
-- cluster solo hay un nodo por región. Eso significa que no tenemos
-- garantía de que esas tablas queden con 3 réplicas votantes repartidas
-- una por nodo (el rango podría terminar subreplicado). Si matamos un
-- nodo y probamos ahí, podríamos estar midiendo "se perdió mi única
-- copia" en vez de "perdimos 1 de 3 y seguimos con mayoría", que es lo
-- que E4 realmente quiere demostrar.
-- Por eso ControlDisponibilidad se deja SIN locality regional: usa el
-- factor de replicación por defecto del cluster (3 nodos -> 3 réplicas
-- votantes, una en cada nodo). Antes de apagar un nodo verificamos con
-- SHOW RANGES que voting_replicas tiene exactamente {1,2,3}, y ahí sí
-- podemos afirmar que estamos probando quórum Raft real (2 de 3), no
-- otra cosa.
CREATE TABLE ControlDisponibilidad (
    id INT8 PRIMARY KEY,
    version INT8 NOT NULL DEFAULT 0,
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT now()
);
