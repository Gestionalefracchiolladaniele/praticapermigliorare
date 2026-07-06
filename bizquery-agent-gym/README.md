# BizQuery — Copilot BI agentico (palestra AI Engineer)

Piano completo e visione a regime in [PROJECT.md](PROJECT.md). Si costruisce a
livelli incrementali. **v0 (Livello 1) è code-complete**; pezzi di **Livello 2/3**
già anticipati dove testabili senza DB live.

## Stato

**Livello 1 (v0)** — step del piano:

| # | Step | Stato |
|---|------|-------|
| 1 | Schema SQL (RLS) + seed | ✅ scritto (verifica DB attende Postgres) |
| 2 | FastAPI + Gemini client (`POST /ask` → SQL) | ✅ scritto e testato (Gemini mockato) |
| 3 | Guardrail hard-coded + unit test | ✅ 12 test verdi |
| 4 | Esecuzione query contro DB reale + risposta NL | 🟡 codice pronto, attende Postgres |
| 5 | Evaluation base | ✅ scritto (`eval/`), esecuzione attende DB |
| 6 | Docker (app + Postgres) | ✅ `Dockerfile` + `docker-compose.yml` |
| 7 | Deploy AWS free tier | ✅ note in `DEPLOY_AWS.md` |

**Livello 2 (grafo agenti)** — anticipato, testato coi mock:
- ✅ Model router (Flash/Pro deterministico) — `app/llm/router.py`
- ✅ Grafo LangGraph con **retry loop** — `app/graph/` — vedi **demo sotto**
- ⬜ Langfuse, CI/CD, verifica end-to-end col DB reale

**Livello 3 (tool come MCP)** — anticipato:
- ✅ Tool `run_query` / `mask_pii` / `send_notification` + server MCP — `app/tools/`, `app/mcp_server/`
- ⬜ Human-in-the-loop (interrupt), data flywheel, SQL avanzato

**Test:** v0 21 verdi + 4 skip (RLS, attendono DB); L2/L3 16 verdi (router+grafo+tool).
Modello: `gemini-2.5-flash-lite` (free tier).

## Vedi il flusso agentico dal vivo (nessun DB/API richiesti)

```bash
./.venv/Scripts/python demo_graph.py
```
Mostra il grafo nodo per nodo su 4 scenari: domanda semplice, domanda complessa
(il router sceglie Pro), **retry loop** (primo tentativo vuoto → ritenta → ok),
e query pericolosa bloccata dal guardrail. Gemini e DB sono simulati.

> **Sblocco esecuzione reale:** serve un Postgres su `localhost:5432` (via Docker,
> ma il disco C: è pieno → spostare lo storage Docker su F:, vedi PROJECT.md).
> Poi: `docker compose up` → `seed` → `/ask` → `eval.py` → i test RLS diventano verdi.

## Struttura

```
app/
  main.py              # FastAPI: POST /ask → genera SQL → guardrail → esegue → risposta NL
  guardrail.py         # regole deterministiche read-only + anti-injection
  answer.py            # formatta il risultato in linguaggio naturale (IT)
  db/
    schema.sql         # 3 tabelle + RLS multi-tenant
    seed.py            # dati finti riproducibili (seed=42)
    client.py          # sessione DB read-only con SET LOCAL app.tenant_id
  llm/
    gemini_client.py   # domanda NL + schema → SQL (gemini-2.5-flash-lite)
    router.py          # [L2] Flash vs Pro deterministico
  graph/               # [L2] grafo LangGraph
    state.py           #   AgentState (Pydantic)
    nodes.py           #   nodi che avvolgono le funzioni v0
    build_graph.py     #   assemblaggio + retry loop
  tools/               # [L3] tool riutilizzabili
    run_query.py       #   esegue SQL in RLS (ri-valida col guardrail)
    mask_pii.py        #   maschera email (PII)
    send_notification.py  # stub notifica
  mcp_server/
    server.py          # [L3] espone i tool come server MCP
eval/
  dataset.json         # 10 casi domanda→numero (attesi dal seed deterministico)
  eval.py              # execution accuracy, output JSON in eval/results/
tests/                 # v0 + router + grafo + tool (mock); RLS skip senza DB
demo_graph.py          # [L2] demo visiva del flusso del grafo (no DB/API)
Dockerfile             # immagine app (non-root)
docker-compose.yml     # app + Postgres 16
DEPLOY_AWS.md          # note deploy free tier
LANGGRAPH_NOTES.md     # convenzioni LangGraph (verificate su langgraph 1.2.7)
```

## Girare i test (nessun Docker richiesto)

```bash
py -m venv .venv
./.venv/Scripts/python -m pip install -r requirements.txt
./.venv/Scripts/python -m pytest -q
```

## Provare l'endpoint con Gemini reale

1. Copia `.env.example` in `.env`, metti `GEMINI_API_KEY` (gratis su
   https://aistudio.google.com/apikey). Lascia `DATABASE_URL` vuota per ora.
2. Avvia: `./.venv/Scripts/python -m uvicorn app.main:app --reload`
3. `POST http://localhost:8000/ask` con `{"tenant_id": 1, "question": "quanti clienti abbiamo?"}`
   → ritorna l'SQL generato + verdetto guardrail (non eseguito: manca il DB).

## Prossimo blocco: Docker

Lo step 4 in poi richiede Postgres reale. Serve installare Docker Desktop, poi:
`docker-compose.yml` (app + Postgres), applicare `schema.sql`, girare `seed.py`,
e l'endpoint eseguirà davvero le query con RLS attiva.
