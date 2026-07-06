"""Popola il DB v0 con dati finti riproducibili.

Uso:
    python -m app.db.seed          # applica schema.sql poi inserisce i dati

Richiede un Postgres raggiungibile via DATABASE_URL (vedi .env.example).
Fino a Docker pronto (step 6) non gira davvero: è lo step 1 del piano v0,
scrivibile subito, verifica bloccata su Docker.

Perché seed deterministico (random.seed fisso): l'evaluation harness (step 5)
confronta risultati numerici attesi; se i dati cambiassero a ogni run, i valori
attesi in eval/dataset.json non avrebbero senso. Stesso seed => stesso DB.
"""
from __future__ import annotations

import os
import random
from pathlib import Path

import psycopg
from dotenv import load_dotenv

load_dotenv()

SEED = 42
random.seed(SEED)

SCHEMA_PATH = Path(__file__).parent / "schema.sql"

TENANTS = [
    (1, "Acme SRL"),
    (2, "Globex SPA"),
]

COUNTRIES = ["Italy", "Germany", "France", "Spain", "United States"]
FIRST_NAMES = ["Marco", "Giulia", "Luca", "Sara", "Anna", "Paolo", "Elena",
               "Davide", "Chiara", "Simone", "Federica", "Andrea"]
LAST_NAMES = ["Rossi", "Bianchi", "Ferrari", "Russo", "Romano", "Gallo",
              "Costa", "Fontana", "Conti", "Ricci", "Marino", "Greco"]
STATUSES = ["pending", "paid", "paid", "paid", "cancelled", "refunded"]  # pesato verso 'paid'

N_CUSTOMERS_PER_TENANT = 15   # 2 tenant => 30 customers
N_ORDERS = 100


def _connect() -> psycopg.Connection:
    # Il seed CREA tabelle e ruoli → serve l'owner/superuser, non il ruolo app
    # (che è read-only e con RLS forzata). Da qui DATABASE_URL_ADMIN.
    dsn = os.environ.get("DATABASE_URL_ADMIN") or os.environ.get("DATABASE_URL")
    if not dsn:
        raise SystemExit(
            "DATABASE_URL_ADMIN non impostata. Copia .env.example in .env e valorizzala "
            "(serve Postgres in piedi — Docker, step 6 del piano v0)."
        )
    return psycopg.connect(dsn)


def apply_schema(conn: psycopg.Connection) -> None:
    """Esegue schema.sql. Come owner/superuser: qui SI vuole creare tabelle."""
    conn.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()


def seed_data(conn: psycopg.Connection) -> None:
    # tenants
    for tid, name in TENANTS:
        conn.execute("INSERT INTO tenants (id, name) VALUES (%s, %s)", (tid, name))

    # customers: id assegnato dal SERIAL, ma ci serve mapparli per tenant per
    # generare orders coerenti (un order appartiene a un customer dello stesso tenant).
    customers_by_tenant: dict[int, list[int]] = {tid: [] for tid, _ in TENANTS}
    for tid, _ in TENANTS:
        for _ in range(N_CUSTOMERS_PER_TENANT):
            fn = random.choice(FIRST_NAMES)
            ln = random.choice(LAST_NAMES)
            email = f"{fn.lower()}.{ln.lower()}@example.com"
            country = random.choice(COUNTRIES)
            row = conn.execute(
                "INSERT INTO customers (tenant_id, name, email, country) "
                "VALUES (%s, %s, %s, %s) RETURNING id",
                (tid, f"{fn} {ln}", email, country),
            ).fetchone()
            customers_by_tenant[tid].append(row[0])

    # orders: 100 totali, distribuiti sui tenant, ogni order coerente col tenant
    for _ in range(N_ORDERS):
        tid = random.choice([t for t, _ in TENANTS])
        cust_id = random.choice(customers_by_tenant[tid])
        total = round(random.uniform(10.0, 5000.0), 2)
        status = random.choice(STATUSES)
        conn.execute(
            "INSERT INTO orders (tenant_id, customer_id, total_amount, status) "
            "VALUES (%s, %s, %s, %s)",
            (tid, cust_id, total, status),
        )

    # riallinea la sequence di tenants (abbiamo inserito id espliciti)
    conn.execute("SELECT setval('tenants_id_seq', (SELECT MAX(id) FROM tenants))")
    conn.commit()


def main() -> None:
    with _connect() as conn:
        apply_schema(conn)
        seed_data(conn)
        n_cust = conn.execute("SELECT count(*) FROM customers").fetchone()[0]
        n_ord = conn.execute("SELECT count(*) FROM orders").fetchone()[0]
    print(f"Seed completato: {n_cust} customers, {n_ord} orders su {len(TENANTS)} tenant.")


if __name__ == "__main__":
    main()
