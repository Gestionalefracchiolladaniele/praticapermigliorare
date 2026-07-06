"""Connessione al DB per l'app a runtime (read-only, RLS forzata).

Punto chiave di v0: ogni query business gira dentro `tenant_session`, che apre
una transazione e imposta `app.tenant_id` con SET LOCAL. SET LOCAL vive solo per
la transazione corrente, quindi non c'è rischio che il tenant "resti impostato"
su una connessione riusata da un pool per un altro tenant.

Si connette come ruolo app (DATABASE_URL = bizquery_app, NOBYPASSRLS): così le
policy RLS dello schema sono davvero applicate. Se per errore l'app usasse il
superuser, la RLS verrebbe bypassata e l'isolamento multi-tenant sarebbe finto.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

import psycopg
from dotenv import load_dotenv

load_dotenv()


def _app_dsn() -> str:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError(
            "DATABASE_URL non impostata (ruolo app, read-only). "
            "Copia .env.example in .env."
        )
    return dsn


@contextmanager
def tenant_session(tenant_id: int) -> Iterator[psycopg.Connection]:
    """Apre una connessione con app.tenant_id impostato per la transazione.

    Uso:
        with tenant_session(1) as conn:
            rows = conn.execute("SELECT ...").fetchall()
    """
    conn = psycopg.connect(_app_dsn())
    try:
        # SET LOCAL richiede una transazione: psycopg apre implicitamente una
        # transazione alla prima query. Passiamo tenant_id come parametro NON
        # è possibile con SET LOCAL (non accetta placeholder), quindi validiamo
        # che sia un int prima di interpolarlo — difesa contro injection sul
        # canale di configurazione.
        tid = int(tenant_id)
        conn.execute(f"SET LOCAL app.tenant_id = {tid}")
        yield conn
        conn.rollback()  # v0 è read-only: nessuna modifica da persistere
    finally:
        conn.close()
