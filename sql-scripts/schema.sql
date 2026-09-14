-- TODO Mantener informacion personal aparte PII
CREATE TABLE Cliente(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    nombre STRING NOT NULL,
    documento INTEGER NOT NULL,
    region_cliente STRING NOT NULL CHECK (region_cliente IN ('cr-sj', 'cr-limon', 'us-east')),
    PRIMARY KEY (region_cliente, id),
    UNIQUE (id),
    UNIQUE (documento)
) PARTITION BY LIST (region_cliente) (
    PARTITION p_cr_sj    VALUES IN ('cr-sj'),
    PARTITION p_cr_limon VALUES IN ('cr-limon'),
    PARTITION p_us_east  VALUES IN ('us-east')
);

ALTER PARTITION p_cr_sj    OF TABLE Cliente CONFIGURE ZONE USING constraints = '[+region=cr-sj]';
ALTER PARTITION p_cr_limon OF TABLE Cliente CONFIGURE ZONE USING constraints = '[+region=cr-limon]';
ALTER PARTITION p_us_east  OF TABLE Cliente CONFIGURE ZONE USING constraints = '[+region=us-east]';

CREATE TABLE Cuenta(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    monto DECIMAL NOT NULL DEFAULT 0,
    tipo STRING NOT NULL,
    cliente_id UUID NOT NULL REFERENCES Cliente(id),
    region_cuenta STRING NOT NULL CHECK (region_cuenta IN ('cr-sj', 'cr-limon', 'us-east')),
    PRIMARY KEY (tipo, id),
    UNIQUE (id)
) PARTITION BY LIST (tipo) (
    PARTITION p_planilla  VALUES IN ('planilla'),
    PARTITION p_inversion VALUES IN ('inversion'),
    PARTITION p_corriente VALUES IN ('corriente'),
    PARTITION p_otros     VALUES IN (DEFAULT)
);

CREATE TABLE Movimiento(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    cuenta_origen UUID NOT NULL REFERENCES Cuenta(id),
    cuenta_destino UUID NOT NULL REFERENCES Cuenta(id),
    monto DECIMAL NOT NULL,
    fecha TIMESTAMP NOT NULL DEFAULT now(),
    region_movimiento STRING NOT NULL CHECK (region_movimiento IN ('cr-sj', 'cr-limon', 'us-east')),
    PRIMARY KEY (fecha, id)
) PARTITION BY RANGE (fecha) (
    PARTITION p_2025 VALUES FROM (MINVALUE) TO ('2026-01-01'),
    PARTITION p_2026 VALUES FROM ('2026-01-01') TO (MAXVALUE)
);
