CREATE TABLE Cliente(
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre STRING NOT NULL,
    documento INTEGER NOT NULL UNIQUE,
    region_cliente crdb_internal_region NOT NULL
) LOCALITY REGIONAL BY ROW AS region_cliente;

-- Fragmentada por tipo (LIST). tipo deja de ser un dato libre: debe ser uno
-- de los valores declarados en las particiones (ajustar la lista según los
-- tipos reales de cuenta del proyecto).
CREATE TABLE Cuenta(
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    monto DECIMAL NOT NULL DEFAULT 0,
    tipo STRING NOT NULL,
    cliente_id UUID NOT NULL REFERENCES Cliente(id),
    region_cuenta crdb_internal_region NOT NULL
) LOCALITY REGIONAL BY ROW AS region_cuenta;

-- Fragmentada por fecha (RANGE). Ajustar los límites de las particiones al
-- horizonte de datos real del proyecto.
CREATE TABLE Movimiento(
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cuenta_origen UUID NOT NULL REFERENCES Cuenta(id),
    cuenta_destino UUID NOT NULL REFERENCES Cuenta(id),
    monto DECIMAL NOT NULL,
    fecha TIMESTAMP NOT NULL DEFAULT now(),
    region_movimiento crdb_internal_region NOT NULL
) LOCALITY REGIONAL BY ROW AS region_movimiento;
