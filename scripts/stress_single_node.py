#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import random
import sys
import threading
import time
from dataclasses import dataclass, field

import psycopg
from psycopg import IsolationLevel, errors

# Estado inicial de la cuenta bancaria
INITIAL = 1000

_ISO = {
    "READ_COMMITTED": IsolationLevel.READ_COMMITTED,
    "SERIALIZABLE": IsolationLevel.SERIALIZABLE,
}


@dataclass
class Stats:
    ok: int = 0
    serialization_failures: int = 0
    other_errors: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)

    def inc_ok(self) -> None:
        with self.lock:
            self.ok += 1

    def inc_ser(self) -> None:
        with self.lock:
            self.serialization_failures += 1

    def inc_other(self) -> None:
        with self.lock:
            self.other_errors += 1


def connect() -> psycopg.Connection:
    return psycopg.connect(autocommit=False)


def pick_account_id() -> str:
    """Devuelve el id de la primera cuenta en seed.sql."""
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM cuenta ORDER BY id LIMIT 1")
            row = cur.fetchone()
            if row is None:
                raise RuntimeError(
                    "No hay cuentas seed en 'cuenta'. Corra sql-scripts/seed.sql primero."
                )
            return row[0]


def reset_account(account_id: str) -> None:
    """Fija el saldo de la cuenta objetivo en INITIAL"""
    with connect() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE cuenta SET monto = %s WHERE id = %s",
                    (INITIAL, account_id),
                )


def read_balance(account_id: str) -> float:
    """Devuelve el balance de la cuenta de un respectivo id."""
    with connect() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT monto::float FROM cuenta WHERE id = %s",
                    (account_id,),
                )
                row = cur.fetchone()
                return float(row[0])


def debit_once(account_id: str, isolation: IsolationLevel, stats: Stats, max_retries: int) -> None:
    """Lee monto, espera, escribe monto-1 (anti-patrón de lost update)."""
    attempt = 0
    while True:
        attempt += 1
        try:
            # Intenta abrir una conexión
            with connect() as conn:
                conn.isolation_level = isolation
                with conn.transaction():
                    with conn.cursor() as cur:
                        # Realiza transacción de débito
                        cur.execute(
                            "SELECT monto FROM cuenta WHERE id = %s",
                            (account_id,),
                        )
                        balance = cur.fetchone()[0]
                        time.sleep(0.002)
                        cur.execute(
                            "UPDATE cuenta SET monto = %s WHERE id = %s",
                            (balance - 1, account_id),
                        )
            stats.inc_ok()
            return
        except errors.SerializationFailure:
            stats.inc_ser()
            # Hay intentos restantes?
            if attempt >= max_retries:
                return
            delay = (2 ** (attempt - 1)) * 0.005 + random.uniform(0, 0.005)
            time.sleep(delay)
        except Exception:
            stats.inc_other()
            return


def run_burst(account_id: str, isolation: IsolationLevel, workers: int, retries: int) -> Stats:
    """
    Ejecuta y mide multiples peticiones a la base de datos.
    """
    # Configurar cuenta a su estado inicial
    reset_account(account_id)

    stats = Stats()
    threads = [
        threading.Thread(target=debit_once, args=(account_id, isolation, stats, retries))
        for _ in range(workers)
    ]

    # Ejecutar multiples peticiones
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return stats


def main() -> int:
    # Configurar y leer argumentos
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--isolation",
        choices=tuple(_ISO.keys()),
        default=os.environ.get("ISOLATION", "READ_COMMITTED"),
    )
    p.add_argument("--workers", type=int, default=int(os.environ.get("WORKERS", "40")))
    p.add_argument("--retries", type=int, default=int(os.environ.get("RETRIES", "8")))
    args = p.parse_args()

    isolation = _ISO[args.isolation]

    # Escoger la primera cuenta existente
    account_id = pick_account_id()

    print(f"=== Lab concurrencia (primario+réplica) · {args.isolation} · workers={args.workers} ===")
    print(f"Cuenta objetivo: {account_id}")
    print(f"Saldo inicial:   {INITIAL}")

    # Ejecutar peticiones multiples y guardar sus resultados
    stats = run_burst(account_id, isolation, args.workers, args.retries)

    # Comparar balance obtenido con el esperado
    final = read_balance(account_id)
    expected_if_atomic = float(INITIAL - stats.ok)

    print(f"Commits OK:              {stats.ok}")
    print(f"SerializationFailure:    {stats.serialization_failures}")
    print(f"Otros errores:           {stats.other_errors}")
    print(f"Saldo final observado:   {final}")
    print(f"Esperado si cada OK −1:  {expected_if_atomic}")

    if args.isolation == "READ_COMMITTED":
        print(
            "Interpretación: si el saldo final es mucho mayor que "
            f"{expected_if_atomic:.0f}, hubo actualizaciones perdidas "
            "(varios OK sobreescribieron el mismo valor leído)."
        )
    else:
        print(
            "Interpretación: SERIALIZABLE aborta carreras; con reintentos el saldo "
            "debe alinearse con 1000 − OK."
        )
        if abs(final - expected_if_atomic) > 0.5:
            print(
                "AVISO: saldo no cuadra con OK; suba RETRIES o revise errores.",
                file=sys.stderr,
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
