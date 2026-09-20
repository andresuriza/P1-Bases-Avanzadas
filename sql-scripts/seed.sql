-- Un cliente por región (para probar completitud/disyunción de la
-- fragmentación de Cliente) más un segundo cliente en cr-sj para poder
-- armar un movimiento local además del movimiento que cruza región.
INSERT INTO Cliente(id, nombre, documento, region_cliente)
VALUES
('11111111-1111-1111-1111-111111111111', 'Harry', 184295827, 'cr-sj'),
('22222222-2222-2222-2222-222222222222', 'Ana', 105820394, 'cr-sj'),
('33333333-3333-3333-3333-333333333333', 'Michael', 148295327, 'cr-limon'),
('44444444-4444-4444-4444-444444444444', 'Laura', 209384756, 'us-east')
ON CONFLICT (id) DO NOTHING;

-- Cada cuenta hereda la region_cliente de su dueño (convención documentada
-- en schema.sql: no se fuerza con CHECK/trigger).
INSERT INTO Cuenta(id, monto, tipo, cliente_id, region_cuenta)
VALUES
('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 100000, 'corriente', '11111111-1111-1111-1111-111111111111', 'cr-sj'),
('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 20000, 'corriente', '22222222-2222-2222-2222-222222222222', 'cr-sj'),
('cccccccc-cccc-cccc-cccc-cccccccccccc', 0, 'corriente', '33333333-3333-3333-3333-333333333333', 'cr-limon'),
('dddddddd-dddd-dddd-dddd-dddddddddddd', 50000, 'corriente', '44444444-4444-4444-4444-444444444444', 'us-east')
ON CONFLICT (id) DO NOTHING;

-- Movimiento local: cuenta_origen y cuenta_destino en cr-sj.
-- region_movimiento toma la región de la cuenta_origen (convención del schema).
INSERT INTO Movimiento(cuenta_origen, cuenta_destino, monto, fecha, region_movimiento)
SELECT 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 5000, '2026-03-06', 'cr-sj'
WHERE NOT EXISTS (
  SELECT 1 FROM Movimiento
  WHERE cuenta_origen = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
    AND cuenta_destino = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'
);

-- Movimiento que cruza región: cuenta_origen en cr-sj, cuenta_destino en
-- cr-limon. region_movimiento = región de la cuenta_origen (cr-sj); la
-- escritura sobre cuenta_destino es la que cruza región.
INSERT INTO Movimiento(cuenta_origen, cuenta_destino, monto, fecha, region_movimiento)
SELECT 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'cccccccc-cccc-cccc-cccc-cccccccccccc', 50000, '2026-03-06', 'cr-sj'
WHERE NOT EXISTS (
  SELECT 1 FROM Movimiento
  WHERE cuenta_origen = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
    AND cuenta_destino = 'cccccccc-cccc-cccc-cccc-cccccccccccc'
);

-- Fila única para la sonda de E4. No representa nada del negocio: solo
-- necesitamos algo que podamos golpear con UPDATE ... SET version = version + 1
-- antes y después de apagar un nodo, para medir RTO y comprobar que la
-- version no retrocede (RPO = 0).
INSERT INTO ControlDisponibilidad (id, version)
VALUES (1, 0)
ON CONFLICT (id) DO NOTHING;
