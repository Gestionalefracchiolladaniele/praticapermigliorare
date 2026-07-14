"""Provider Python per promptfoo: espone il guardrail come "modello" da attaccare.

PERCHE' ESISTE
--------------
promptfoo è nato per attaccare LLM, ma il suo "provider" è generico: qualsiasi
cosa che, dato un input, ritorni un output. Qui il "modello sotto attacco" è il
nostro guardrail deterministico `check_sql`. Così il red-team di promptfoo colpisce
la DIFESA VERA (le regole che decidono approved/rejected) senza spendere una sola
chiamata Gemini — la domanda di sicurezza "il guardrail ferma questo SQL malevolo?"
non dipende da CHI ha generato l'SQL (Gemini via prompt-injection o l'attaccante
diretto): dipende solo dal guardrail. Testarlo direttamente è più rigoroso ed è
gratis, quindi gira in CI a ogni push.

CONTRATTO promptfoo (Python provider):
  call_api(prompt: str, options, context) -> {"output": <stringa/dict>}
Il `prompt` è l'SQL malevolo del test case. Ritorniamo il verdetto serializzato
come stringa, così le assert di promptfoo (contains/not-contains/regex) ci lavorano.
"""
from __future__ import annotations

import os
import sys

# Rende importabile il package `app` quando promptfoo lancia questo file dalla
# cartella security/ (il cwd di promptfoo non è garantito essere la root progetto).
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from app.guardrail import check_sql  # noqa: E402


def call_api(prompt, options=None, context=None):
    """prompt = l'SQL (malevolo o legittimo) da sottoporre al guardrail.

    Ritorna un output testuale con il verdetto in forma facilmente asseribile:
      VERDICT=<approved|rejected|needs_human> | reason=<...>
    così i test promptfoo possono asserire, es., che un SELECT con pg_read_file
    dia VERDICT=rejected.
    """
    sql = prompt if isinstance(prompt, str) else str(prompt)
    v = check_sql(sql)
    if v.approved:
        verdict = "approved"
    elif v.needs_human:
        verdict = "needs_human"
    else:
        verdict = "rejected"
    return {
        "output": f"VERDICT={verdict} | reason={v.reason}",
        # metadata utile per il report promptfoo (non usato dalle assert, ma comodo)
        "metadata": {"approved": v.approved, "needs_human": v.needs_human},
    }
