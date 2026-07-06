"""Client Gemini per generare SQL dalla domanda in NL (step 2 del piano v0).

SDK ufficiale google-genai (free tier, gemini-2.0-flash). Meccanica pura, scritta
da zero.

Due scelte da capire:
  - Lo SCHEMA del DB viene messo nel prompt di sistema. Il modello non "conosce"
    le nostre tabelle: gliele descriviamo noi. Senza schema in prompt genererebbe
    SQL su tabelle inventate.
  - Chiediamo SOLO l'SQL, niente prosa, e ripuliamo eventuali ```sql fences. Il
    guardrail e l'executor a valle si aspettano una stringa SQL pulita, non un
    testo con spiegazioni intorno.

Il tenant_id NON viene passato al modello come qualcosa da "ricordare di
filtrare": glielo diciamo nel prompt per fargli mettere il WHERE giusto, ma la
sicurezza vera è guardrail (rifiuta se manca) + RLS (isola comunque). Non ci si
fida dell'LLM per l'isolamento.
"""
from __future__ import annotations

import os
import re

from dotenv import load_dotenv
from google import genai

load_dotenv()

# Descrizione schema data al modello. Volutamente compatta: è il "contratto" che
# il modello vede. Se lo schema.sql cambia, questa va aggiornata di pari passo.
_SCHEMA_DESC = """\
Tabelle disponibili (Postgres, e-commerce B2B multi-tenant):

tenants(id INT, name TEXT)
customers(id INT, tenant_id INT, name TEXT, email TEXT, country TEXT)
orders(id INT, tenant_id INT, customer_id INT, total_amount NUMERIC,
       status TEXT, created_at TIMESTAMPTZ)

status di orders puo' essere: 'pending', 'paid', 'cancelled', 'refunded'.
"""

_SYSTEM_PROMPT = """\
Sei un generatore di SQL PostgreSQL in sola lettura per una business intelligence.
Regole ASSOLUTE:
- Genera UNA sola query SELECT. Mai INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE/CREATE.
- Filtra SEMPRE per il tenant indicato: aggiungi `tenant_id = {tenant_id}` nel
  WHERE di ogni tabella business (customers, orders).
- Non selezionare la colonna email a meno che non sia strettamente richiesto (PII).
- Rispondi con la SOLA query SQL, senza spiegazioni, senza markdown, senza ```.

{schema}
"""


def _clean_sql(text: str) -> str:
    """Toglie eventuali code fence ```sql ... ``` e spazi, lascia l'SQL nudo."""
    text = text.strip()
    text = re.sub(r"^```(?:sql)?", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


def _client() -> genai.Client:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError(
            "GEMINI_API_KEY non impostata. Prendine una gratis su "
            "https://aistudio.google.com/apikey e mettila in .env."
        )
    return genai.Client(api_key=key)


def generate_sql(question: str, tenant_id: int) -> str:
    """Domanda NL + tenant -> stringa SQL (non ancora validata dal guardrail)."""
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")
    system = _SYSTEM_PROMPT.format(tenant_id=int(tenant_id), schema=_SCHEMA_DESC)

    resp = _client().models.generate_content(
        model=model,
        contents=question,
        config={"system_instruction": system, "temperature": 0.0},
    )
    return _clean_sql(resp.text or "")
