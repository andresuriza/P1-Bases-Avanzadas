#!/usr/bin/env python3
"""Mide p50/p99 de operaciones locales y remotas desde un gateway fijo."""

from __future__ import annotations

import argparse
import csv
import math
import os
import statistics
import time
from dataclasses import dataclass

import psycopg


ROWS = {
    # "cr-sj": "10000000-0000-0000-0000-000000000001",
    # "cr-limon": "10000000-0000-0000-0000-000000000002",
}


@dataclass(frozen=True)
class Case:
    operation: str
    locality: str
    region: str


# Casos de prueba
CASES = (
    Case("read", "local", "cr-sj"),
    Case("read", "remote", "cr-limon"),
    Case("write", "local", "cr-sj"),
    Case("write", "remote", "cr-limon"),
)


def connect(host: str) -> psycopg.Connection:
    """
    Abre una conexión con el nodo gateway especificado sin requerir SSL.
    """
    return psycopg.connect(
        host=host,
        port=26257,
        user="root",
        dbname="ti4601",
        sslmode="disable",
        connect_timeout=3,
        autocommit=True,
    )


def percentile_nearest_rank(values: list[float], percentile: float) -> float:
    """
    Calcula el percentil deseado utilizando el método de rango más cercano sobre una lista ordenada de latencias.
    """
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile * len(ordered)))
    return ordered[rank - 1]


# EJECUCIÓN DE OPERACIONES
def execute_case(conn: psycopg.Connection, case: Case) -> None:
    """
    Ejecuta el caso de prueba especificado sobre la tabla cuenta.
    """
    target_id = ROWS[case.region]

    # Operación de lectura
    if case.operation == "read":
        row = conn.execute(
            """
            SELECT monto, region_cuenta
            FROM cuenta
            WHERE region_cuenta = %s AND id = %s 
            """,
            (case.region, target_id),
        ).fetchone()
        if row is None:
            raise RuntimeError(f"No existe fila seed en cuenta para ID={target_id} en región {case.region}")
        
    # Operación de escritura
    else:
        conn.execute(
            """
            UPDATE cuenta
            SET monto = monto + 1.00
            WHERE region_cuenta = %s AND id = %s 
            """,
            (case.region, target_id),
        )

# MEDICIÓN DE TIEMPOS
def measure(
    conn: psycopg.Connection, case: Case, warmup: int, runs: int
) -> list[float]:
    """
    Ejecuta las rondas de warm-up y mide las latencias para cada caso.
    """
    # Rondas de calentamiento para evitar el cold start
    for _ in range(warmup):
        execute_case(conn, case)

    # Ejecutar y medir los casos de prueba
    samples: list[float] = []
    for _ in range(runs):
        started = time.perf_counter_ns()
        execute_case(conn, case)
        elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
        samples.append(elapsed_ms)
    return samples


def main() -> int:
    # Configuración y argumentos del script
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gateway", default="crdb-1")
    parser.add_argument("--runs", type=int, default=50)
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--csv", default="")

    # Validación de argumentos
    args = parser.parse_args()
    if args.runs < 30:
        parser.error("--runs debe ser >= 30 para el entregable")
    if args.warmup < 1:
        parser.error("--warmup debe ser >= 1")

    print(
        f"=== Proyecto 1 · gateway={args.gateway} · "
        f"warmup={args.warmup} · n={args.runs} ==="
    )

    summaries: list[dict[str, str | int | float]] = []
    raw: list[dict[str, str | int | float]] = []

    # Ejecutar y medir los casos de prueba en cada nodo
    with connect(args.gateway) as conn:
        gateway_region = conn.execute(
            "SELECT gateway_region()"
        ).fetchone()[0]
        print(f"Región del gateway: {gateway_region}")

        # Obtener un ID de cuenta válido para cada región
        for reg in ["cr-sj", "cr-limon"]:
            row_id = conn.execute(
                "SELECT id FROM cuenta WHERE region_cuenta = %s LIMIT 1",
                (reg,)
            ).fetchone()
            if not row_id:
                raise RuntimeError(f"No se encontró ninguna cuenta seed para la región '{reg}'. ¿Corrió el seed.sql?")
            ROWS[reg] = row_id[0]
        
        print(f"IDs de prueba detectados: {ROWS}")

        for case in CASES:
            # Ejecutar casos de prueba
            samples = measure(conn, case, args.warmup, args.runs)

            # Guardar mediciones
            for run, elapsed_ms in enumerate(samples, start=1):
                raw.append(
                    {
                        "operation": case.operation,
                        "locality": case.locality,
                        "home_region": case.region,
                        "run": run,
                        "latency_ms": f"{elapsed_ms:.3f}",
                    }
                )
            summaries.append(
                {
                    "operation": case.operation,
                    "locality": case.locality,
                    "home_region": case.region,
                    "n": len(samples),
                    "p50_ms": statistics.median(samples),
                    "p99_ms": percentile_nearest_rank(samples, 0.99),
                }
            )

    # Imprimir resultados en terminal
    print("\noperation locality home_region n p50_ms p99_ms")
    for row in summaries:
        print(
            f"{row['operation']:9} {row['locality']:8} "
            f"{row['home_region']:11} {row['n']:>2} "
            f"{row['p50_ms']:>7.3f} {row['p99_ms']:>7.3f}"
        )

    # Guardar resultados en un .csv
    if args.csv:
        os.makedirs(os.path.dirname(args.csv) or ".", exist_ok=True)
        with open(args.csv, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=raw[0].keys())
            writer.writeheader()
            writer.writerows(raw)
        print(f"\nMuestras crudas: {args.csv}")

    print(
        "\nNota: Docker corre las tres regiones en una sola máquina. "
        "Un ratio local/remoto cercano a 1 no invalida el experimento."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
