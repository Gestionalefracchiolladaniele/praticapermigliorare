"""Test di isolamento RLS — il piu' importante di v0 (dimostra che la sicurezza
multi-tenant e' reale, non teorica).

Gira SOLO con un DB popolato (Docker su + seed). Senza DATABASE_URL viene
skippato pulito invece di fallire: e' un test di integrazione, non unit.

Cosa dimostra:
  1. Connesso come tenant 1, vedo SOLO customers/orders del tenant 1.
  2. Una query SENZA WHERE su customers non fa uscire dati di altri tenant:
     la RLS filtra comunque (difesa vera, indipendente dal guardrail).
  3. Cambiando app.tenant_id cambiano i dati visti: isolamento effettivo.
"""
import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="Richiede DB popolato (Docker su + seed). Test di integrazione.",
)


def _count_all(tenant_id: int, table: str) -> int:
    from app.db.client import tenant_session
    # Volutamente SENZA where: se la RLS funziona, torna solo le righe del tenant.
    with tenant_session(tenant_id) as conn:
        return conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]


def test_customers_isolated_per_tenant():
    # Dal seed: 15 customers per tenant. Connesso come 1 devo vedere 15, non 30.
    assert _count_all(1, "customers") == 15
    assert _count_all(2, "customers") == 15


def test_orders_isolated_per_tenant():
    # Dal seed: 55 orders tenant 1, 45 tenant 2. Mai 100 (= totale).
    assert _count_all(1, "orders") == 55
    assert _count_all(2, "orders") == 45


def test_no_cross_tenant_leak_without_where():
    # Query "ingenua" senza filtro: la RLS deve comunque isolare.
    # Se vedessi 100 orders come tenant 1, la RLS sarebbe rotta.
    assert _count_all(1, "orders") != 100
    assert _count_all(2, "orders") != 100


def test_tenant_rows_are_actually_that_tenant():
    from app.db.client import tenant_session
    with tenant_session(1) as conn:
        tenants_seen = conn.execute(
            "SELECT DISTINCT tenant_id FROM orders"
        ).fetchall()
    # Come tenant 1 non devono comparire tenant_id diversi da 1.
    assert tenants_seen == [[1]] or tenants_seen == [(1,)]
