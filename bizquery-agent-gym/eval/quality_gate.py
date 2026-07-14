"""Quality gate — il cancello di qualita' della CI (regression testing).

COSA FA E PERCHE'
-----------------
L'eval MISURA (produce un numero). Il gate DECIDE se il numero e' abbastanza:
confronta le metriche con le soglie in thresholds.json e ritorna un EXIT CODE.
  exit 0  -> tutte le soglie rispettate  -> la CI passa
  exit 1  -> almeno una metrica sotto soglia -> la CI FALLISCE (merge/deploy bloccato)

L'exit code e' il linguaggio che GitHub Actions capisce. E' questo che trasforma
"ho un punteggio" in "il punteggio DIFENDE il sistema": se un domani cambi un
prompt e l'accuracy crolla, il gate se ne accorge e impedisce che quel codice
vada in produzione. Questo e' il "regression testing dell'agente in CI" del
PROJECT.md, ed e' il pezzo che fa di BizQuery un sistema di eval, non uno script.

DUE LIVELLI DI GATE
-------------------
1) SEMPRE: execution_accuracy (dal tuo eval.py, senza Langfuse). Economico, gira
   ovunque, e' il controllo base "il sistema da' ancora i numeri giusti?".
2) OPZIONALE (--judge): le metriche di qualita' dell'LLM-as-judge
   (faithfulness/relevance/safety). Costano chiamate Gemini -> opt-in, come nell'eval.

DIPENDENZE
----------
Il gate base NON richiede Langfuse (gira in CI dove Langfuse puo' non esserci).
Richiede pero' il DB popolato + GEMINI_API_KEY, esattamente come eval.py: quindi
in CI va eseguito nel contesto che ha un Postgres di test seedato (lo predisporra'
il workflow GitHub Actions al passo successivo).

USO
---
    python -m eval.quality_gate            # gate su execution_accuracy
    python -m eval.quality_gate --judge    # + soglie judge (costa chiamate Gemini)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

THRESHOLDS_FILE = Path(__file__).parent / "thresholds.json"


def _load_thresholds() -> dict:
    return json.loads(THRESHOLDS_FILE.read_text(encoding="utf-8"))


def _check(name: str, value: float, floor: float, failures: list[str]) -> None:
    """Confronta una metrica con la sua soglia; stampa l'esito; accumula i fallimenti.

    Effetto collaterale voluto: stampa una riga leggibile per ogni metrica, cosi'
    il log della CI dice a colpo d'occhio cosa e' passato e cosa no.
    """
    ok = value >= floor
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {name:20} = {value:.3f}   (soglia >= {floor:.3f})")
    if not ok:
        failures.append(f"{name}={value:.3f} < {floor:.3f}")


def run(with_judge: bool = False) -> int:
    thresholds = _load_thresholds()
    failures: list[str] = []

    print("Quality gate — execution accuracy")
    from eval.eval import evaluate

    report = evaluate()
    _check(
        "execution_accuracy",
        report["accuracy"],
        thresholds["execution_accuracy"],
        failures,
    )
    print(f"  (dettaglio: {report['passed']}/{report['total']} casi corretti)")

    # Elenca i casi NON corretti col motivo: serve a capire se un fallimento e'
    # colpa del sistema (SQL sbagliato) o rumore del free tier (429/503). Senza
    # questo, il gate dice solo "0.733" e si e' costretti a indovinare.
    failed = [r for r in report["results"] if not r.get("ok")]
    if failed:
        print("  casi falliti:")
        for r in failed:
            status = r.get("status", "?")
            if status == "executed":
                motivo = f"ottenuto={r.get('got')} atteso={r.get('expected')}"
            elif status == "guardrail_rejected":
                motivo = f"guardrail: {r.get('reason')}"
            elif status == "error":
                motivo = f"errore: {r.get('error')}"
            else:
                motivo = status
            print(f"    - {r['id']:24} [{status}] {motivo}")

    if with_judge:
        print("\nQuality gate — LLM-as-judge (qualita')")
        judge_scores = _run_judge_over_dataset()
        judge_floors = thresholds.get("judge", {})
        for criterion, floor in judge_floors.items():
            _check(
                f"judge.{criterion}",
                judge_scores.get(criterion, 0.0),
                floor,
                failures,
            )

    print()
    if failures:
        print("QUALITY GATE: FALLITO ->", "; ".join(failures))
        return 1
    print("QUALITY GATE: SUPERATO. Tutte le soglie rispettate.")
    return 0


def _run_judge_over_dataset() -> dict[str, float]:
    """Gira il judge su ogni caso del dataset e ritorna la MEDIA per criterio.

    Separato da evaluate() perche' il judge e' opt-in (costa chiamate Gemini). Per
    ogni caso: genera SQL, esegue, formatta la risposta (mascherata) e la fa
    giudicare. La media per criterio e' cio' che confrontiamo con le soglie.

    Come eval.py: continua sul caso dopo un errore, non crasha il gate.
    """
    from app.answer import format_answer
    from app.db.client import tenant_session
    from app.guardrail import check_sql
    from app.llm.gemini_client import generate_sql
    from app.llm.judge import CRITERIA, judge
    from app.tools.mask_pii import mask_pii_in_rows

    dataset = json.loads((Path(__file__).parent / "dataset.json").read_text(encoding="utf-8"))
    cases = dataset["cases"]

    totals = {c: 0.0 for c in CRITERIA}
    counted = 0
    for c in cases:
        try:
            sql = generate_sql(c["question"], c["tenant_id"])
            if not check_sql(sql).approved:
                # Guardrail-reject: nessuna risposta -> non conta nella media qualita'
                # (la execution accuracy lo ha gia' penalizzato come non-corretto).
                continue
            with tenant_session(c["tenant_id"]) as conn:
                rows = [list(r) for r in conn.execute(sql).fetchall()]
            answer = format_answer(c["question"], mask_pii_in_rows(rows))
            scores = judge(c["question"], sql, rows, answer)
            for crit in CRITERIA:
                totals[crit] += scores.get(crit)
            counted += 1
        except Exception as e:  # noqa: BLE001 — un caso rotto non ferma il gate
            print(f"  [warn] judge saltato per {c['id']}: {e}")

    if counted == 0:
        return {c: 0.0 for c in CRITERIA}
    return {c: totals[c] / counted for c in CRITERIA}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--judge", action="store_true",
        help="controlla anche le soglie di qualita' LLM-judge (costa chiamate Gemini)",
    )
    args = parser.parse_args()
    sys.exit(run(with_judge=args.judge))
