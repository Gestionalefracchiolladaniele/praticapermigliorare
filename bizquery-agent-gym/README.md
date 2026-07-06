# BizQuery — v0 (Livello 1)

Copilot di business intelligence agentico. Piano completo e visione a regime in
[PROJECT.md](PROJECT.md). Questo README copre lo **stato attuale (v0, Livello 1)**.

## Stato

Step del piano v0 (vedi PROJECT.md):

| # | Step | Stato |
|---|------|-------|
| 1 | Schema SQL (RLS) + seed | ✅ scritto (verifica DB bloccata su Docker) |
| 2 | FastAPI + Gemini client (`POST /ask` → SQL) | ✅ scritto e testato (Gemini mockato) |
| 3 | Guardrail hard-coded + unit test | ✅ 12/12 test verdi |
| 4 | Esecuzione query contro DB reale + risposta NL | 🟡 codice pronto (`main.py`, `answer.py`), attende Postgres |
| 5 | Evaluation base | ✅ scritto (`eval/`), esecuzione attende DB |
| 6 | Docker (app + Postgres) | ✅ `Dockerfile` + `docker-compose.yml` (config valida) |
| 7 | Deploy AWS free tier | ✅ note in `DEPLOY_AWS.md` |

**21 test verdi + 4 skip** (i 4 skip = isolamento RLS, girano quando il DB è su).
Modello Gemini: `gemini-2.5-flash-lite` (free tier).

> **Sblocco:** serve un Postgres in ascolto su `localhost:5432`. Il piano è Docker
> (`docker compose up --build`), ma il disco C: è pieno e lo storage Docker va
> prima spostato su F: (vedi PROJECT.md, sezione Ambiente). Poi:
> `docker compose run --rm app python -m app.db.seed` → prova `/ask` → `python -m eval.eval`.

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
eval/
  dataset.json         # 10 casi domanda→numero (attesi dal seed deterministico)
  eval.py              # execution accuracy, output JSON in eval/results/
tests/                 # guardrail, endpoint, answer (mock), isolamento RLS (skip senza DB)
Dockerfile             # immagine app (non-root)
docker-compose.yml     # app + Postgres 16
DEPLOY_AWS.md          # note deploy free tier
LANGGRAPH_NOTES.md     # prep Livello 2: convenzioni LangGraph
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
