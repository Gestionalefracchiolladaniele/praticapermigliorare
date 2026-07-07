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
from fastapi.responses import HTMLResponse
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


# Interfaccia utente minima (opzione A): una pagina servita dalla stessa app,
# nessun framework frontend, nessuna dipendenza esterna. La textbox chiama /ask
# in JS e mostra risposta + SQL generato + verdetto guardrail. Per v0 basta e
# avanza; un vero frontend (Next) arriva quando l'agente e' completo.
_INDEX_HTML = """<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BizQuery</title>
<style>
  :root { color-scheme: light dark; }
  * { box-sizing: border-box; }
  body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
         max-width: 720px; margin: 0 auto; padding: 2rem 1rem; line-height: 1.5; }
  h1 { margin: 0 0 .25rem; font-size: 1.6rem; }
  .sub { color: #888; margin: 0 0 1.5rem; font-size: .9rem; }
  .card { border: 1px solid #8883; border-radius: 12px; padding: 1.25rem; }
  label { display: block; font-weight: 600; margin: .75rem 0 .35rem; font-size: .9rem; }
  input, select, button { font: inherit; padding: .6rem .75rem; border-radius: 8px;
         border: 1px solid #8886; width: 100%; background: transparent; color: inherit; }
  .row { display: flex; gap: .75rem; }
  .row > div:first-child { flex: 0 0 130px; }
  .row > div:last-child { flex: 1; }
  button { margin-top: 1rem; cursor: pointer; font-weight: 600;
           background: #2563eb; color: #fff; border: none; }
  button:disabled { opacity: .6; cursor: wait; }
  #out { margin-top: 1.25rem; }
  .answer { font-size: 1.15rem; font-weight: 600; padding: .9rem 1rem;
            border-radius: 10px; background: #2563eb18; }
  .meta { margin-top: .9rem; font-size: .85rem; color: #999; }
  code { background: #8882; padding: .15rem .4rem; border-radius: 6px;
         font-family: ui-monospace, Menlo, Consolas, monospace; }
  pre { background: #8881; padding: .75rem; border-radius: 8px; overflow-x: auto;
        font-size: .85rem; }
  .err { background: #ef444422; padding: .9rem 1rem; border-radius: 10px; }
  .badge-ok { color: #16a34a; } .badge-no { color: #ef4444; }
</style>
</head>
<body>
  <h1>BizQuery</h1>
  <p class="sub">Fai una domanda in italiano sui dati aziendali. Un agente la traduce in SQL, la valida e la esegue.</p>
  <div class="card">
    <div class="row">
      <div>
        <label for="tenant">Azienda</label>
        <select id="tenant">
          <option value="1">Tenant 1</option>
          <option value="2">Tenant 2</option>
        </select>
      </div>
      <div>
        <label for="q">Domanda</label>
        <input id="q" placeholder="Es. Quanti clienti abbiamo?" value="Quanti clienti abbiamo?">
      </div>
    </div>
    <button id="go">Chiedi</button>
    <div id="out"></div>
  </div>

<script>
const btn = document.getElementById('go');
const out = document.getElementById('out');
async function ask() {
  const question = document.getElementById('q').value.trim();
  const tenant_id = parseInt(document.getElementById('tenant').value, 10);
  if (!question) return;
  btn.disabled = true; btn.textContent = 'Sto pensando…'; out.innerHTML = '';
  try {
    const r = await fetch('/ask', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ tenant_id, question })
    });
    // La risposta di errore puo' NON essere JSON (es. 500 -> testo "Internal
    // Server Error"): leggo il testo grezzo e provo a interpretarlo, senza
    // far esplodere r.json().
    const raw = await r.text();
    let data;
    try { data = JSON.parse(raw); }
    catch { render_err('HTTP ' + r.status + ' — ' + raw.slice(0, 200)); return; }
    if (!r.ok) { render_err(data.detail || ('Errore HTTP ' + r.status)); return; }
    render(data);
  } catch (e) {
    render_err(String(e));
  } finally {
    btn.disabled = false; btn.textContent = 'Chiedi';
  }
}
function esc(s){ return String(s).replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }
function render(d) {
  const g = d.guardrail_approved
    ? '<span class="badge-ok">approvato</span>'
    : '<span class="badge-no">bloccato: ' + esc(d.guardrail_reason) + '</span>';
  let html = '';
  if (d.answer) html += '<div class="answer">' + esc(d.answer) + '</div>';
  else if (d.note) html += '<div class="answer">' + esc(d.note) + '</div>';
  html += '<div class="meta">Guardrail: ' + g +
          '<br>SQL generato:<pre>' + esc(d.generated_sql) + '</pre></div>';
  out.innerHTML = html;
}
function render_err(msg) {
  out.innerHTML = '<div class="err"><b>Errore.</b> ' + esc(msg) +
    '<br><small>Se dice quota/429: hai finito le richieste gratis di Gemini per oggi.</small></div>';
}
btn.addEventListener('click', ask);
document.getElementById('q').addEventListener('keydown', e => { if (e.key === 'Enter') ask(); });
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return _INDEX_HTML


# --- Livello 2: stesso /ask ma orchestrato dal grafo LangGraph ---------------
# /ask (sopra) e' l'agente singolo v0. /ask-graph fa lo STESSO lavoro passando
# per il grafo (planner -> router -> sql_executor -> guardrail -> db_executor ->
# reviewer -> answer, con retry loop). Serve a verificare il Livello 2 dal vivo:
# stessa risposta di /ask, ma si vede il percorso dei nodi e il modello scelto
# dal router. Import locale: il grafo tira langgraph, che non serve a /ask v0.

class GraphResponse(BaseModel):
    tenant_id: int
    question: str
    # "done" (risposta pronta), "needs_human" (sospesa, serve /approve),
    # "rejected" (bloccata dal guardrail).
    status: str = "done"
    thread_id: str | None = None        # per riprendere una run sospesa
    model: str | None = None            # scelto dal router (Flash vs Pro)
    generated_sql: str | None = None
    guardrail_verdict: str | None = None
    guardrail_reason: str | None = None
    review_verdict: str | None = None
    retry_count: int = 0
    final_answer: str | None = None
    error: str | None = None


class ApproveRequest(BaseModel):
    thread_id: str
    decision: str = "approve"   # "approve" | "reject"


def _graph_response(req_tenant: int, question: str, thread_id: str, result: dict,
                    interrupted) -> "GraphResponse":
    """Costruisce la risposta HTTP da uno stato del grafo. Se il grafo si è
    fermato su un interrupt (human_review), status=needs_human e si espone il
    thread_id per riprendere via /approve."""
    if interrupted:
        payload = interrupted.value if hasattr(interrupted, "value") else interrupted
        return GraphResponse(
            tenant_id=req_tenant, question=question, status="needs_human",
            thread_id=thread_id,
            generated_sql=payload.get("sql") if isinstance(payload, dict) else None,
            guardrail_verdict="needs_human",
            guardrail_reason=payload.get("reason") if isinstance(payload, dict) else None,
        )
    status = "rejected" if result.get("guardrail_verdict") == "rejected" else "done"
    return GraphResponse(
        tenant_id=req_tenant, question=question, status=status, thread_id=thread_id,
        model=result.get("model"),
        generated_sql=result.get("sql_candidate"),
        guardrail_verdict=result.get("guardrail_verdict"),
        guardrail_reason=result.get("guardrail_reason"),
        review_verdict=result.get("review_verdict"),
        retry_count=result.get("retry_count", 0),
        final_answer=result.get("final_answer"),
        error=result.get("error"),
    )


def _first_interrupt(result: dict):
    """LangGraph mette gli interrupt pendenti sotto la chiave '__interrupt__'."""
    ints = result.get("__interrupt__") if isinstance(result, dict) else None
    if ints:
        return ints[0]
    return None


@app.post("/ask-graph", response_model=GraphResponse)
def ask_graph(req: AskRequest) -> GraphResponse:
    import uuid
    from app.graph.build_graph import get_graph
    from app.graph.state import AgentState

    graph = get_graph()
    thread_id = str(uuid.uuid4())
    cfg = {"configurable": {"thread_id": thread_id}}
    result = graph.invoke(AgentState(question=req.question, tenant_id=req.tenant_id), cfg)
    return _graph_response(req.tenant_id, req.question, thread_id, result,
                           _first_interrupt(result))


@app.post("/approve", response_model=GraphResponse)
def approve(req: ApproveRequest) -> GraphResponse:
    """Riprende una run sospesa su human_review con la decisione umana."""
    from langgraph.types import Command
    from app.graph.build_graph import get_graph

    graph = get_graph()
    cfg = {"configurable": {"thread_id": req.thread_id}}
    # Command(resume=...) inietta la decisione come valore di ritorno di interrupt().
    result = graph.invoke(Command(resume=req.decision), cfg)
    # Recupera la domanda dallo stato persistito per la risposta.
    snap = graph.get_state(cfg)
    question = snap.values.get("question", "") if snap else ""
    tenant = snap.values.get("tenant_id", 0) if snap else 0
    return _graph_response(tenant, question, req.thread_id, result,
                           _first_interrupt(result))


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

    answer = format_answer(req.question, rows)

    # Data flywheel: logga anche le run dell'agente singolo v0 (non solo il grafo).
    from app.flywheel import log_run
    log_run(
        tenant_id=req.tenant_id, question=req.question, generated_sql=sql,
        guardrail_verdict="approved", review_verdict=None, retry_count=0,
        was_flagged=False, human_approved=None, success=bool(rows),
    )

    return AskResponse(
        tenant_id=req.tenant_id,
        question=req.question,
        generated_sql=sql,
        guardrail_approved=True,
        guardrail_reason="",
        executed=True,
        rows=rows,
        answer=answer,
    )
