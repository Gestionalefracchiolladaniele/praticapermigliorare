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

from app.observability.prompts import get_prompt

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

# Fallback hardcoded del prompt di sistema, usato se Langfuse è offline/non
# configurato (Capacità 3 — Prompt Management). NB: sintassi variabili Langfuse
# `{{var}}` (doppia graffa), NON str.format: lo stesso testo funziona sia caricato
# su Langfuse sia come fallback. Nome del prompt su Langfuse: "bizquery-sql-system".
_SYSTEM_PROMPT = """\
Sei un generatore di SQL PostgreSQL in sola lettura per una business intelligence.
Regole ASSOLUTE:
- Genera UNA sola query SELECT. Mai INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE/CREATE.
- Filtra SEMPRE per il tenant indicato: aggiungi `tenant_id = {{tenant_id}}` nel
  WHERE di ogni tabella business (customers, orders).
- Non selezionare la colonna email a meno che non sia strettamente richiesto (PII).
- Rispondi con la SOLA query SQL, senza spiegazioni, senza markdown, senza ```.

{{schema}}
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


def _few_shot_block(examples: list[tuple[str, str]]) -> str:
    """Formatta esempi (domanda, sql) riusciti come few-shot per il prompt.
    Vuoto se non ci sono esempi — così il prompt base resta invariato a freddo."""
    if not examples:
        return ""
    lines = ["\nEsempi di query corrette generate in passato (imitane lo stile):"]
    for q, sql in examples:
        lines.append(f"Domanda: {q}\nSQL: {sql}")
    return "\n".join(lines) + "\n"


def generate_sql(
    question: str,
    tenant_id: int,
    examples: list[tuple[str, str]] | None = None,
) -> str:
    """Domanda NL + tenant -> stringa SQL (non ancora validata dal guardrail).

    `examples`: few-shot (domanda, sql) da run passate riuscite (data flywheel).
    Se presenti, vengono aggiunti al system prompt per guidare la generazione
    verso lo stile che ha già funzionato. Opzionale: senza esempi il
    comportamento è identico a prima."""
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")
    # Prompt Management (Cap.3): recupera il prompt di sistema da Langfuse; se
    # offline ricade sul fallback hardcoded _SYSTEM_PROMPT, comportamento identico.
    resolved = get_prompt(
        "bizquery-sql-system",
        _SYSTEM_PROMPT,
        tenant_id=int(tenant_id),
        schema=_SCHEMA_DESC,
    )
    # Il few-shot del flywheel è dinamico (dipende dalle run passate) → resta fuori
    # dal prompt versionato e viene appeso dopo la compilazione.
    system = resolved.text + _few_shot_block(examples or [])
    _record_prompt_ref("sql", resolved.ref)

    resp = _client().models.generate_content(
        model=model,
        contents=question,
        config={"system_instruction": system, "temperature": 0.0},
    )
    return _clean_sql(resp.text or "")


# Registro dell'ultima versione di prompt usata, per chiave logica ("sql",
# "review"). Perche' cosi': la versione di prompt va LINKATA alla trace, ma la
# chiamata Gemini gira nel thread del nodo, FUORI dal contesto OTel dello span
# aperto dal CallbackHandler di LangGraph — quindi update_current_generation() qui
# e' un no-op (verificato: "No active span in current context"). Soluzione pulita:
# generate_sql/review_answer registrano il ref qui; il NODO del grafo (che ha il
# contesto trace attivo) lo legge subito dopo e lo mette nello stato e sui metadata
# della trace. Semplice, testabile, e non dipende dal contesto OTel del thread.
_LAST_PROMPT_REF: dict[str, str] = {}


def _record_prompt_ref(key: str, ref: str) -> None:
    """Registra la versione di prompt appena usata (letta poi dal nodo del grafo)."""
    _LAST_PROMPT_REF[key] = ref


def last_prompt_ref(key: str) -> str | None:
    """Ritorna l'ultimo `name@vN` usato per `key` ("sql" | "review"), o None."""
    return _LAST_PROMPT_REF.get(key)


# Fallback hardcoded del reviewer (nessuna variabile). Nome su Langfuse:
# "bizquery-reviewer".
_REVIEW_PROMPT = """\
Sei un revisore di risposte per una business intelligence. Ricevi una DOMANDA in
linguaggio naturale, l'SQL eseguito e il RISULTATO (righe). Valuta SOLO se il
risultato risponde davvero alla domanda.
Rispondi con una sola parola: OK se il risultato risponde alla domanda,
RETRY se non risponde (SQL sbagliato, colonne errate, risultato incoerente).
Nessuna spiegazione, solo OK oppure RETRY.
"""


def review_answer(question: str, sql: str, rows: list) -> str:
    """Reviewer LLM (Gemini Flash): 'ok' se il risultato risponde alla domanda,
    'retry_needed' altrimenti. Fallback prudente: se la chiamata fallisce o
    l'output è ambiguo, NON blocca il flusso — ritorna 'ok' se ci sono righe
    (comportamento deterministico precedente), così un errore del reviewer non
    manda tutto in retry loop inutile."""
    has_rows = bool(rows)
    try:
        model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")
        # Prompt Management (Cap.3): reviewer da Langfuse, fallback all'hardcoded.
        resolved = get_prompt("bizquery-reviewer", _REVIEW_PROMPT)
        _record_prompt_ref("review", resolved.ref)
        # Passiamo un estratto del risultato: bastano le prime righe per giudicare.
        preview = str(rows[:5]) if rows else "[]"
        contents = f"DOMANDA: {question}\nSQL: {sql}\nRISULTATO (prime righe): {preview}"
        resp = _client().models.generate_content(
            model=model,
            contents=contents,
            config={"system_instruction": resolved.text, "temperature": 0.0},
        )
        verdict = (resp.text or "").strip().upper()
        if verdict.startswith("OK"):
            return "ok"
        if verdict.startswith("RETRY"):
            return "retry_needed"
    except Exception:  # noqa: BLE001 — reviewer non deve rompere il flusso
        pass
    # Fallback deterministico (come prima): righe presenti => ok.
    return "ok" if has_rows else "retry_needed"
