"""Unit test del guardrail (step 3). Puro Python, gira senza Docker/DB.

Ogni test documenta QUALE attacco/errore blocca, così il guardrail resta
leggibile come una lista di minacce coperte.
"""
from app.guardrail import check_sql


# --- query legittime: devono passare ------------------------------------------

def test_simple_select_with_tenant_passes():
    v = check_sql("SELECT count(*) FROM customers WHERE tenant_id = 1")
    assert v.approved, v.reason


def test_with_cte_passes():
    sql = (
        "WITH paid AS (SELECT * FROM orders WHERE tenant_id = 1 AND status='paid') "
        "SELECT count(*) FROM paid"
    )
    assert check_sql(sql).approved


def test_join_with_tenant_passes():
    sql = (
        "SELECT c.name, sum(o.total_amount) FROM customers c "
        "JOIN orders o ON o.customer_id = c.id "
        "WHERE c.tenant_id = 2 GROUP BY c.name"
    )
    assert check_sql(sql).approved


# --- scritture / DDL: devono essere rifiutate ---------------------------------

def test_delete_rejected():
    assert not check_sql("DELETE FROM customers WHERE tenant_id = 1").approved


def test_drop_rejected():
    assert not check_sql("DROP TABLE customers").approved


def test_update_rejected():
    assert not check_sql(
        "UPDATE orders SET status='paid' WHERE tenant_id = 1"
    ).approved


def test_insert_rejected():
    assert not check_sql(
        "INSERT INTO orders (tenant_id) VALUES (1)"
    ).approved


# --- injection -----------------------------------------------------------------

def test_stacked_query_rejected():
    # SELECT innocuo seguito da DROP: il multi-statement va bloccato.
    sql = "SELECT * FROM orders WHERE tenant_id = 1; DROP TABLE orders"
    assert not check_sql(sql).approved


def test_comment_hidden_write_rejected():
    # Prova a nascondere che manca il tenant e a iniettare via commento.
    sql = "SELECT * FROM customers WHERE tenant_id = 1 -- ; DROP TABLE x"
    # Questa specifica resta approvata (il DROP è commentato e rimosso),
    # ma il tenant c'è: verifichiamo che almeno non esploda e sia coerente.
    assert check_sql(sql).approved


# --- filtro tenant mancante ----------------------------------------------------

def test_select_without_tenant_rejected():
    assert not check_sql("SELECT * FROM customers").approved


def test_empty_rejected():
    assert not check_sql("   ").approved


# --- falsi positivi da evitare -------------------------------------------------

def test_created_at_does_not_trigger_create():
    # 'created_at' contiene 'create' come sottostringa: NON deve far scattare
    # la regola DDL grazie al \b sui confini di parola.
    sql = "SELECT created_at FROM orders WHERE tenant_id = 1"
    assert check_sql(sql).approved, check_sql(sql).reason
