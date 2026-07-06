# BizQuery — Agentic Business Intelligence Copilot

Progetto-palestra per passare da "uso le API" a **AI Engineer di produzione**,
costruito **a livelli incrementali** allineati a `ROADMAP-AI-ENGINEER.md`
(F:\sicurezzacapire\ROADMAP-AI-ENGINEER.md — fonte di verità).

**Regola guida**: si finisce il Livello 1 (🔴, assolutamente necessario) prima di
toccare il Livello 2 (🟡), e il 2 prima del 3 (🟢). Stessa visione finale (vedi
"Visione finale" sotto), ma costruita a strati, ogni strato verificabile da solo
prima di aggiungere il successivo. Niente RAG (già padroneggiato in wha-gmail),
tutto su Gemini free tier (zero costi).

**Metodo per-livello, deciso pezzo per pezzo (2026-07-05)**: si scrive sempre
tutto **noi, da zero, riga per riga** — mai clonare o copiare un repo esterno.
Per i pezzi puramente meccanici (Python/FastAPI, SQL/RLS, Docker, AWS) questo
è naturale. Per i framework con convenzioni precise (LangGraph, MCP) scriviamo
comunque da zero, ma **guardando prima come la documentazione ufficiale /
esempi standard strutturano il pattern** (es. come si definisce lo stato di un
grafo, come funziona `interrupt` per l'human-in-the-loop) — così il codice che
scriviamo somiglia a un pattern riconoscibile da un senior, non a un'invenzione
isolata. Non è "copiare un repo": è "scrivere da zero sapendo qual è la
convenzione giusta invece di indovinarla".

**Cosa si fa in ciascun modo, per step** (aggiornare mano a mano):
- 🔨 **Da zero, senza guardare nulla**: schema SQL + RLS, seed data, FastAPI
  scaffold, Gemini client, guardrail hard-coded, evaluation script, Dockerfile,
  deploy AWS.
- 📖 **Da zero, ma con occhiata a convenzioni standard prima di scrivere**:
  LangGraph (stato, nodi, conditional edge, interrupt), MCP (struttura server),
  Langfuse (istrumentazione tracing) — quando ci si arriva (Livello 2/3).

**Come lavoriamo, per ogni pezzo di codice**: spiegazione essenziale (perché
questa scelta, cosa si romperebbe senza) subito dopo o durante la scrittura —
non discorsiva, solo il necessario per capire la decisione.

---

## Visione finale (dove arriviamo, non da costruire subito)

Un utente business fa domande in linguaggio naturale sui dati aziendali
("quanti clienti abbiamo perso questo mese in Italia?"). Un team di agenti
orchestrato con stato (LangGraph) traduce la domanda in query SQL reali,
le esegue in sicurezza (RLS + guardrail + human-in-the-loop), valuta la
qualità della risposta, e la restituisce — con ogni passaggio tracciato
(Langfuse), misurato (evaluation harness) e migliorato nel tempo (data flywheel).
Gira in Docker, un pezzo su AWS.

Il dettaglio completo di schema dati, contratti agenti, grafo, regole guardrail
ecc. è in fondo a questo file ("Riferimento completo — visione a regime").
Quella sezione descrive il sistema **a Livello 3 completo**: non tutto va
costruito subito, si scala man mano seguendo i livelli qui sotto.

---

## LIVELLO 1 — v0, ASSOLUTAMENTE NECESSARIO (costruire ORA, da zero)

> Corrisponde a 🔴 nella roadmap: Python+FastAPI, Docker, evaluation base, AWS.
> Niente LangGraph, niente multi-agente, niente MCP, niente Langfuse ancora.

**Cos'è v0**: un solo agente (no grafo) che riceve una domanda, chiama Gemini
per generare SQL, esegue la query su Postgres (con RLS multi-tenant), applica
un guardrail minimo hard-coded (blocca DELETE/DROP/UPDATE, blocca query senza
tenant_id), e ritorna la risposta. Poi: un evaluation script che misura se
funziona su un set fisso di domande. Poi: containerizzato in Docker. Poi:
deployato su un servizio AWS free tier.

**Schema dati v0** (sottoinsieme minimo, vedi versione estesa in fondo):
- `tenants` (id, name)
- `customers` (id, tenant_id, name, email [PII], country)
- `orders` (id, tenant_id, customer_id, total_amount, status, created_at)
- RLS attiva su `customers` e `orders` da subito (`tenant_id = current_setting('app.tenant_id')`)
  — è meccanica di base (Postgres), non "Livello 2", va imparata bene qui.

**Step di build v0** (ognuno verificabile prima di passare al successivo).
Segnato per ciascuno se è **scrivibile subito in codice senza Docker** (🟢,
il codice si scrive e in parte si testa già) o se **richiede Docker in piedi**
per essere eseguito/verificato davvero (🔒, bloccato finché Docker non è pronto).

1. 🟢 **Schema + seed**: `schema.sql` con RLS, `seed.py` con dati random (2 tenant,
   ~30 customers, ~100 orders). Il codice si scrive subito; l'esecuzione contro
   un Postgres vero richiede Docker (step 1 nasce scrivibile, verifica bloccata
   fino a Docker pronto).
2. 🟢 **FastAPI + Gemini client**: endpoint `POST /ask` che prende `{tenant_id, question}`,
   chiama Gemini Flash con lo schema in prompt, ottiene SQL. Scrivibile e
   testabile subito: la chiamata a Gemini non dipende da Postgres, si può
   verificare che l'SQL generato sia sensato anche senza eseguirlo davvero.
3. 🟢 **Guardrail hard-coded** (funzione, non agente): regex/parsing che blocca
   DELETE/DROP/UPDATE/INSERT/ALTER/TRUNCATE e query senza `tenant_id` nel WHERE.
   Puro Python, zero dipendenze esterne, scrivibile e testabile subito con
   unit test semplici (stringhe SQL finte in input).
4. 🔒 **Esecuzione + risposta**: esegue la query approvata *contro il DB vero*
   e formatta il risultato in linguaggio naturale. Il codice si scrive prima,
   ma la verifica end-to-end richiede Postgres in piedi → Docker.
5. 🔒 **Evaluation base**: dataset di 15-20 domande con risultato atteso
   (`eval/dataset.json`), script `eval.py` che gira le domande e confronta
   risultato numerico. Lo script si scrive prima, ma girarlo davvero richiede
   il DB popolato (step 4) → Docker.
6. 🔒 **Docker**: `Dockerfile` + `docker-compose.yml` (app + Postgres locale).
   Questo step stesso richiede Docker Desktop installato — è il momento in
   cui il blocco si scioglie per tutti gli step precedenti.
7. 🔒 **AWS free tier**: deploy dell'app containerizzata. Richiede lo step 6
   già fatto (l'app deve già girare in un container prima di poterla deployare).

**Quindi, in pratica**: possiamo scrivere in codice, uno dietro l'altro, GIÀ
OGGI senza aspettare Docker: **step 1 (schema/seed), step 2 (FastAPI+Gemini),
step 3 (guardrail)**. Il primo momento in cui siamo bloccati per davvero è lo
step 4 (serve un Postgres reale per eseguire ed eseguire la query) — a quel
punto ci serve Docker installato.

**Criterio "v0 FATTO"**: hai un endpoint HTTP, in Docker, deployato (almeno in
parte) su AWS, che risponde a domande in NL su dati reali con guardrail anti-injection
di base, e uno script di evaluation che dà un punteggio numerico misurabile.
Nessun LangGraph ancora — è normale e voluto.

---

## LIVELLO 2 — v1, IL SALTO A "SENIOR VERO" (dopo v0, scritto da noi da zero)

> Corrisponde a 🟡 nella roadmap: Langfuse, LangGraph/agenti, CI/CD, message queue.
> Scriviamo il grafo noi, da zero — prima di scrivere guardiamo come la
> documentazione ufficiale LangGraph struttura stato/nodi/conditional edge/interrupt,
> per non reinventare male le convenzioni. Nessun repo clonato o copiato.

Cosa si aggiunge a v0, senza riscriverlo da zero:
- **LangGraph**: trasformare l'agente singolo in un grafo con più nodi
  (planner → sql_executor → reviewer, con retry loop). Il dettaglio completo
  del grafo è nella sezione "Riferimento completo" in fondo.
- **Observability (Langfuse)**: ogni run diventa una trace, ogni nodo uno span,
  con costi/latenza/modello usato.
- **Model routing**: Flash vs Pro in base alla complessità del task (già gratis
  con Gemini free tier).
- **CI/CD**: pipeline che testa + deploya automaticamente ad ogni push.

**Criterio "v1 FATTO"**: il grafo LangGraph gestisce almeno un caso di retry
reale (query sbagliata → reviewer la rifiuta → secondo tentativo corretto),
e Langfuse mostra le trace con costo/latenza per nodo.

---

## LIVELLO 3 — v2, VALORE AGGIUNTO (dopo v1)

> Corrisponde a 🟢 nella roadmap: guardrail avanzati, MCP, SQL avanzato,
> reranking/agent evaluation, ottimizzazioni.

Cosa si aggiunge a v1:
- **Guardrail avanzati + human-in-the-loop**: cost-guardian agent, interrupt/resume
  per query rischiose, non solo regole statiche.
- **MCP**: i tool (`run_query`, `mask_pii`, `send_notification`) esposti come
  server MCP riutilizzabile.
- **PII masking dedicato**: tool separato, non solo esclusione a monte.
- **Data flywheel**: usare `query_logs` per migliorare i few-shot del planner
  nel tempo, misurando il delta di score sull'evaluation harness.
- **SQL avanzato**: query più complesse (join multipli, aggregazioni, window
  functions) nel dataset di eval.

**Criterio "v2 FATTO"**: esiste almeno un ciclo dimostrabile di data flywheel
(prima/dopo score di evaluation migliorato aggiungendo few-shot dai log reali),
e i tool girano anche come server MCP indipendente.

---

## Stato avanzamento

- 🟡 **Livello 1 (v0)** — in corso. Tutto il codice v0 scritto e testato offline
  (**21 test verdi + 4 skip** che attendono il DB). Manca solo l'esecuzione live
  (serve un Postgres reale).
  - ✅ Step 1: `app/db/schema.sql` (3 tabelle + RLS multi-tenant), `app/db/seed.py`
    (seed=42 riproducibile). Verifica contro DB reale attende Postgres.
  - ✅ Step 2: `app/main.py` (`POST /ask`), `app/llm/gemini_client.py`. Catena
    domanda→SQL→guardrail→risposta testata con Gemini mockato (`tests/test_ask_endpoint.py`, 3 test).
  - ✅ Step 3: `app/guardrail.py` + `tests/test_guardrail.py` (12 test: read-only,
    anti-injection, filtro tenant, falsi positivi).
  - ✅ Step 4 (codice pronto): esecuzione in `main.py` via `app/db/client.py`
    (`tenant_session` con SET LOCAL) + **formattazione risposta in NL**
    `app/answer.py` (`tests/test_answer.py`, 6 test). Esecuzione live attende Postgres.
  - ✅ Step 5 (scritto): `eval/dataset.json` (10 casi, valori attesi calcolati
    dal seed deterministico) + `eval/eval.py` (execution accuracy, output JSON).
  - ✅ Step 6 (scritto): `Dockerfile`, `docker-compose.yml` (app + Postgres 16,
    healthcheck, schema auto-applicato al boot). `docker compose config` valida.
  - ✅ Step 7 (scritto): `DEPLOY_AWS.md` (EC2 t3.micro + docker compose, free tier
    reale; scelta motivata vs ECS/RDS).
  - ✅ Test isolamento RLS: `tests/test_rls_isolation.py` (4 test, il più importante
    di v0: tenant 1 non vede i dati di tenant 2). Si skippa senza DB, gira col DB su.
  - Scaffold: `requirements.txt`, `.env.example`, `.gitignore`, `README.md`.
  - 📖 Prep Livello 2 (senza iniziarlo): `LANGGRAPH_NOTES.md` — convenzioni
    LangGraph verificate su doc ufficiale, mappate sul nostro grafo.
  - 🔒 **Prossimo blocco: un Postgres reale su localhost:5432** (via Docker una
    volta risolto lo spazio, oppure Postgres nativo). Poi: `docker compose up`
    → `seed` → `/ask` dal vivo → `python -m eval.eval` → i 4 test RLS diventano verdi.
- 🟡 **Livello 2 (v1)** — anticipati i pezzi costruibili/testabili senza DB live
  (nodi mockati). Da riverificare col DB reale quando v0 gira dal vivo.
  - ✅ Model router `app/llm/router.py` (Flash vs Pro deterministico su segnali di
    complessità) + `tests/test_router.py` (7 test).
  - ✅ Grafo LangGraph (langgraph 1.2.7): `app/graph/state.py` (AgentState Pydantic),
    `app/graph/nodes.py` (nodi che avvolgono le funzioni v0), `app/graph/build_graph.py`
    (planner→router→sql_executor→guardrail→db_executor→reviewer→answer + **retry loop**).
    `tests/test_graph.py` (4 test, retry loop dimostrato = criterio "v1 FATTO", mockato).
  - ✅ Demo visiva `demo_graph.py`: mostra il flusso nodo per nodo senza DB/API
    (router, retry, guardrail block). Gira con `python demo_graph.py`.
  - ⬜ Manca (richiede DB/servizi live): Langfuse (tracing), CI/CD, e la verifica
    del grafo end-to-end con Gemini e Postgres veri.
- 🟡 **Livello 3 (v2)** — anticipata la struttura dei tool come MCP.
  - ✅ Tool estratti: `app/tools/run_query.py` (ri-valida col guardrail + esegue in
    RLS), `app/tools/mask_pii.py` (maschera email, PII), `app/tools/send_notification.py`
    (stub locale). `tests/test_tools.py` (5 test).
  - ✅ Server MCP `app/mcp_server/server.py` (mcp 1.28.1, FastMCP): espone
    run_query/mask_email/send_notification. Verificato che registra i 3 tool.
  - ⬜ Manca: guardrail avanzati + human-in-the-loop (interrupt/resume), PII masking
    nel flusso, data flywheel, SQL avanzato nell'eval. E l'esecuzione MCP live (run_query
    richiede DB).

---

## Ambiente e setup operativo

> Da confermare/compilare prima di scrivere il primo file di codice (step 1 di v0).

- **Python**: 3.14.3 installato, ma raggiungibile solo come `py` (launcher
  Windows) in questo terminale Bash, non come `python` (alias Store attivo).
  Dentro un venv attivato `python` funzionerà normalmente — non è un problema
  per il progetto, va solo saputo per i comandi da terminale grezzi.
- **Docker Desktop**: CLI installata (docker 29.6.1) e distro WSL2 presente, ma
  il **daemon non risponde** (verificato 2026-07-06: `docker info` va in timeout).
  **Ostacolo reale scoperto il 2026-07-06: il disco C: è pieno (0–0.2 GB liberi)**,
  e lo storage Docker (`docker_data.vhdx`, ~1.1 GB) è ancora su C:. Va spostato su
  F: (464 GB liberi) prima di poter buildare. Il `docker-compose.yml` è scritto e
  `docker compose config` lo valida; manca solo un Postgres reale in ascolto.
- **Postgres per v0**: locale via Docker (deciso 2026-07-05). Alternativa emersa
  se lo spazio Docker resta bloccato: Postgres nativo su F:. Qualunque Postgres in
  ascolto su `localhost:5432` sblocca gli step 4-5.
- **Gemini**: modello `gemini-2.5-flash-lite` (deciso 2026-07-06), free tier.
  API key su Google AI Studio, salvata in `.env` (mai committata — `.gitignore`).
  ⚠️ La chiave attuale è comparsa nella chat di sviluppo: va rigenerata.
- **Gestione pacchetti Python**: `venv` + `pip` (coerente con quanto già usa
  l'utente in altri progetti Python, vedi `user-profile`).

---

## Riferimento completo — visione a regime (Livello 3, tutto insieme)

> Questa sezione descrive il sistema COMPLETO come sarà a fine Livello 3.
> Non è il piano di lavoro immediato (quello è nelle sezioni Livello 1/2/3 sopra) —
> è la mappa di destinazione per non perdere la visione d'insieme mentre si
> costruisce a strati.

### Schema dati completo (Supabase/Postgres)

E-commerce B2B finto, multi-tenant.

- `tenants` (id, name, plan)
- `customers` (id, tenant_id, name, email [PII], country, created_at, churned_at)
- `orders` (id, tenant_id, customer_id, total_amount, status, created_at)
- `order_items` (id, order_id, product_id, quantity, unit_price)
- `products` (id, tenant_id, name, category, price)
- `query_logs` (id, tenant_id, user_id, question, generated_sql, result_summary,
  agent_path, tokens_used, cost_estimate, latency_ms, was_flagged, human_approved,
  feedback_score, created_at) — alimenta evaluation + data flywheel

RLS su ogni tabella business. PII mascherata a livello applicativo (`mask_pii`
tool), non a livello RLS (RLS isola per tenant, il masking PII è un livello
diverso e va sopra, non al posto).

### Contratti agenti (stato condiviso LangGraph)

`AgentState` (Pydantic): `question`, `tenant_id`, `user_id`, `chat_history`,
`plan`, `sql_candidate`, `guardrail_verdict`, `query_result`, `review_verdict`,
`retry_count`, `final_answer`, `trace_id`.

1. **Memory agent** — recupera `chat_history` da `query_logs`. No LLM.
2. **Planner agent** — interpreta la domanda, produce `plan`, chiede chiarimento
   se ambigua. Gemini Flash.
3. **Model router** — funzione deterministica su complessità del `plan` → Flash o Pro.
4. **SQL executor agent** — genera `sql_candidate`. Gemini (tier da router).
5. **Security/guardrail agent** — regole deterministiche (vedi sotto), verdetto
   `approved`/`rejected`/`needs_human`.
6. **Cost-guardian agent** — blocca/avvisa oltre soglia token o righe scansionate.
7. **Human-in-the-loop** — `needs_human` sospende il grafo (LangGraph `interrupt`)
   fino ad approvazione esterna.
8. **Executor (DB)** — esegue la query con ruolo RLS-limited.
9. **Reviewer agent** — valida che il risultato risponda alla domanda, altrimenti
   `retry_needed` (max 2 retry). Gemini Flash.
10. **Answer/report agent** — genera `final_answer` in NL.
11. **Notifica** — tool `send_notification` (email/Slack).
12. **Log** — scrive `query_logs` con `agent_path` completo.

### Grafo LangGraph

```
memory → planner --(ambigua)--> [STOP: chiedi chiarimento]
                --(chiara)--> sql_executor → guardrail
guardrail --(rejected)--> [STOP: rifiuta con motivo]
guardrail --(needs_human)--> [interrupt: attesa approvazione] → db_executor
guardrail --(approved)--> cost_guardian
cost_guardian --(blocked)--> [STOP: budget esaurito]
cost_guardian --(approved)--> db_executor
db_executor → reviewer
reviewer --(retry_needed, retry_count<2)--> sql_executor
reviewer --(retry_needed, retry_count>=2)--> [STOP: fallimento, log per flywheel]
reviewer --(ok)--> answer_agent → notifica → log → END
```

### Regole guardrail (deterministiche, non LLM)

- `DELETE`/`DROP`/`UPDATE`/`INSERT`/`ALTER`/`TRUNCATE` → **rejected** sempre
  (agente read-only).
- `SELECT` senza `WHERE tenant_id = ...` esplicito → **rejected** (difesa
  aggiuntiva anche se RLS lo forzerebbe comunque).
- Query oltre N righe stimate (`EXPLAIN`) o senza `LIMIT` su tabelle grandi →
  **needs_human**.
- Query che seleziona colonne PII senza passare da `mask_pii` → **rejected**.

### Evaluation harness

Dataset fisso (~20-30 coppie domanda/risultato atteso), metriche: SQL execution
accuracy, guardrail precision/recall, LLM-as-judge (Gemini Pro) per la qualità
della risposta in NL. Script standalone `eval.py`, output JSON in `eval/results/`.

### Observability (Langfuse)

Ogni run = trace, ogni nodo = span, con token/costo/latenza/modello usato.
Dashboard: costo per tenant, latenza media per nodo, tasso retry, tasso rifiuti.

### Model routing (Gemini free tier)

Flash: planner, reviewer, report. Pro: SQL executor su task complessi (join
multipli/aggregazioni). Router = funzione deterministica su `plan.complexity`.
Da verificare in fase di build i rate limit esatti del free tier corrente.

### Struttura repo (a regime)

```
bizquery-agent-gym/
  PROJECT.md
  docker-compose.yml
  app/
    main.py
    graph/
      state.py
      nodes.py
      build_graph.py
    tools/
      run_query.py
      mask_pii.py
      send_notification.py
      estimate_cost.py
    mcp_server/
      server.py
    db/
      schema.sql
      seed.py
      client.py
    llm/
      gemini_client.py
      router.py
    observability/
      langfuse_setup.py
  eval/
    dataset.json
    eval.py
    results/
  tests/
  Dockerfile
  requirements.txt
  .env.example
```

### Cosa NON c'è (di proposito, a nessun livello)

- RAG / vector search — già padroneggiato altrove, non serve qui.
- Fine-tuning / ML pesante — escluso dalla traiettoria di carriera (deciso
  2026-07-04).
- Modelli a pagamento — tutto Gemini free tier.

### Stack completo

Python + FastAPI, LangGraph, Gemini API (free tier), Supabase/Postgres con RLS,
MCP, Langfuse, Docker, AWS free tier.
