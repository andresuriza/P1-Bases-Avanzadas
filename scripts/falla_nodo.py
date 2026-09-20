#!/usr/bin/env python3
"""Sonda de escrituras para E4 (falla de nodo) sobre ControlDisponibilidad.

Escribe en bucle mientras dura la prueba. El host crea un archivo de señal
justo después del `docker stop`, y con eso calculamos el RTO real: tiempo
entre la falla y la primera escritura que vuelve a confirmarse.
"""

from __future__ import annotations

import argparse
import csv
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import psycopg


# FUNCIONES DE UTILIDAD
def utc_now() -> str:
    """
    Genera una marca de tiempo (UTC estandar) para registrar cuándo ocurren los eventos.
    """
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def connect() -> psycopg.Connection:
    """
    Abre una conexión rápida a la base de datos con límites estrictos de tiempo de espera..
    """
    return psycopg.connect(
        connect_timeout=2,
        options="-c statement_timeout=2000",
        autocommit=True,
    )


# OPERACIÓN DE ESCRITURA
def write_once() -> None:
    """
    Actualiza una fila específica (id = 1) en la tabla controldisponibilidad, sumándole 1 a su versión actual.
    """
    with connect() as conn:
        updated = conn.execute(
            """
            UPDATE controldisponibilidad
            SET version = version + 1, actualizado_en = now()
            WHERE id = 1
            RETURNING version
            """
        ).fetchone()
        if updated is None:
            raise RuntimeError(
                "No existe ControlDisponibilidad(id=1); aplique "
                "sql-scripts/schema.sql y sql-scripts/seed.sql primero"
            )


def read_signal(path: Path) -> float | None:
    """
    Busca y lee la marca de tiempo de la falla del nodo en el archivo .epoch generado.
    """
    try:
        return float(path.read_text(encoding="utf-8").strip())
    except (FileNotFoundError, ValueError):
        return None


def main() -> int:
    # Configuración y argumentos del script
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration", type=float, default=30)
    parser.add_argument("--interval", type=float, default=0.5)
    parser.add_argument("--label", default="Escenario A")
    parser.add_argument(
        "--signal-file",
        default="evidence/falla-nodo-stop.epoch",
        help="Archivo que el host crea justo después de docker stop",
    )
    parser.add_argument("--csv", default="evidence/falla-nodo.csv")
    args = parser.parse_args()

    # Lectura de argumentos
    signal_path = Path(args.signal_file)
    output_path = Path(args.csv)

    # Crear directorio de evidencia
    output_path.parent.mkdir(parents=True, exist_ok=True)

    started = time.time()
    samples: list[dict[str, str]] = []
    first_ok_after_signal: float | None = None
    failures_after_signal = 0

    print(f"=== E4 · sonda {args.label} ===")
    print(f"PGHOST={os.environ.get('PGHOST')}")
    print("Fila objetivo: controldisponibilidad(id=1), RF=3 (ver evidence/cluster-inspect.txt)")
    print(f"Señal de falla: {signal_path}")

    # Bucle de pruebas y medición
    while time.time() - started < args.duration:
        # Estado inicial de la prueba
        attempt_started = time.time()
        perf_started = time.perf_counter_ns()
        status = "ok"
        error = ""

        # Intento de escritura
        try:
            write_once()
        except Exception as exc:  # La clase concreta cambia según la causa.
            status = "error"
            error = f"{type(exc).__name__}: {str(exc).splitlines()[0]}"[:240]

        # Medición de latencia y tiempo de finalización
        latency_ms = (time.perf_counter_ns() - perf_started) / 1_000_000
        completed_at = time.time()

        # Detección de la falla del nodo
        signal_at = read_signal(signal_path)

        # Evaluación de fase post-falla
        phase = "before-stop"
        if signal_at is not None and completed_at >= signal_at: # Se ejecutó la escritura después de la falla?
            phase = "after-stop"
            if status == "error": # No se pudo completar la escritura?
                failures_after_signal += 1
            elif first_ok_after_signal is None:
                first_ok_after_signal = completed_at

        # Guardar resultado de las mediciones
        sample = {
            "timestamp_utc": utc_now(),
            "epoch": f"{attempt_started:.6f}",
            "completed_epoch": f"{completed_at:.6f}",
            "phase": phase,
            "status": status,
            "latency_ms": f"{latency_ms:.3f}",
            "error": error,
        }
        samples.append(sample)

        print(
            f"{sample['timestamp_utc']} {phase:11} {status:5} "
            f"{latency_ms:8.3f} ms {error}"
        )

        # Delay antes de la proxima prueba
        time.sleep(max(0.0, args.interval - (time.time() - attempt_started)))

    # Guardar resultados (.csv)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=samples[0].keys())
        writer.writeheader()
        writer.writerows(samples)

    # Cálculos finales del RTO
    signal_at = read_signal(signal_path)
    print(f"\nMuestras: {output_path}")
    print(f"Errores después de la señal: {failures_after_signal}")

    if signal_at is None:
        print("RTO no calculado: nunca apareció el archivo de señal.")
    elif first_ok_after_signal is None:
        print("RTO no observado: no hubo escritura OK después de la señal.")
    else:
        rto_ms = max(0.0, (first_ok_after_signal - signal_at) * 1000)
        print(f"RTO observado hasta primer write OK: {rto_ms:.1f} ms")

    print(
        "RPO se verifica aparte: la fila confirmada antes de la falla debe "
        "seguir presente y su version no debe retroceder."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
