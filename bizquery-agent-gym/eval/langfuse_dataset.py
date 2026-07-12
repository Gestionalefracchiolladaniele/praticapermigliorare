"""Upload di eval/dataset.json come DATASET Langfuse (Capacita' 2 — evaluation offline).

Cosa fa: legge i casi locali (`dataset.json`) e li crea su Langfuse come un
Dataset + i suoi Dataset item. E' uno script UNA-TANTUM: lo lanci quando il
dataset cambia. NON chiama Gemini (legge solo un JSON e lo spedisce) -> costo zero.

Perche' serve (Capacita' 2): l'evaluation offline in Langfuse ruota attorno a tre
oggetti — Dataset (la collezione), Dataset item (un caso: input + expected_output),
Dataset run (un giro di valutazione). Qui creiamo i primi due; la run la fa
`eval_langfuse.py` con `run_experiment`.

Tre scelte di design (le stesse che un senior spiega in colloquio):

1. IDEMPOTENZA. Ogni item viene creato con `id = caso["id"]` (es. "t1_num_customers").
   Langfuse fa UPSERT su quell'id: rilanciare lo script AGGIORNA gli item, non li
   duplica. Senza id espliciti, ogni run raddoppierebbe il dataset.

2. INPUT vs METADATA. `input` = cio' che la pipeline consuma davvero (la domanda).
   Il `tenant_id` (serve per eseguire con la RLS giusta) e la `tolerance` (serve
   all'evaluator per i confronti float) NON sono "la domanda": sono contorno ->
   vanno in `metadata`. `expected_output` = il valore atteso. Questa separazione
   e' esattamente lo schema che `run_experiment` si aspetta di ritrovare negli item.

3. ROBUSTEZZA. Se Langfuse non e' configurato (chiavi mancanti), lo script lo dice
   ed esce pulito — non crasha. Stesso principio di langfuse_setup.py / eval.py.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from app.observability.langfuse_setup import flush, get_client

DATASET_FILE = Path(__file__).parent / "dataset.json"
DATASET_NAME = "bizquery-eval"


def upload() -> int:
    client = get_client()
    if client is None:
        print("[stop] Langfuse non configurato (chiavi mancanti). Niente da caricare.")
        return 1

    data = json.loads(DATASET_FILE.read_text(encoding="utf-8"))
    cases = data["cases"]

    # 1) Il Dataset (la collezione). create_dataset e' idempotente sul nome: se
    #    esiste gia', Langfuse lo riusa invece di lamentarsi.
    client.create_dataset(
        name=DATASET_NAME,
        description="Domande BI in italiano su dati multi-tenant (seed=42). "
        "Ogni item: domanda -> valore scalare atteso. Fonte: eval/dataset.json.",
    )

    # 2) Gli item. Un item per caso, con id = caso["id"] (UPSERT -> no duplicati).
    for c in cases:
        client.create_dataset_item(
            dataset_name=DATASET_NAME,
            id=c["id"],
            input={"question": c["question"]},
            expected_output=c["expected"],
            metadata={
                "tenant_id": c["tenant_id"],
                # tolerance c'e' solo sui casi float; None sui count interi.
                "tolerance": c.get("tolerance"),
                "sql_kind": c.get("_sql_kind", "scalar"),
            },
        )

    # Langfuse bufferizza e invia in background: flush() forza l'invio ORA cosi'
    # gli item compaiono subito nella UI (utile in uno script una-tantum).
    flush()
    print(f"OK: caricati {len(cases)} item nel dataset '{DATASET_NAME}'.")
    print("Vai su Langfuse -> Datasets -> bizquery-eval per vederli.")
    return 0


if __name__ == "__main__":
    sys.exit(upload())
