"""FastAPI — endpoint POST /ask (step 2 del piano v0).

Colla di v0: domanda NL -> Gemini genera SQL -> guardrail valida -> risposta.
L'ESECUZIONE della query contro il DB e' lo step 4 (bloccato su Docker): finche'
il DB non c'e', l'endpoint ritorna l'SQL generato + il verdetto del guardrail,
senza eseguire. Il ramo di esecuzione e' gia' predisposto (execute_query) ma
attivo solo se il DB e' raggiungibile.

Questo permette di verificare GIA' ORA, senza Docker, che la catena
domanda -> SQL -> validazione funzioni end-to-end (tranne l'esecuzione).
"""
from __future__ import annotations

import os

from fastapi import FastAPI
from pydantic import BaseModel

from app.answer import format_answer
from app.guardrail import check_sql
from app.llm.gemini_client import generate_sql

app = FastAPI(title="BizQuery v0")


class AskRequest(BaseModel):
    tenant_id: int
    question: str


class AskResponse(BaseModel):
    tenant_id: int
    question: str
    generated_sql: str
    guardrail_approved: bool
    guardrail_reason: str
    executed: bool
    rows: list | None = None
    answer: str | None = None   # risposta in linguaggio naturale (quando eseguita)
    note: str | None = None


def _db_available() -> bool:
    return bool(os.environ.get("DATABASE_URL"))


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest) -> AskResponse:
    sql = generate_sql(req.question, req.tenant_id)
    verdict = check_sql(sql)

    # Guardrail rifiuta -> ci si ferma qui, non si esegue nulla.
    if not verdict.approved:
        return AskResponse(
            tenant_id=req.tenant_id,
            question=req.question,
            generated_sql=sql,
            guardrail_approved=False,
            guardrail_reason=verdict.reason,
            executed=False,
            note="Query bloccata dal guardrail: non eseguita.",
        )

    # Guardrail approva. Se il DB c'e' (step 4, Docker) esegue; altrimenti ritorna
    # solo l'SQL validato. Import locale per non richiedere psycopg quando si vuole
    # solo generare+validare senza DB.
    if not _db_available():
        return AskResponse(
            tenant_id=req.tenant_id,
            question=req.question,
            generated_sql=sql,
            guardrail_approved=True,
            guardrail_reason="",
            executed=False,
            note="DATABASE_URL non impostata: SQL validato ma non eseguito "
                 "(esecuzione = step 4, richiede Docker).",
        )

    from app.db.client import tenant_session

    with tenant_session(req.tenant_id) as conn:
        cur = conn.execute(sql)
        rows = [list(r) for r in cur.fetchall()]

    return AskResponse(
        tenant_id=req.tenant_id,
        question=req.question,
        generated_sql=sql,
        guardrail_approved=True,
        guardrail_reason="",
        executed=True,
        rows=rows,
        answer=format_answer(req.question, rows),
    )
