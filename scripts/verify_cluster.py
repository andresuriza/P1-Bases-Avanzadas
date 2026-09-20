#!/usr/bin/env python3
"""Verifica la configuración del clúster del Proyecto 1 (banca regional).

No configura ni corrige nada: solo lee y reporta [OK]/[FAIL]. Si algo falla,
corrija con los pasos del README y vuelva a correr este script.
"""

from __future__ import annotations

import sys
from collections.abc import Callable

import psycopg


EXPECTED_REGIONS = {"cr-sj", "cr-limon", "us-east"}
REGIONAL_TABLES = ("cliente", "cuenta", "movimiento")


# FUNCIONES DE INSPECCIÓN DE INFRAESTRUCTURA Y CLÚSTER
def live_regions(conn: psycopg.Connection) -> set[str]:
    """
    Consulta los nodos activos y devuelve sus respectivas regiones.
    """
    rows = conn.execute(
        "SELECT locality FROM crdb_internal.gossip_nodes WHERE is_live"
    ).fetchall()
    return {
        item.removeprefix("region=")
        for row in rows
        for item in str(row[0]).split(",")
        if item.startswith("region=")
    }


def configured_regions(conn: psycopg.Connection) -> set[str]:
    """
    Consulta y devuelve las regiones geográficas que ya fueron registradas formalmente.
    """
    rows = conn.execute("SHOW REGIONS FROM DATABASE ti4601").fetchall()
    return {str(row[1]) for row in rows}


def tablas_regional_by_row(conn: psycopg.Connection) -> bool:
    """
    Verifica en el esquema de las tablas exista el atributo REGIONAL BY ROW.
    """
    for tabla in REGIONAL_TABLES:
        ddl = str(conn.execute(f"SHOW CREATE TABLE {tabla}").fetchone()[1]).upper()
        if "REGIONAL BY ROW" not in ddl:
            return False
    return True


# FUNCIONES DE VERFICACIÓN DE DATOS Y ALTA DISPONIBILIDAD
def cliente_cubre_las_tres_regiones(conn: psycopg.Connection) -> bool:
    """
    Verifica que las tablas en cada región geográfica se encuentren pobladas.
    """
    rows = conn.execute("SELECT DISTINCT region_cliente FROM cliente").fetchall()
    return EXPECTED_REGIONS <= {str(row[0]) for row in rows}


def movimiento_cruza_region(conn: psycopg.Connection) -> bool:
    """
    Valida que exista al menos una transacción entre cuentas de distintas regiones.
    """
    # Al menos un movimiento donde la cuenta_destino vive en una región
    # distinta a region_movimiento (ver convención en schema.sql: la región
    # del movimiento es la de la cuenta_origen).
    row = conn.execute(
        """
        SELECT count(*)
        FROM movimiento m
        JOIN cuenta destino ON destino.id = m.cuenta_destino
        WHERE destino.region_cuenta <> m.region_movimiento
        """
    ).fetchone()
    return row is not None and row[0] > 0


def control_disponibilidad_tiene_tres_votantes(conn: psycopg.Connection) -> bool:
    """
    Verifica que los rangos de la tabla control de disponibilidad posean tres réplicas votantes.
    """
    rows = conn.execute(
        """
        SELECT voting_replicas
        FROM [SHOW RANGES FROM TABLE controldisponibilidad WITH DETAILS]
        """
    ).fetchall()
    return bool(rows) and all(len(row[0]) == 3 for row in rows)


def check(label: str, assertion: Callable[[], bool], hint: str) -> bool:
    """
    Ejecuta una aserción de verificación, manejando excepciones y mostrando el estado OK/FAIL con su pista.
    """
    try:
        passed = assertion()
    except (psycopg.Error, IndexError, TypeError) as exc:
        print(f"[FAIL] {label}: {str(exc).splitlines()[0]}")
        print(f"       Pista: {hint}")
        return False
    if passed:
        print(f"[ OK ] {label}")
        return True
    print(f"[FAIL] {label}")
    print(f"       Pista: {hint}")
    return False


def main() -> int:
    # Intentar conectarse a la base de datos
    try:
        conn = psycopg.connect(autocommit=True)
    except psycopg.Error as exc:
        print(f"[FAIL] conexión: {str(exc).splitlines()[0]}")
        print("       Pista: levante los tres nodos y compruebe `make proy1-status`.")
        return 1

    # Si se abrió una conexión
    with conn:
        # Realizar verificación del clúster y sus datos
        results = [
            check(
                "tres nodos/localities vivos",
                lambda: EXPECTED_REGIONS <= live_regions(conn),
                "revise localities y logs de crdb-1, crdb-2 y crdb-3",
            ),
            check(
                "tres regiones configuradas en ti4601",
                lambda: EXPECTED_REGIONS <= configured_regions(conn),
                "ejecute PRIMARY REGION y ADD REGION en el orden del README",
            ),
            check(
                "cliente/cuenta/movimiento son REGIONAL BY ROW",
                lambda: tablas_regional_by_row(conn),
                "aplique sql-scripts/schema.sql después de configurar las regiones",
            ),
            check(
                "hay clientes en las tres regiones",
                lambda: cliente_cubre_las_tres_regiones(conn),
                "aplique sql-scripts/seed.sql",
            ),
            check(
                "existe al menos un movimiento que cruza región",
                lambda: movimiento_cruza_region(conn),
                "revise el seed: debe existir un movimiento con cuenta_destino "
                "en otra región distinta a region_movimiento",
            ),
            check(
                "ControlDisponibilidad tiene tres votantes",
                lambda: control_disponibilidad_tiene_tres_votantes(conn),
                "aplique sql-scripts/schema.sql y sql-scripts/seed.sql, y espere "
                "unos segundos a que se repliquen las 3 réplicas antes del chaos",
            ),
        ]

    passed = sum(results)

    print(f"\nResultado: {passed}/{len(results)} verificaciones.")

    if passed != len(results):
        print("El verificador no modificó el clúster. Corrija el primer FAIL y repita.")
        return 1
    
    print("Configuración lista para mediciones (E3) y falla de nodo (E4).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
