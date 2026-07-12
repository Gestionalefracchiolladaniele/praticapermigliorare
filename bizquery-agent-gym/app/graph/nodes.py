"""Nodi del grafo LangGraph (Livello 2).

Principio: ogni nodo AVVOLGE una funzione v0 già scritta e testata. LangGraph
aggiunge solo l'orchestrazione (stato, routing, retry) sopra logica che esiste.
Ecco perché il grafo non butta v0.

Testabilità senza DB/Gemini: i nodi chiamano funzioni importate a livello di
modulo (generate_sql, check_sql, run_query, ...). Nei test si monkeypatchano,
esattamente come già fatto per l'endpoint /ask in v0. Col DB vero (dopo) le
stesse funzioni girano davvero, senza riscrivere i nodi.

Convenzione LangGraph (langgraph 1.2.7): nodo = funzione (state) -> dict coi soli
campi da aggiornare.
"""
from __future__ import annotations

from langgraph.types import interrupt

from app.answer import format_answer
from app.guardrail import check_sql
from app.llm.gemini_client import generate_sql, last_prompt_ref, review_answer
from app.llm.router import route_model
from app.tools.mask_pii import mask_pii_in_rows
from app.flywheel import successful_examples
from app.graph.state import AgentState

MAX_RETRY = 2


def _tag_trace_prompt(field: str, ref: str | None) -> None:
    """Scrive la versione di prompt usata sui metadata della trace corrente.

    Chiamato DAI NODI: qui il contesto OTel della trace è attivo (il
    CallbackHandler ha aperto lo span mentre esegue il nodo), quindi
    update_current_trace funziona — a differenza di dentro generate_sql, dove
    non c'è span attivo. Best-effort: no-op se tracing spento o fuori contesto."""
    if not ref:
        return
    try:
        from app.observability.langfuse_setup import get_client

        client = get_client()
        if client is not None:
            client.update_current_trace(metadata={field: ref})
    except Exception:  # noqa: BLE001 — l'observability non deve rompere il grafo
        pass


def planner_node(state: AgentState) -> dict:
    """v1 minimale: il plan è la domanda stessa (nessun LLM planner ancora).
    A regime interpreta/disambigua; qui fa da passo esplicito per il router."""
    return {"plan": state.question}


def router_node(state: AgentState) -> dict:
    """Sceglie il modello (deterministico). Non è un nodo LLM."""
    decision = route_model(state.question, state.plan)
    return {"model": decision.model}


def sql_executor_node(state: AgentState) -> dict:
    """Genera l'SQL. Avvolge generate_sql (Gemini). Il retry ripassa di qui:
    incrementiamo retry_count qui così il loop è visibile nello stato.

    Data flywheel: passa al modello i few-shot dalle run passate riuscite per
    questo tenant. Al primo tentativo (retry_count==0) li usa; nei retry no —
    se un esempio somigliante ha portato all'SQL sbagliato, ripeterlo non aiuta,
    meglio lasciare rigenerare 'pulito'."""
    examples = successful_examples(state.tenant_id) if state.retry_count == 0 else []
    sql = generate_sql(state.question, state.tenant_id, examples=examples)
    # Cap.3: dopo la chiamata leggo quale versione di prompt e' stata usata e la
    # porto nello stato (compare nell'I/O dello span) + sui metadata della trace.
    ref = last_prompt_ref("sql")
    _tag_trace_prompt("prompt_ref_sql", ref)
    return {"sql_candidate": sql, "retry_count": state.retry_count + 1, "prompt_ref_sql": ref}


def guardrail_node(state: AgentState) -> dict:
    """Avvolge check_sql (deterministico). Livello 3: tre verdetti —
    approved / rejected / needs_human (query lecita ma rischiosa)."""
    v = check_sql(state.sql_candidate or "")
    if v.needs_human:
        verdict = "needs_human"
    elif v.approved:
        verdict = "approved"
    else:
        verdict = "rejected"
    return {"guardrail_verdict": verdict, "guardrail_reason": v.reason}


def human_review_node(state: AgentState) -> dict:
    """Human-in-the-loop (Livello 3). Sospende il grafo con interrupt() e aspetta
    una decisione esterna. Alla ripresa (Command(resume=...)) il valore tornato
    da interrupt() è la decisione umana: "approve" | "reject".

    Convenzione LangGraph: interrupt(payload) salva lo stato col checkpointer e
    ferma l'esecuzione; il payload è ciò che il client vede per decidere. Serve
    un checkpointer nel compile() perché lo stato sopravviva tra le due chiamate.
    """
    decision = interrupt({
        "reason": state.guardrail_reason,
        "sql": state.sql_candidate,
        "question": state.question,
    })
    approved = str(decision).strip().lower() in ("approve", "approved", "yes", "si", "true")
    if approved:
        return {"guardrail_verdict": "approved", "human_approved": True}
    return {
        "guardrail_verdict": "rejected",
        "human_approved": False,
        "guardrail_reason": "Rifiutata da revisione umana.",
    }


def db_executor_node(state: AgentState) -> dict:
    """Esegue la query approvata. Avvolge run_query (che usa tenant_session).
    Import locale: il DB serve solo qui, non deve rompere l'import del grafo."""
    from app.tools.run_query import run_query

    try:
        rows = run_query(
            state.sql_candidate or "", state.tenant_id,
            human_approved=bool(state.human_approved),
        )
        return {"query_result": rows}
    except Exception as e:  # noqa: BLE001
        return {"error": f"esecuzione fallita: {e}"}


def reviewer_node(state: AgentState) -> dict:
    """Reviewer LLM (Gemini Flash): valuta se il risultato risponde davvero alla
    domanda. review_answer ha un fallback deterministico (righe presenti => ok)
    se l'LLM non è disponibile, quindi il grafo funziona anche senza chiamata."""
    verdict = review_answer(
        state.question, state.sql_candidate or "", state.query_result or []
    )
    ref = last_prompt_ref("review")
    _tag_trace_prompt("prompt_ref_review", ref)
    return {"review_verdict": verdict, "prompt_ref_review": ref}


def answer_node(state: AgentState) -> dict:
    """Avvolge format_answer (risposta NL). Livello 3: prima di comporre la
    risposta, maschera le PII (email) nel risultato — il masking è un livello
    sopra la RLS (PROJECT.md), applicato in uscita, non a livello DB."""
    safe_rows = mask_pii_in_rows(state.query_result or [])
    return {"final_answer": format_answer(state.question, safe_rows)}


def log_node(state: AgentState) -> dict:
    """Data flywheel: registra la run in query_logs. success=True solo se il
    grafo ha prodotto una risposta (final_answer presente). Best-effort: log_run
    non solleva, quindi questo nodo non può far fallire la run. Non modifica lo
    stato (ritorna {})."""
    from app.flywheel import log_run

    log_run(
        tenant_id=state.tenant_id,
        question=state.question,
        generated_sql=state.sql_candidate,
        guardrail_verdict=state.guardrail_verdict,
        review_verdict=state.review_verdict,
        retry_count=state.retry_count,
        was_flagged=(state.human_approved is not None),
        human_approved=state.human_approved,
        success=bool(state.final_answer),
    )
    return {}
