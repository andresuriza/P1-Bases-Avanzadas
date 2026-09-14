INSERT INTO Cliente(nombre, documento, region_cliente)
VALUES
('Harry', 184295827, 'us-east'),
('Michael', 148295327, 'cr-sj');

INSERT INTO Cuenta(monto, tipo, cliente_id, region_cuenta)
VALUES
(100000, 'corriente', (SELECT id FROM Cliente WHERE nombre = 'Harry'), 'us-east'),
(0, 'corriente', (SELECT id FROM Cliente WHERE nombre = 'Michael'), 'us-east');

INSERT INTO Movimiento(cuenta_origen, cuenta_destino, monto, fecha, region_movimiento)
VALUES
((SELECT id FROM Cuenta WHERE cliente_id = (SELECT id FROM Cliente WHERE nombre = 'Harry')), (SELECT id FROM Cuenta WHERE cliente_id = (SELECT id FROM Cliente WHERE nombre = 'Michael')), 50000, '2026-03-06', 'us-east');
