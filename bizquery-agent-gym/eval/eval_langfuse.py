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
    docker compose exec -T app python -m eval.eval_langfuse           # 5 casi, solo 'correct'
    docker compose exec -T app python -m eval.eval_langfuse --all     # tutti e 15
    docker compose exec -T app python -m eval.eval_langfuse --no-cache  # ignora cache SQL
    docker compose exec -T app python -m eval.eval_langfuse --judge   # + LLM-as-judge (qualita')

NB --judge: aggiunge 3 score di qualita' (faithfulness/relevance/safety) via un
secondo LLM-giudice. Costa 1 chiamata Gemini PER CASO -> e' opt-in per non bruciare
il free tier. Vedi app/llm/judge.py per il come e il perche'.
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
    """Pipeline BizQuery su un item del dataset -> output DICT arricchito.

    Riceve un DatasetItem: item.input (dict con 'question'), item.expected_output,
    item.metadata (tenant_id, tolerance, ...). Langfuse traccia questa funzione come
    la trace dell'item.

    OUTPUT: prima ritornavamo lo scalare nudo. Ora ritorniamo un DICT con tutto
    cio' che serve ai due tipi di evaluator che girano sullo stesso caso:
      - correct_evaluator legge output["scalar"]  (execution accuracy, come prima)
      - i judge evaluator leggono question/sql/rows/answer (qualita' multi-criterio)
    Un dict solo alimenta entrambi con UNA sola esecuzione della pipeline: non
    rieseguiamo SQL o formattazione per criterio.
    """
    from app.answer import format_answer
    from app.db.client import tenant_session
    from app.guardrail import check_sql
    from app.tools.mask_pii import mask_pii_in_rows

    question = item.input["question"]
    tenant_id = item.metadata["tenant_id"]
    item_id = item.id

    sql = _get_sql(item_id, question, tenant_id)

    verdict = check_sql(sql)
    if not verdict.approved:
        # Guardrail-reject: nessuna risposta prodotta. Output senza 'answer' ->
        # correct lo vede != expected (scalar=None), i judge lo vedono come
        # "nessuna risposta da giudicare". Conta come fallito, non crasha.
        return {
            "question": question, "sql": sql, "scalar": None,
            "error": "guardrail_rejected", "reason": verdict.reason,
        }

    with tenant_session(tenant_id) as conn:
        rows = [list(r) for r in conn.execute(sql).fetchall()]

    # La RISPOSTA che il judge valuta e' quella VERA che vede l'utente: righe
    # mascherate (PII) -> formattazione NL deterministica. Cosi' safety e
    # faithfulness sono giudicate sull'output reale del sistema, non su un proxy.
    masked = mask_pii_in_rows(rows)
    answer = format_answer(question, masked)

    return {
        "question": question,
        "sql": sql,
        "rows": masked,
        "answer": answer,
        "scalar": _extract_scalar(rows),  # per correct_evaluator (valore non mascherato)
    }


def correct_evaluator(*, input=None, output=None, expected_output=None, metadata=None, **kwargs):
    """Score 'correct' 1/0: lo scalare prodotto corrisponde all'atteso?

    Legge output["scalar"] dal dict arricchito del task. Usa la tolerance dal
    metadata per i confronti float (fatturati/medie). Scalare mancante (None,
    es. guardrail-reject) -> 0.
    """
    scalar = output.get("scalar") if isinstance(output, dict) else output
    if not isinstance(scalar, (int, float)):
        return Evaluation(name="correct", value=0.0, comment=f"output non numerico: {scalar}")
    if expected_output is None:
        return Evaluation(name="correct", value=0.0, comment="nessun expected_output")

    tolerance = (metadata or {}).get("tolerance")
    if tolerance is not None:
        ok = abs(float(scalar) - float(expected_output)) <= tolerance
    else:
        ok = float(scalar) == float(expected_output)
    return Evaluation(
        name="correct",
        value=1.0 if ok else 0.0,
        comment=f"ottenuto={scalar} atteso={expected_output}",
    )


def run(subset: list[str] | None, *, with_judge: bool = False) -> int:
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

    # Evaluator: sempre 'correct' (execution accuracy). Con --judge aggiungiamo i
    # tre criteri di qualita' LLM-as-judge. Sono OPT-IN perche' ognuno costa 1
    # chiamata Gemini per caso: si accende quando serve, non a ogni run, per non
    # bruciare il free tier (~20 chiamate/giorno).
    evaluators = [correct_evaluator]
    if with_judge:
        from eval.judge_evaluators import JUDGE_EVALUATORS, reset_memo

        reset_memo()
        evaluators = evaluators + JUDGE_EVALUATORS

    result = dataset.run_experiment(
        name="BizQuery eval",
        description=(
            "Pipeline domanda->SQL->DB. Score: correct (accuracy)"
            + (" + faithfulness/relevance/safety (LLM-judge)" if with_judge else "")
        ),
        task=task,
        evaluators=evaluators,
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
    parser.add_argument(
        "--judge", action="store_true",
        help="aggiungi gli score LLM-as-judge (faithfulness/relevance/safety). "
             "Costa 1 chiamata Gemini per caso: occhio al free tier.",
    )
    args = parser.parse_args()

    if args.no_cache:
        _use_cache = False
    subset = None if args.all else _DEFAULT_SUBSET
    sys.exit(run(subset, with_judge=args.judge))
