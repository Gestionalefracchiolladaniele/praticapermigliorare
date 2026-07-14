"""Evaluation harness v0 (step 5 del piano).

Per ogni caso in dataset.json esegue la pipeline REALE:
    domanda -> Gemini genera SQL -> guardrail valida -> esegue sul DB (RLS) ->
    estrae il valore scalare -> confronta con l'atteso.

Metrica v0: execution accuracy = quante domande danno il numero giusto.
Output: stampa a video + JSON in eval/results/<timestamp>.json.

Richiede DB popolato (seed) e GEMINI_API_KEY => gira solo con Docker su (step 6).
Lo script e' pronto ora; l'esecuzione e' bloccata finche' non c'e' il DB.

Perche' scalare: le domande v0 ritornano un singolo numero (count/sum). Prendiamo
la prima colonna della prima riga come risultato. Domande piu' ricche (righe,
LLM-as-judge) arrivano al Livello 3.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from app.guardrail import check_sql
from app.llm.gemini_client import generate_sql

DATASET = Path(__file__).parent / "dataset.json"
RESULTS_DIR = Path(__file__).parent / "results"


def _extract_scalar(rows: list) -> float | int | None:
    """Prende il primo valore della prima riga (count/sum tornano cosi')."""
    if not rows or not rows[0]:
        return None
    val = rows[0][0]
    if val is None:
        return None
    # NUMERIC di Postgres torna Decimal -> float per confronto.
    return float(val)


def _matches(got, expected, tolerance: float | None) -> bool:
    if got is None:
        return False
    if tolerance is not None:
        return abs(float(got) - float(expected)) <= tolerance
    return float(got) == float(expected)


def evaluate() -> dict:
    """Gira la pipeline su tutto il dataset e ritorna i numeri, senza stampare.

    Estratto da run() perche' il quality_gate ha bisogno del VALORE dell'accuracy
    (per confrontarlo con una soglia), non solo dell'exit code. run() resta la
    versione "da riga di comando" che stampa e usa questi numeri.

    Ritorna: {"accuracy": float, "passed": int, "total": int, "results": [...]}.
    """
    # Import qui: serve il DB, non deve rompere l'import del modulo se manca psycopg
    # in contesti dove eval non gira.
    from app.db.client import tenant_session

    data = json.loads(DATASET.read_text(encoding="utf-8"))
    cases = data["cases"]

    results = []
    passed = 0
    for c in cases:
        row = {"id": c["id"], "question": c["question"], "expected": c["expected"]}
        try:
            sql = generate_sql(c["question"], c["tenant_id"])
            row["generated_sql"] = sql

            verdict = check_sql(sql)
            if not verdict.approved:
                row.update(status="guardrail_rejected", reason=verdict.reason, ok=False)
                results.append(row)
                continue

            with tenant_session(c["tenant_id"]) as conn:
                rows = [list(r) for r in conn.execute(sql).fetchall()]
            got = _extract_scalar(rows)
            ok = _matches(got, c["expected"], c.get("tolerance"))
            row.update(status="executed", got=got, ok=ok)
            if ok:
                passed += 1
        except Exception as e:  # noqa: BLE001 — vogliamo continuare sul caso dopo
            row.update(status="error", error=str(e), ok=False)
        results.append(row)

    total = len(cases)
    accuracy = passed / total if total else 0.0
    return {"accuracy": accuracy, "passed": passed, "total": total, "results": results}


def run() -> int:
    report = evaluate()
    results = report["results"]
    passed, total, accuracy = report["passed"], report["total"], report["accuracy"]

    # Stampa leggibile
    for r in results:
        mark = "OK " if r.get("ok") else "XX "
        detail = r.get("got", r.get("reason") or r.get("error", ""))
        print(f"{mark}{r['id']:22} atteso={r['expected']!s:>10}  ottenuto={detail}")
    print(f"\nExecution accuracy: {passed}/{total} = {accuracy:.0%}")

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = RESULTS_DIR / f"{ts}.json"
    try:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"Salvato: {out}")
    except OSError as e:
        # In container (utente non-root, FS immagine read-only) il salvataggio
        # puo' fallire: il punteggio e' gia' stampato sopra, non e' fatale.
        print(f"[warn] risultati non salvati su {out}: {e}")

    # exit code != 0 se non tutto verde: utile per CI (Livello 2).
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(run())
