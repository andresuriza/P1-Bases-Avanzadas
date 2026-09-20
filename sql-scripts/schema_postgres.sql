-- Esquema relacional compatible con PostgreSQL para la arquitectura alternativa (1 nodo)

CREATE TABLE IF NOT EXISTS Cliente (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre VARCHAR(100) NOT NULL,
    documento INTEGER NOT NULL UNIQUE,
    region_cliente VARCHAR(50) NOT NULL
);

CREATE TABLE IF NOT EXISTS Cuenta (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    monto DECIMAL NOT NULL DEFAULT 0,
    tipo VARCHAR(50) NOT NULL,
    cliente_id UUID NOT NULL REFERENCES Cliente(id),
    region_cuenta VARCHAR(50) NOT NULL
);

CREATE TABLE IF NOT EXISTS Movimiento (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cuenta_origen UUID NOT NULL REFERENCES Cuenta(id),
    cuenta_destino UUID NOT NULL REFERENCES Cuenta(id),
    monto DECIMAL NOT NULL,
    fecha TIMESTAMP NOT NULL DEFAULT now(),
    region_movimiento VARCHAR(50) NOT NULL
);

CREATE TABLE IF NOT EXISTS ControlDisponibilidad (
    id INT8 PRIMARY KEY,
    version INT8 NOT NULL DEFAULT 0,
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT now()
);
