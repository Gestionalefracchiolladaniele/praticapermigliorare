# BizQuery — Copilot BI agentico (palestra AI Engineer)

Piano completo e visione a regime in [PROJECT.md](PROJECT.md). Costruito a livelli
incrementali. **Tutto il codice applicativo dei 3 livelli è scritto e gira dal
vivo in Docker** (Gemini + Postgres reali). Observability con **Langfuse** attiva
(tracing + evaluation offline su dataset). Restano CI/CD e il deploy AWS.

Un utente business fa una domanda in italiano sui dati aziendali; un agente
(LangGraph) la traduce in SQL, la valida (guardrail + RLS multi-tenant), la
esegue, e risponde — con human-in-the-loop sulle query rischiose, PII mascherate,
e ogni run loggata per migliorare i few-shot nel tempo (data flywheel).

## Stato — 47 test verdi, tutto verificato dal vivo (2026-07-07)

**Livello 1 (v0)** — 🟢 FATTO dal vivo:

| # | Step | Stato |
|---|------|-------|
| 1 | Schema SQL (RLS) + seed | ✅ 30 customers, 100 orders, 2 tenant |
| 2 | FastAPI + Gemini (`POST /ask` → SQL) | ✅ gira dal vivo |
| 3 | Guardrail hard-coded (read-only, anti-injection, tenant) | ✅ |
| 4 | Esecuzione contro DB reale + risposta NL | ✅ |
| 5 | Evaluation (15 casi, execution accuracy) | ✅ gira |
| 6 | Docker (app + Postgres 16) | ✅ builda e gira |
| 7 | Deploy AWS free tier | ✅ note in `DEPLOY_AWS.md` (non ancora eseguito) |
| + | Interfaccia web (casella domanda → risposta) | ✅ `GET /` |

**Livello 2 (grafo agenti)** — 🟢 grafo verificato dal vivo:
- ✅ Model router (Flash/Pro deterministico) — `app/llm/router.py`
- ✅ Grafo LangGraph con **retry loop** contro Postgres reale — `app/graph/`
- ✅ Reviewer LLM (Gemini Flash valuta il risultato) + fallback deterministico
- ✅ Endpoint `POST /ask-graph` (stesso lavoro di `/ask` ma via grafo)
- ✅ **Langfuse tracing** (ogni run = trace, ogni nodo = span) — `app/observability/`
- ⬜ CI/CD

**Livello 3 (guardrail avanzati, MCP, flywheel)** — 🟢 code-complete:
- ✅ Tool `run_query` / `mask_pii` / `send_notification` + server MCP
- ✅ **Human-in-the-loop**: `SELECT *` rischioso → grafo sospeso (`interrupt`) →
  `POST /approve` riprende (checkpointer LangGraph)
- ✅ **PII masking nel flusso**: email offuscate in uscita (`f***@example.com`)
- ✅ **Data flywheel**: `query_logs` (RLS) + logging di ogni run + few-shot dalle
  run riuscite — `app/flywheel.py`
- ✅ SQL avanzato nell'eval (group by, avg, count distinct, sum)

Modello: `gemini-2.5-flash-lite` (free tier, ~20 richieste/giorno per progetto).

## Avvio (Docker)

```bash
# 1. .env con la tua GEMINI_API_KEY (da https://aistudio.google.com/apikey)
cp .env.example .env    # poi valorizza GEMINI_API_KEY

# 2. avvia db + app
docker compose up -d --build

# 3. popola i dati (una volta)
docker compose run --rm app python -m app.db.seed

# 4. usa l'app
#    - interfaccia web:  http://localhost:8000/
#    - Swagger:          http://localhost:8000/docs
#    - agente singolo:   POST /ask        {"tenant_id":1,"question":"..."}
#    - grafo LangGraph:  POST /ask-graph  {"tenant_id":1,"question":"..."}
#    - approva sospesa:  POST /approve    {"thread_id":"...","decision":"approve"}
```

Nota: lo `schema.sql` (tabelle + RLS + ruolo app + `query_logs`) è applicato
automaticamente al primo boot del container Postgres. Il seed va lanciato a mano
(è Python). Se cambi lo schema: `docker compose down -v` per ricreare il DB.

## Girare i test

```bash
# tutti i test (mockati + live) — tests/ va montato: non è nell'immagine
docker compose run --rm -v "$PWD/tests:/app/tests:ro" app \
  python -m pytest tests/ -p no:cacheprovider -q
```

I test che richiedono il DB (`test_rls_isolation`, `test_graph_live`,
`test_flywheel`) si skippano senza `DATABASE_URL`; girano verdi col DB su.

## Evaluation

**Locale** (senza Langfuse, output JSON):

```bash
docker compose run --rm -v "$PWD/eval/results:/app/eval/results" app \
  python -m eval.eval
```

Esegue i 15 casi di `eval/dataset.json`, misura l'execution accuracy, salva un
JSON in `eval/results/`. (I fallimenti tipici sono i 429/503 del free tier Gemini,
non errori di logica.)

**Su Langfuse** (evaluation offline: dataset versionato + dataset run + score
navigabili nella UI):

```bash
# 1. carica il dataset su Langfuse (una volta, o quando cambia; non chiama Gemini)
docker compose exec -T app python -m eval.langfuse_dataset

# 2. gira l'experiment (5 casi default; --all per 15; --no-cache per ignorare la cache SQL)
docker compose exec -T app python -m eval.eval_langfuse
```

Usa `dataset.run_experiment(task=, evaluators=)`: **task** = la pipeline reale,
**evaluator** = score `correct` 1/0. L'SQL generato è **cachato** in
`eval/results/sql_cache.json` così i rilanci non consumano il free tier Gemini.
Risultato in **Datasets → bizquery-eval → Runs** con link diretto a ogni trace.
Richiede le `LANGFUSE_*` nel `.env` (senza chiavi, si disattiva pulito).

## Struttura

```
app/
  main.py              # FastAPI: GET / (UI), POST /ask, /ask-graph, /approve, /health
  guardrail.py         # regole deterministiche: read-only, anti-injection, tenant,
                       #   + verdetto needs_human (SELECT * senza LIMIT → human review)
  answer.py            # formatta il risultato in linguaggio naturale (IT)
  flywheel.py          # [L3] log_run + successful_examples (data flywheel)
  db/
    schema.sql         # tabelle business + query_logs, RLS multi-tenant
    seed.py            # dati finti riproducibili (seed=42)
    client.py          # sessione DB con SET LOCAL app.tenant_id (RLS)
  llm/
    gemini_client.py   # generate_sql (con few-shot dal flywheel) + review_answer (reviewer LLM)
    router.py          # [L2] Flash vs Pro deterministico
  graph/               # [L2] grafo LangGraph
    state.py           #   AgentState (Pydantic)
    nodes.py           #   nodi: planner→router→sql→guardrail→[human_review]→db→reviewer→answer→log
    build_graph.py     #   assemblaggio + retry loop + checkpointer (human-in-the-loop)
  tools/               # [L3] tool riutilizzabili (grafo + MCP)
    run_query.py       #   esegue SQL in RLS (ri-valida col guardrail; bypass needs_human solo se umano-approvato)
    mask_pii.py        #   maschera email (PII)
    send_notification.py  # stub notifica
  mcp_server/
    server.py          # [L3] espone i tool come server MCP
  observability/
    langfuse_setup.py  # [L2] client Langfuse globale + callback handler (autodisattivo)
eval/
  dataset.json         # 15 casi domanda→numero (attesi dal seed deterministico)
  eval.py              # execution accuracy locale, output JSON in eval/results/
  langfuse_dataset.py  # upload dataset.json → Dataset Langfuse (idempotente)
  eval_langfuse.py     # experiment su Langfuse (run_experiment: task + evaluator, cache SQL)
tests/                 # v0 + router + grafo + tool + flywheel (mock + live)
demo_graph.py          # [L2] demo visiva del flusso del grafo, no DB/API (python demo_graph.py)
Dockerfile             # immagine app (non-root)
docker-compose.yml     # app + Postgres 16
DEPLOY_AWS.md          # note deploy free tier (EC2 t3.micro)
LANGGRAPH_NOTES.md     # convenzioni LangGraph (verificate su langgraph 1.2.7)
```

## Cosa resta (non più codice applicativo core)

- **Langfuse** — ✅ tracing + evaluation offline fatti. Restano le capacità
  avanzate (prompt management, feedback online, LLM-as-judge, dashboards, A/B):
  percorso di studio in [LEARN_LANGFUSE.md](LEARN_LANGFUSE.md).
- **CI/CD** — GitHub Actions (build + test + deploy).
- **Deploy AWS** — EC2 t3.micro free tier (richiede account AWS).
- **Sicurezza** — rigenerare le API key Gemini usate in sviluppo.
```
