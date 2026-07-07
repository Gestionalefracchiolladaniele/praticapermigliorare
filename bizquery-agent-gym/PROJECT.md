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

> **Aggiornamento 2026-07-07 — sessione "tutto dal vivo in Docker".** Docker
> sbloccato e l'intero stack gira davvero (Postgres 16 + app FastAPI in
> container). v0 verificato end-to-end dal vivo; L2 (grafo) e gran parte del
> codice L3 (human-in-the-loop, PII masking) scritti e verificati con Gemini +
> Postgres reali. **44 test verdi** nel container. Dettagli per livello sotto.

- 🟢 **Livello 1 (v0)** — **FATTO e verificato dal vivo (2026-07-07)**. L'app
  gira in Docker, il DB è popolato, `/ask` risponde su dati reali con guardrail.
  - ✅ Step 1: `app/db/schema.sql` (3 tabelle + RLS multi-tenant), `app/db/seed.py`.
    **Seed live: 30 customers, 100 orders, 2 tenant** (`docker compose run --rm app python -m app.db.seed`).
  - ✅ Step 2: `app/main.py` (`POST /ask`), `app/llm/gemini_client.py`. **Testato
    dal vivo**: domanda→Gemini→SQL→guardrail→esecuzione→risposta NL. Es. "Quanti
    clienti abbiamo?" → `SELECT count(id) FROM customers WHERE tenant_id = 1` → 15.
  - ✅ Step 3: `app/guardrail.py` + `tests/test_guardrail.py` (read-only,
    anti-injection, filtro tenant, falsi positivi). **Esteso a L3** (verdetto
    `needs_human`, vedi sotto).
  - ✅ Step 4: esecuzione via `app/db/client.py` (`tenant_session` SET LOCAL) +
    `app/answer.py`. **Gira dal vivo.**
  - ✅ Step 5: `eval/dataset.json` (10 casi) + `eval/eval.py`. **Girato dal vivo**:
    10/10 sui casi in cui Gemini rispondeva (i fallimenti erano solo 429/503 del
    free tier, non errori di logica). Fix: salvataggio risultati reso non-fatale
    in container (utente non-root) — `eval.py` non crasha più se non può scrivere.
  - ✅ Step 6: `Dockerfile` + `docker-compose.yml`. **Buildano e girano.** Fix:
    `pydantic 2.10.4 → 2.11.9` in `requirements.txt` (era ResolutionImpossible:
    `mcp==1.28.1` esige `pydantic>=2.11.0`; senza questo il build falliva).
  - ✅ Step 7 (scritto, non ancora eseguito): `DEPLOY_AWS.md` (EC2 t3.micro free tier).
  - ✅ Test isolamento RLS `tests/test_rls_isolation.py` (4 test): **tutti VERDI
    col DB reale** — tenant 1 non vede i dati di tenant 2.
  - ✅ **Interfaccia web (opzione A)**: pagina HTML+JS servita da FastAPI su `GET /`
    (in `app/main.py`, inline, zero dipendenze). Casella domanda + selettore tenant
    → mostra risposta, verdetto guardrail, SQL generato. Gira su `http://localhost:8000/`.
- 🟢 **Livello 2 (v1)** — **grafo VERIFICATO DAL VIVO (2026-07-07)**, non più
  solo mockato. Criterio "v1 FATTO" raggiunto col DB reale.
  - ✅ Model router `app/llm/router.py` + `tests/test_router.py`. Gira nel grafo.
  - ✅ Grafo LangGraph (langgraph 1.2.7): `state.py`, `nodes.py`, `build_graph.py`
    (planner→router→sql_executor→guardrail→db_executor→reviewer→answer + retry loop).
  - ✅ **Endpoint `POST /ask-graph`** (in `app/main.py`): esegue lo STESSO lavoro di
    `/ask` ma via grafo, ritornando modello scelto, verdetti, retry_count. Provabile
    da Swagger/UI. **Testato dal vivo**: attraversa i 7 nodi, risponde correttamente.
  - ✅ **Retry loop contro Postgres reale**: `tests/test_graph_live.py` — primo SQL
    dà 0 righe → reviewer chiede retry → secondo SQL ok. Criterio "v1 FATTO" verde
    col DB vero (non mockato).
  - ✅ `tests/test_graph.py` aggiornato (checkpointer → serve `thread_id` per run).
  - ⬜ Manca: **Langfuse** (tracing — free tier Hobby 50k/mese, deciso di usare il
    cloud gratuito), **CI/CD**, e **planner/reviewer con Gemini vero** (ora minimali:
    planner = passthrough, reviewer = deterministico su risultato non vuoto).
- 🟡 **Livello 3 (v2)** — **gran parte del codice SCRITTA e verificata dal vivo
  (2026-07-07)**. Manca solo il data flywheel.
  - ✅ Tool `app/tools/run_query.py` (ri-valida col guardrail + esegue in RLS),
    `mask_pii.py`, `send_notification.py` (stub) + `tests/test_tools.py`.
  - ✅ Server MCP `app/mcp_server/server.py` (mcp 1.28.1, FastMCP): espone
    run_query/mask_email/send_notification.
  - ✅ **Guardrail avanzato — verdetto `needs_human`**: `SELECT *` senza `LIMIT`
    (legge tutte le colonne incluse PII, tante righe) → non blocca, chiede umano.
    Regola stretta di proposito (aggregazioni e colonne esplicite passano).
  - ✅ **Human-in-the-loop reale** (LangGraph `interrupt` + `MemorySaver`
    checkpointer): nodo `human_review_node` sospende il grafo; `POST /approve`
    (con `thread_id` + `decision`) lo riprende. **Verificato dal vivo**: `SELECT *`
    → SOSPESO → `/approve` → eseguito. `run_query` accetta un bypass di `needs_human`
    SOLO se `human_approved=True`, mai le regole di sicurezza vere (DROP/injection/
    no-tenant restano invalicabili). `build_graph.get_graph()` = singleton così
    `/ask-graph` e `/approve` condividono il checkpointer.
  - ✅ **PII masking nel flusso**: `answer_node` applica `mask_pii_in_rows` prima di
    comporre la risposta → email offuscate (`f***@example.com`). **Verificato dal vivo.**
  - ⬜ Manca: **data flywheel** (tabella `query_logs` + logging di ogni run + usare i
    log per migliorare i few-shot del planner, misurando il delta di score
    sull'eval) e **SQL avanzato nel dataset di eval** (join/window functions).

---

## Ambiente e setup operativo

> Da confermare/compilare prima di scrivere il primo file di codice (step 1 di v0).

- **Python**: 3.14.3 installato, ma raggiungibile solo come `py` (launcher
  Windows) in questo terminale Bash, non come `python` (alias Store attivo).
  Dentro un venv attivato `python` funzionerà normalmente — non è un problema
  per il progetto, va solo saputo per i comandi da terminale grezzi.
- **Docker Desktop**: ✅ **FUNZIONA (2026-07-07)**. Il daemon era bloccato
  (500 Internal Server Error su ogni route); risolto **riavviando Docker Desktop**
  (kill processo + riavvio, pronto in ~15s). Lo spazio disco non era più un
  problema. `docker compose up -d --build` builda e avvia db+app; db diventa
  healthy (`pg_isready`), app in ascolto su :8000. **Nota Windows/PowerShell**:
  lo stderr di `docker compose` viene mostrato in rosso come "NativeCommandError"
  ma NON è un errore — è solo PowerShell che tratta lo stream. `tests/` NON è
  copiato nell'immagine (il Dockerfile copia solo `app` ed `eval`): per girare i
  test nel container montare la dir con `-v .../tests:/app/tests:ro`.
- **Postgres per v0**: ✅ locale via Docker, **gira** (`postgres:16` nel compose,
  volume `pgdata`, schema+RLS applicati al primo boot). In ascolto su `localhost:5432`.
- **Gemini**: modello `gemini-2.5-flash-lite`, free tier. **Limite reale: ~20
  richieste/giorno** per progetto Google (429 RESOURCE_EXHAUSTED oltre; 503 quando
  il modello è sovraccarico — entrambi transitori, non bug). Un `/ask` o `/ask-graph`
  = **1 chiamata**. ⚠️ **Le chiavi usate in questa chat (`AQ.Ab8...` e `AIzaSyB...`)
  sono comparse in chiaro: vanno RIGENERATE su aistudio.google.com/apikey.** La
  chiave va solo in `.env` (mai committata). Nota sicurezza: nella root
  `f:\sicurezzacapire` c'è un file `envchiaveesempio` con chiavi in chiaro —
  aggiunto al `.gitignore` root, ma va cancellato/rigenerato.
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
