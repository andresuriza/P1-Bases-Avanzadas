#!/usr/init/env python3
"""Mide p50/p99 de operaciones en la arquitectura alternativa PostgreSQL (Primario + Réplica)."""

from __future__ import annotations

import argparse
import csv
import itertools
import math
import os
import statistics
import time

import psycopg

# Operaciones estándar
OPERATIONS = ("read", "write")


def node_for(operation: str) -> str:
    """Devuelve el nodo físico que atiende la operación."""
    return "replica" if operation == "read" else "primario"


def connect(host: str, port: int, user: str, password: str, dbname: str) -> psycopg.Connection:
    """Abre una conexión con el nodo de PostgreSQL especificado."""
    return psycopg.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        dbname=dbname,
        sslmode="disable",
        connect_timeout=3,
        autocommit=True,
    )


def percentile_nearest_rank(values: list[float], percentile: float) -> float:
    """Calcula el percentil deseado utilizando el método de rango más cercano."""
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile * len(ordered)))
    return ordered[rank - 1]


# POLÍTICA DE ENRUTAMIENTO: Lecturas a la Réplica, Escrituras al Primario
def execute_operation(
    conn_primary: psycopg.Connection, conn_replica: psycopg.Connection, operation: str, target_id
) -> None:
    """Ejecuta la operación contra el nodo que le corresponde según la política fija."""
    if operation == "read":
        # Las consultas de lectura van exclusivamente al nodo réplica
        row = conn_replica.execute(
            "SELECT monto FROM cuenta WHERE id = %s",
            (target_id,),
        ).fetchone()
        if row is None:
            raise RuntimeError(f"No existe fila seed en cuenta para ID={target_id}")

    else:
        # Las operaciones de escritura van exclusivamente al nodo primario
        conn_primary.execute(
            "UPDATE cuenta SET monto = monto + 1.00 WHERE id = %s",
            (target_id,),
        )


def measure(
    conn_primary: psycopg.Connection,
    conn_replica: psycopg.Connection,
    operation: str,
    target_ids: list,
    warmup: int,
    runs: int,
) -> list[float]:
    """Ejecuta warm-up y mide latencias, alternando entre las cuentas sembradas
    solo para no golpear siempre la misma fila"""
    id_cycle = itertools.cycle(target_ids)

    # Realizar ejecuciones de calentamiento
    for _ in range(warmup):
        execute_operation(conn_primary, conn_replica, operation, next(id_cycle))

    samples: list[float] = []
    for _ in range(runs):
        target_id = next(id_cycle)

        # Ejecutar operación
        started = time.perf_counter_ns()
        execute_operation(conn_primary, conn_replica, operation, target_id)
        elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000

        # Guardar resultados
        samples.append(elapsed_ms)
    return samples


def main() -> int:
    # Confuguración de parametros y validación
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--primary-host", default="postgres-primary", help="Host del nodo primario")
    parser.add_argument("--replica-host", default="postgres-replica", help="Host de la réplica de lectura")
    parser.add_argument("--port", type=int, default=5432, help="Puerto de PostgreSQL")
    parser.add_argument("--user", default="ti4601", help="Usuario de PostgreSQL")
    parser.add_argument("--password", default="ti4601", help="Contraseña de PostgreSQL")
    parser.add_argument("--dbname", default="ti4601", help="Nombre de la base de datos")
    parser.add_argument("--runs", type=int, default=50)
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--csv", default="")

    args = parser.parse_args()
    if args.runs < 30:
        parser.error("--runs debe ser >= 30 para el entregable")
    if args.warmup < 1:
        parser.error("--warmup debe ser >= 1")

    print(
        f"=== Arquitectura Alternativa (Primario: {args.primary_host} | Réplica: {args.replica_host}) ==="
    )

    summaries: list[dict[str, str | int | float]] = []
    raw: list[dict[str, str | int | float]] = []

    # Abrir conexiones independientes a ambos nodos
    with connect(args.primary_host, args.port, args.user, args.password, args.dbname) as conn_primary, \
         connect(args.replica_host, args.port, args.user, args.password, args.dbname) as conn_replica:

        # Obtener las cuentas seed disponibles consultando al primario.
        # Se usan varias filas solo para no reescribir/releer siempre la
        # misma tupla.
        target_ids = [
            row[0]
            for row in conn_primary.execute("SELECT id FROM cuenta ORDER BY id").fetchall()
        ]
        if not target_ids:
            raise RuntimeError("No se encontraron cuentas seed en la tabla 'cuenta'.")

        print(f"Cuentas seed detectadas ({len(target_ids)}): {target_ids}")

        for operation in OPERATIONS:
            samples = measure(conn_primary, conn_replica, operation, target_ids, args.warmup, args.runs)
            node = node_for(operation)

            # Guardar mediciones en un formato ordenado
            for run, elapsed_ms in enumerate(samples, start=1):
                raw.append(
                    {
                        "operation": operation,
                        "node": node,
                        "run": run,
                        "latency_ms": f"{elapsed_ms:.3f}",
                    }
                )
            summaries.append(
                {
                    "operation": operation,
                    "node": node,
                    "n": len(samples),
                    "p50_ms": statistics.median(samples),
                    "p99_ms": percentile_nearest_rank(samples, 0.99),
                }
            )

    # Imprimir resultados
    print("\noperation node     n p50_ms p99_ms")
    for row in summaries:
        print(
            f"{row['operation']:9} {row['node']:8} "
            f"{row['n']:>2} "
            f"{row['p50_ms']:>7.3f} {row['p99_ms']:>7.3f}"
        )

    # Guardar resultados en un .csv
    if args.csv:
        os.makedirs(os.path.dirname(args.csv) or ".", exist_ok=True)
        with open(args.csv, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=raw[0].keys())
            writer.writeheader()
            writer.writerows(raw)
        print(f"\nMuestras guardadas en: {args.csv}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
