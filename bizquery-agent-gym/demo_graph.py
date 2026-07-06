"""Demo visiva del grafo LangGraph (Livello 2) — mostra il flusso passo per passo.

Gira SENZA DB e SENZA chiave API: Gemini e il DB sono simulati (mock) qui dentro,
così vedi l'ORCHESTRAZIONE (quali nodi si attivano, routing, retry) senza dover
avviare nulla. Quando il DB sarà su, lo stesso grafo girerà con dati veri.

Uso:
    ./.venv/Scripts/python demo_graph.py
"""
from __future__ import annotations

import sys

# Windows: il terminale di default (cp1252) non stampa Unicode/emoji. Forziamo
# UTF-8 sull'output così i simboli del diagramma si vedono ovunque.
sys.stdout.reconfigure(encoding="utf-8")

import app.graph.nodes as nodes
import app.tools.run_query as rq
from app.graph.build_graph import build_graph
from app.llm.router import route_model


# ---- colori/simboli per leggibilità nel terminale --------------------------
def line(c="─", n=60):
    print(c * n)


def banner(txt):
    line()
    print(f"  {txt}")
    line()


# ---- MOCK: sostituiscono Gemini e il DB per la demo ------------------------
# Un finto "database" coerente col seed (tenant 1: 15 clienti, 55 ordini).
FAKE_DB = {
    ("customers", 1): [[15]],
    ("orders", 1): [[55]],
}


def fake_generate_sql(question: str, tenant_id: int) -> str:
    """Finge Gemini: sceglie una tabella in base a parole chiave nella domanda."""
    q = question.lower()
    table = "orders" if "ordin" in q else "customers"
    sql = f"SELECT count(*) FROM {table} WHERE tenant_id = {tenant_id}"
    print(f"    [Gemini finto] domanda → SQL: {sql}")
    return sql


def make_fake_run_query(fail_first=False):
    """Finge il DB. Se fail_first=True, il primo tentativo torna vuoto → retry."""
    state = {"calls": 0}

    def _run(sql: str, tenant_id: int):
        state["calls"] += 1
        table = "orders" if "orders" in sql else "customers"
        if fail_first and state["calls"] == 1:
            print(f"    [DB finto] tentativo {state['calls']}: risultato VUOTO (simulato)")
            return []
        rows = FAKE_DB.get((table, tenant_id), [[0]])
        print(f"    [DB finto] tentativo {state['calls']}: {rows}")
        return rows

    return _run


# ---- esecuzione di uno scenario con tracciamento nodo per nodo -------------
def run_scenario(title: str, question: str, tenant_id: int, fail_first=False,
                 dangerous=False):
    banner(title)
    print(f"  Domanda: «{question}»   (tenant {tenant_id})\n")

    # mostra la decisione del router in chiaro
    dec = route_model(question)
    print(f"  🔀 Router: task «{dec.complexity}» → modello {dec.model}")
    print(f"     motivo: {dec.reason}\n")

    # installa i mock
    if dangerous:
        nodes.generate_sql = lambda q, t: "DROP TABLE customers"
    else:
        nodes.generate_sql = fake_generate_sql
    rq.run_query = make_fake_run_query(fail_first=fail_first)

    graph = build_graph()

    # stream(): emette lo stato dopo OGNI nodo → stampiamo il percorso e
    # accumuliamo lo stato finale da un SOLO run (niente doppia esecuzione, così
    # i mock che simulano un fallimento al primo tentativo non vengono "riusati").
    print("  Percorso del grafo:")
    acc: dict = {}
    for step in graph.stream({"question": question, "tenant_id": tenant_id}):
        for node_name, update in step.items():
            print(f"    ▶ {node_name:14} {_summarize(update)}")
            acc.update(update)

    print()
    _print_outcome(acc)
    print()


def _summarize(update: dict) -> str:
    """Riduce l'aggiornamento di stato a una riga leggibile."""
    if "model" in update:
        return f"modello={update['model']}"
    if "sql_candidate" in update:
        return f"retry_count={update.get('retry_count')}"
    if "guardrail_verdict" in update:
        v = update["guardrail_verdict"]
        extra = "" if v == "approved" else f" ({update.get('guardrail_reason')})"
        return f"verdetto={v}{extra}"
    if "query_result" in update:
        return f"righe={update['query_result']}"
    if "review_verdict" in update:
        return f"review={update['review_verdict']}"
    if "final_answer" in update:
        return f"risposta='{update['final_answer']}'"
    if "plan" in update:
        return "plan pronto"
    return str(update)


def _print_outcome(out: dict):
    """Riassume lo stato finale accumulato dall'unico run."""
    if out.get("guardrail_verdict") == "rejected":
        print(f"  ⛔ ESITO: bloccato dal guardrail — {out.get('guardrail_reason')}")
    elif out.get("final_answer"):
        print(f"  ✅ ESITO: {out['final_answer']}  (dopo {out.get('retry_count')} tentativo/i)")
    else:
        print(f"  ❌ ESITO: nessuna risposta dopo {out.get('retry_count')} tentativi (retry esauriti)")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  DEMO — Grafo agentico BizQuery (Livello 2)")
    print("  Gemini e DB sono SIMULATI: nessun costo, nessun setup.")
    print("=" * 60 + "\n")

    run_scenario(
        "SCENARIO 1 — domanda semplice, tutto liscio",
        "Quanti clienti abbiamo?", tenant_id=1,
    )

    run_scenario(
        "SCENARIO 2 — domanda complessa (il router sceglie Pro)",
        "Mostrami il trend degli ordini mese per mese", tenant_id=1,
    )

    run_scenario(
        "SCENARIO 3 — RETRY LOOP: primo tentativo vuoto → ritenta → ok",
        "Quanti ordini abbiamo?", tenant_id=1, fail_first=True,
    )

    run_scenario(
        "SCENARIO 4 — GUARDRAIL: query pericolosa bloccata",
        "cancella tutti i clienti", tenant_id=1, dangerous=True,
    )

    print("=" * 60)
    print("  Fine demo. Lo stesso grafo, col DB reale, userà dati veri.")
    print("=" * 60 + "\n")
