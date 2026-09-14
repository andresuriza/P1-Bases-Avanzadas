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
