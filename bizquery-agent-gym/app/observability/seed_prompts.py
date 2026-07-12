"""Carica i prompt di BizQuery su Langfuse Prompt Management (Capacita' 3).

COSA FA: prende i due prompt di sistema che vivono come fallback hardcoded in
`app/llm/gemini_client.py` (`_SYSTEM_PROMPT`, `_REVIEW_PROMPT`) e li crea su
Langfuse come prompt versionati, con l'etichetta `production`.

PERCHE' SERVE: finche' i prompt non sono su Langfuse, `get_prompt` (in
`app/observability/prompts.py`) ricade sempre sul fallback e il versionamento non
esiste. Questo script "accende" il Prompt Management: da qui in poi il prompt vive
sul server, lo si modifica dalla UI senza toccare il codice, e ogni run resta
legata alla versione usata.

DA DOVE VENGONO I TESTI: li IMPORTIAMO da gemini_client.py, non li ricopiamo qui.
Cosi' c'e' una sola fonte di verita': se un giorno cambia il fallback, ricaricando
si ricarica lo stesso testo, senza rischio di divergenza tra i due posti.

IDEMPOTENZA (semantica Langfuse): ogni create_prompt con lo stesso `name` crea una
NUOVA VERSIONE e sposta l'etichetta `production` su di essa. Rilanciare non
"duplica": semplicemente production punta all'ultima versione caricata. E' voluto —
e' il modo Langfuse di gestire lo storico dei prompt.

ROBUSTEZZA: se Langfuse non e' configurato (chiavi mancanti), lo dice ed esce
pulito, come langfuse_dataset.py / eval.py.
"""
from __future__ import annotations

import sys

from app.llm.gemini_client import _REVIEW_PROMPT, _SYSTEM_PROMPT
from app.observability.langfuse_setup import flush, get_client

# (nome-su-Langfuse, testo, descrizione) — i nomi combaciano con quelli che
# get_prompt() chiede a runtime in gemini_client.py.
_PROMPTS = [
    (
        "bizquery-sql-system",
        _SYSTEM_PROMPT,
        "System prompt del generatore SQL. Variabili: {{tenant_id}}, {{schema}}.",
    ),
    (
        "bizquery-reviewer",
        _REVIEW_PROMPT,
        "System prompt del reviewer LLM (verdetto OK/RETRY). Nessuna variabile.",
    ),
]


def upload() -> int:
    client = get_client()
    if client is None:
        print("[stop] Langfuse non configurato (chiavi mancanti). Niente da caricare.")
        return 1

    for name, text, commit in _PROMPTS:
        client.create_prompt(
            name=name,
            prompt=text,
            type="text",
            # `production` e' l'etichetta che get_prompt(..., label="production")
            # cerca: caricare gia' etichettato rende il prompt subito "live".
            labels=["production"],
            commit_message=commit,
        )
        print(f"OK: prompt '{name}' caricato e etichettato 'production'.")

    # Come per il dataset: flush() forza l'invio ORA cosi' i prompt compaiono
    # subito nella UI (script una-tantum).
    flush()
    print("\nVai su Langfuse -> Prompts per vederli e modificarli dalla UI.")
    return 0


if __name__ == "__main__":
    sys.exit(upload())
