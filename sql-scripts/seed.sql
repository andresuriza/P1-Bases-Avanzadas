-- Un cliente por región (para probar completitud/disyunción de la
-- fragmentación de Cliente) más un segundo cliente en cr-sj para poder
-- armar un movimiento local además del movimiento que cruza región.
INSERT INTO Cliente(nombre, documento, region_cliente)
VALUES
('Harry', 184295827, 'cr-sj'),
('Ana', 105820394, 'cr-sj'),
('Michael', 148295327, 'cr-limon'),
('Laura', 209384756, 'us-east');

-- Cada cuenta hereda la region_cliente de su dueño (convención documentada
-- en schema.sql: no se fuerza con CHECK/trigger).
INSERT INTO Cuenta(monto, tipo, cliente_id, region_cuenta)
VALUES
(100000, 'corriente', (SELECT id FROM Cliente WHERE nombre = 'Harry'), 'cr-sj'),
(20000, 'corriente', (SELECT id FROM Cliente WHERE nombre = 'Ana'), 'cr-sj'),
(0, 'corriente', (SELECT id FROM Cliente WHERE nombre = 'Michael'), 'cr-limon'),
(50000, 'corriente', (SELECT id FROM Cliente WHERE nombre = 'Laura'), 'us-east');

-- Movimiento local: cuenta_origen y cuenta_destino en cr-sj.
-- region_movimiento toma la región de la cuenta_origen (convención del schema).
INSERT INTO Movimiento(cuenta_origen, cuenta_destino, monto, fecha, region_movimiento)
VALUES
(
  (SELECT id FROM Cuenta WHERE cliente_id = (SELECT id FROM Cliente WHERE nombre = 'Harry')),
  (SELECT id FROM Cuenta WHERE cliente_id = (SELECT id FROM Cliente WHERE nombre = 'Ana')),
  5000, '2026-03-06', 'cr-sj'
);

-- Movimiento que cruza región: cuenta_origen en cr-sj, cuenta_destino en
-- cr-limon. region_movimiento = región de la cuenta_origen (cr-sj); la
-- escritura sobre cuenta_destino es la que cruza región.
INSERT INTO Movimiento(cuenta_origen, cuenta_destino, monto, fecha, region_movimiento)
VALUES
(
  (SELECT id FROM Cuenta WHERE cliente_id = (SELECT id FROM Cliente WHERE nombre = 'Harry')),
  (SELECT id FROM Cuenta WHERE cliente_id = (SELECT id FROM Cliente WHERE nombre = 'Michael')),
  50000, '2026-03-06', 'cr-sj'
);

-- Fila única para la sonda de E4. No representa nada del negocio: solo
-- necesitamos algo que podamos golpear con UPDATE ... SET version = version + 1
-- antes y después de apagar un nodo, para medir RTO y comprobar que la
-- version no retrocede (RPO = 0).
INSERT INTO ControlDisponibilidad (id, version)
VALUES (1, 0)
ON CONFLICT (id) DO NOTHING;
