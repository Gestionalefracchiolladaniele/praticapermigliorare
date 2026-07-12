"""Experiment Langfuse sul dataset bizquery-eval (Capacita' 2 — evaluation offline).

Questo file e' il cuore della Capacita' 2. Fa girare la pipeline REALE su ogni item
del dataset caricato con langfuse_dataset.py, e produce una DATASET RUN in Langfuse
con uno SCORE 'correct' (1/0) per ogni caso — navigabile e confrontabile nella UI.

Il pattern v4: dataset.run_experiment(task=..., evaluators=[...]).
  - Langfuse orchestra tutto: per ogni item apre una trace, chiama il TUO task,
    chiama i TUOI evaluator, crea gli score, li lega alla run. Noi forniamo solo
    i due pezzi che cambiano da progetto a progetto:

  TASK      = come produco l'output  -> la pipeline BizQuery (domanda -> SQL ->
              guardrail -> DB -> scalare). E' la parte che chiama Gemini.
  EVALUATOR = come giudico se e' giusto -> confronto scalare vs expected (con la
              tolerance per i float) -> {"name":"correct","value":1.0/0.0}.

Separare task ed evaluator NON e' un dettaglio: e' "evaluation framework". La
pipeline puo' cambiare (prompt, modello) e la metrica resta la stessa -> esperimenti
confrontabili. E' cio' che gli annunci chiamano "reproducible evaluation".

--- STRATEGIA RATE-LIMIT (Gemini free tier ~20 chiamate/giorno) ---
La parte costosa e' "domanda -> SQL" (1 chiamata Gemini per caso). Ma per un dato
item la domanda e' sempre la stessa -> l'SQL e' (quasi) sempre lo stesso. Quindi
CACHIAMO l'SQL generato su file: primo giro chiama Gemini e salva; giri successivi
rileggono dal file -> ZERO chiamate. Cosi' puoi rilanciare l'experiment quante volte
vuoi per prendere confidenza con la UI, senza bruciare la quota. (E' anche un pattern
vero di produzione: "generation caching" per cost/latency control.)

Uso:
    docker compose exec -T app python -m eval.eval_langfuse         # 5 casi (default)
    docker compose exec -T app python -m eval.eval_langfuse --all   # tutti e 15
    docker compose exec -T app python -m eval.eval_langfuse --no-cache  # ignora cache SQL
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from langfuse import Evaluation

from app.observability.langfuse_setup import flush, get_client

DATASET_NAME = "bizquery-eval"
# La cache SQL vive accanto ai risultati; e' un semplice dict {item_id: sql}.
SQL_CACHE_FILE = Path(__file__).parent / "results" / "sql_cache.json"

# Quali item nel sottoinsieme di default (uno per "tipo" di query, cosi' 5 casi
# coprono count / sum-con-tolerance / group-by / count-distinct).
_DEFAULT_SUBSET = [
    "t1_num_customers",       # count semplice
    "t1_revenue_paid",        # sum con tolerance (float)
    "t1_customers_italy",     # count con filtro
    "t1_max_orders_per_customer",  # group by + max
    "t1_customers_with_orders",    # count distinct
]

# Cache SQL caricata una volta a inizio processo. _USE_CACHE / _SAVE_CACHE
# controllati dai flag CLI.
_sql_cache: dict[str, str] = {}
_use_cache = True


def _load_cache() -> None:
    global _sql_cache
    if _use_cache and SQL_CACHE_FILE.exists():
        try:
            _sql_cache = json.loads(SQL_CACHE_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            _sql_cache = {}


def _save_cache() -> None:
    try:
        SQL_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        SQL_CACHE_FILE.write_text(
            json.dumps(_sql_cache, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        pass  # best-effort: se non si puo' scrivere, pazienza (container non-root)


def _extract_scalar(rows: list) -> float | None:
    """Primo valore della prima riga (count/sum tornano cosi'). Come in eval.py."""
    if not rows or not rows[0]:
        return None
    val = rows[0][0]
    return None if val is None else float(val)


def _get_sql(item_id: str, question: str, tenant_id: int) -> str:
    """SQL dalla cache se c'e', altrimenti chiede a Gemini e lo mette in cache."""
    if _use_cache and item_id in _sql_cache:
        return _sql_cache[item_id]
    from app.llm.gemini_client import generate_sql

    sql = generate_sql(question, tenant_id)
    _sql_cache[item_id] = sql
    return sql


def task(*, item, **kwargs):
    """Pipeline BizQuery su un item del dataset -> output scalare (o dict d'errore).

    Riceve un DatasetItem: item.input (dict con 'question'), item.expected_output,
    item.metadata (tenant_id, tolerance, ...). Langfuse traccia questa funzione come
    la trace dell'item.
    """
    from app.db.client import tenant_session
    from app.guardrail import check_sql

    question = item.input["question"]
    tenant_id = item.metadata["tenant_id"]
    item_id = item.id

    sql = _get_sql(item_id, question, tenant_id)

    verdict = check_sql(sql)
    if not verdict.approved:
        # Ritorniamo un output "non numerico" strutturato: l'evaluator lo vedra'
        # come != expected -> score 0. Cosi' un guardrail-reject conta come fallito
        # ma non fa crashare l'experiment.
        return {"error": "guardrail_rejected", "reason": verdict.reason, "sql": sql}

    with tenant_session(tenant_id) as conn:
        rows = [list(r) for r in conn.execute(sql).fetchall()]
    return _extract_scalar(rows)


def correct_evaluator(*, input, output, expected_output=None, metadata=None, **kwargs):
    """Score 'correct' 1/0: l'output scalare corrisponde all'atteso?

    Usa la tolerance dal metadata per i confronti float (fatturati/medie). Un output
    non numerico (dict d'errore da guardrail) -> 0.
    """
    if not isinstance(output, (int, float)):
        return Evaluation(name="correct", value=0.0, comment=f"output non numerico: {output}")
    if expected_output is None:
        return Evaluation(name="correct", value=0.0, comment="nessun expected_output")

    tolerance = (metadata or {}).get("tolerance")
    if tolerance is not None:
        ok = abs(float(output) - float(expected_output)) <= tolerance
    else:
        ok = float(output) == float(expected_output)
    return Evaluation(
        name="correct",
        value=1.0 if ok else 0.0,
        comment=f"ottenuto={output} atteso={expected_output}",
    )


def run(subset: list[str] | None) -> int:
    client = get_client()
    if client is None:
        print("[stop] Langfuse non configurato. Carica prima il dataset e le chiavi.")
        return 1

    _load_cache()
    dataset = client.get_dataset(DATASET_NAME)

    # run_experiment gira su TUTTI gli item del dataset client. Per il sottoinsieme
    # filtriamo gli item prima, costruendo un dataset "ristretto" via la sua API:
    # piu' semplice e robusto e' filtrare qui e passare solo quelli al task tramite
    # un dataset client filtrato. In v4 il modo diretto e' iterare noi e usare
    # dataset.items; ma run_experiment vuole il dataset client. Soluzione pulita:
    # se subset e' dato, restringiamo dataset.items in-place (lista Python).
    if subset is not None:
        dataset.items = [it for it in dataset.items if it.id in subset]

    result = dataset.run_experiment(
        name="BizQuery eval",
        description="Execution accuracy della pipeline (domanda->SQL->DB) sui casi seed.",
        task=task,
        evaluators=[correct_evaluator],
    )

    if _use_cache:
        _save_cache()
    flush()

    print(result.format())
    print("\nURL run:", result.dataset_run_url)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="gira tutti e 15 i casi")
    parser.add_argument("--no-cache", action="store_true", help="ignora la cache SQL")
    args = parser.parse_args()

    if args.no_cache:
        _use_cache = False
    subset = None if args.all else _DEFAULT_SUBSET
    sys.exit(run(subset))
