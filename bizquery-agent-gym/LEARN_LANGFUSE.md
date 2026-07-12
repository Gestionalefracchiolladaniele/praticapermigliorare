# LEARN_LANGFUSE — percorso per padroneggiare Langfuse (da zero ad avanzato)

> **STATO 2026-07-09: PERCORSO CHIUSO.** Fatte e verificate dal vivo le Cap.1-2-3
> (Tracing, Evaluation offline, Prompt Management). **Cap.4-8 non si fanno**:
> l'utente conosce già la UI (tour completo) e l'eventuale integrazione in codice
> la delega a Claude Code. Con 1+2+3 il CV su observability/evaluation/prompt
> management è coperto. Documento tenuto come riferimento storico. Prossimo lavoro
> del progetto: **CI/CD + deploy AWS**.

> File di studio personale. Scopo: sapere **davvero** usare Langfuse, non solo
> "averlo acceso". Ordine per **valore sugli annunci di lavoro** (vedi in fondo
> il match con le job offer reali in `../job offer riferimento/`).
>
> Ambiente: **Langfuse v4 (4.13.2)**, cloud EU free tier "Hobby", instrumentato
> sul grafo LangGraph di BizQuery. NB: v4 è su OpenTelemetry ed è **diverso** dai
> tutorial v2 in giro — l'API v3/v2 (es. `langfuse.trace()` a mano) è cambiata.
> Le capacità elencate qui sono state **verificate sul client reale** (metodi
> `create_dataset`, `create_score`, `run_experiment`, `create_prompt`, `api.sessions`,
> `api.annotation_queues`, `api.metrics`, `api.models`, `api.llm_connections`).

---

## Come ripartire da chat nuova

Apri una chat nuova nella cartella `f:\sicurezzacapire` e scrivi:

> "Leggi `bizquery-agent-gym/LEARN_LANGFUSE.md` e la memoria del progetto BizQuery.
> Sono alla **Capacità N**, guidami passo passo a impararla e verificarla dal vivo."

Il contesto del progetto (cosa è fatto, fatti operativi su Docker/Gemini/Langfuse)
è già in memoria e verrà richiamato.

**Setup operativo da ricordare** (già funzionante):
- Stack: `cd bizquery-agent-gym && docker compose up -d` (db postgres:16 + app FastAPI :8000).
- Chiavi Langfuse già nel `.env` (`LANGFUSE_PUBLIC_KEY/SECRET_KEY/HOST`) e passate al
  container via `docker-compose.yml`. `auth_check: True` verificato (region EU).
- Il tracing si autodisattiva se le chiavi mancano (`app/observability/langfuse_setup.py`).
- Gemini free tier `gemini-2.5-flash-lite`: ~20 richieste/giorno, 429/503 transitori
  (non bug) → nei test di eval mettere retry/attese.
- Ingestion Langfuse è **asincrona**: dopo una run fare `flush()` e attendere ~10s
  prima di leggere le trace via API (con timeout ampio).

---

## La mappa completa: 8 capacità (non 5)

| # | Capacità | Cosa dimostri sul CV | Match annunci | Stato |
|---|----------|----------------------|---------------|-------|
| 1 | **Tracing** (trace/span, latenza, costo) | telemetry / monitoring | FanDuel r.36, linkedin1 | ✅ FATTO |
| 2 | **Scores & Evaluation offline** (dataset → esperimenti → punteggio) | *automated evaluation (offline)*, *evaluation frameworks* | FanDuel r.36-37, linkedin9 | ✅ FATTO |
| 3 | **Prompt Management** (prompt versionati in Langfuse) | *prompt / version management* | FanDuel r.35 | ✅ FATTO |
| 4 | **Feedback online & Scores dal vivo** (voto utente/LLM sulle run reali) | *automated evaluation (online)* | FanDuel r.36 | ⬜ |
| 5 | **LLM-as-a-judge / Evaluators** (valutazione automatica della qualità) | *hallucination rate*, *quality over time* | linkedin1, FanDuel r.36 | ⬜ |
| 6 | **Dashboards & Metrics** (costo/latenza/qualità nel tempo, drift) | *monitoring*, *drift* | linkedin1 | ⬜ |
| 7 | **Experiments / A-B** (confronto tra due prompt o modelli) | *A/B tests, safe rollout* | FanDuel r.37 | ⬜ |
| 8 | **Human Annotation & Sessions** (ground truth umano, conversazioni multi-turn) | *human-in-the-loop*, data flywheel | linkedin vari | ⬜ |

> Regola pratica: fatte **1→2→3** puoi scrivere onestamente sul CV
> "LLM observability & evaluation with Langfuse" e reggere le domande in colloquio.
> **4→5→6** = profilo "produzione/senior". **7→8** = "senior+".

---

## Capacità 1 — Tracing ✅ (FATTO)

**Concetto**: ogni run del grafo = una **trace**; ogni nodo = uno **span**; ogni
chiamata LLM = una **generation** (span speciale con token/costo/modello).

**Cosa è stato fatto qui**: `CallbackHandler` di Langfuse (`langfuse.langchain`)
passato a `graph.invoke(config={"callbacks":[handler]})` in `/ask-graph` e `/approve`.
LangGraph chiama il callback a ogni nodo → Langfuse costruisce l'albero da solo.

**Cosa saper leggere nella UI** (Tracing → clic su una trace root):
- albero degli span con **latenza per nodo** (qui i colli di bottiglia sono le 2
  chiamate Gemini: `sql_executor` ~3.7s + `reviewer` ~1.6s ≈ tutta la latenza);
- pannello Input/Output = come lo **stato del grafo** si riempie nodo dopo nodo;
- righe `ERROR` rosse = i 503 Gemini transitori (utile: si vedono anche i fallimenti);
- filtri Search: `level:ERROR`, `latency:>2`, `name:LangGraph`.

**Esercizio per consolidare**: clic sullo span `sql_executor` → guarda input/output
della generation Gemini e se ci sono token/costo. È il pezzo "generation".

---

## Capacità 2 — Scores & Evaluation offline ✅ (FATTO 2026-07-09)

**Perché prima di tutto il resto**: è LA parola chiave degli annunci ("evaluation").
Il progetto era **già a metà**: esistevano `eval/dataset.json` (15 domande con valore
atteso) ed `eval/eval.py` (accuracy locale, output JSON).

**Concetti Langfuse**:
- **Dataset** = collezione di `dataset item` (input + `expected_output`).
- **Experiment / Dataset Run** = giri il tuo sistema su tutti gli item del dataset.
- **Score** = numero/etichetta attaccata a una run (es. `correct=1/0`, o `accuracy`).

**Cosa è stato costruito** (due file, il vecchio `eval.py` resta intatto come
fallback locale senza Langfuse):
1. `eval/langfuse_dataset.py` — upload **idempotente** di `dataset.json` → Dataset
   `bizquery-eval` (15 item). Chiave: `id=caso["id"]` → Langfuse fa UPSERT, rilanci
   senza duplicare. Separazione `input={question}` / `expected_output=atteso` /
   `metadata={tenant_id, tolerance, sql_kind}`: è lo schema che `run_experiment`
   si aspetta. **Non chiama Gemini** → costo zero.
2. `eval/eval_langfuse.py` — pattern v4 `dataset.run_experiment(task=, evaluators=)`.
   - **task**(*, item): la pipeline reale (domanda→SQL→guardrail→DB→scalare).
   - **evaluator**: `correct` 1/0 (con `tolerance` dal metadata per i float).
   - Langfuse orchestra il resto: per ogni item apre una trace, chiama task+evaluator,
     crea gli score, li lega alla dataset run. Ritorna `dataset_run_url`.

**La frase da colloquio** (perché conta): non "so accendere Langfuse", ma *"ho
separato la pipeline (task) dalla logica di valutazione (evaluator) e la giro su un
dataset versionato → esperimenti riproducibili e confrontabili"*. = "evaluation
framework", non "uso di un tool". E apre gratis la Cap.7 (A/B): stesso dataset, due
prompt → due esperimenti → confronto nella UI.

**Cost control (Gemini free tier ~20/giorno)**: `task` **cachea l'SQL generato** su
`eval/results/sql_cache.json`. Primo giro chiama Gemini e salva; giri successivi
rileggono → **zero chiamate**. Così rilanci l'experiment quante volte vuoi per
imparare la UI. Flag: default 5 casi, `--all` per 15, `--no-cache`.

**Trap v4 risolte** (i tutorial v2/v3 sono diversi — verificato sul client 4.13.2):
- L'evaluator DEVE ritornare `Evaluation(name=, value=, comment=)` (`from langfuse
  import Evaluation`), **non un dict** — la docstring dice dict ma `result.format()`
  accede a `.name` e crasha sul dict.
- `get_dataset_runs(dataset_name=...)` è **keyword-only**.
- `run_experiment` gira su `self.items` del dataset client → per un **sottoinsieme**
  si filtra `dataset.items` in-place (lista Python) *prima* di chiamarlo.
- Il codice va nel container: aggiunti mount volumi `./app` e `./eval` in
  `docker-compose.yml` (dev: modifiche subito attive senza rebuild).

**API v4 usate** (verificate): `create_dataset`, `create_dataset_item` (con `id` per
upsert), `get_dataset`, `dataset.run_experiment`, `get_dataset_runs`.

**Verificato dal vivo**: dataset `bizquery-eval` (15 item) nel cloud; run con
`correct: 1.000` (5/5 subset), score navigabile fino alla singola trace.

**Criterio "capacità 2 acquisita"** ✅: esiste un Dataset Langfuse popolato e un
Experiment con Score visibile, e sai spiegare offline (dataset fisso, laboratorio)
vs online (run reali di produzione — Cap.4).

---

## Capacità 3 — Prompt Management ✅ (FATTO 2026-07-09)

**Problema che risolve**: i prompt erano **hardcoded** in `app/llm/gemini_client.py`
(`_SYSTEM_PROMPT`, `_REVIEW_PROMPT`). Cambiarli = cambiare codice + redeploy, e non
c'è storico. In produzione i prompt si **versionano fuori dal codice**.

**Concetto Langfuse**: carichi il prompt su Langfuse (`create_prompt`), lo recuperi
a runtime (`get_prompt`, con cache locale), lo aggiorni dalla UI senza toccare il
codice. Ogni versione è tracciata; le trace si **linkano alla versione di prompt usata**
→ sai quale prompt ha prodotto quale risultato.

**Cosa è stato costruito**:
1. `app/observability/prompts.py` — helper `get_prompt(name, fallback, **vars)` →
   `ResolvedPrompt(text, ref, from_langfuse)`. Recupera da Langfuse con cache 60s,
   **fallback nativo v4** (se il server non ha il prompt o è offline, usa la stringa
   hardcoded → comportamento identico a prima). `ref` = `name@vN` o `name@fallback`.
2. `app/llm/gemini_client.py` — i due prompt hardcoded restano come **fallback**
   (convertiti alla sintassi Langfuse `{{var}}`, doppia graffa, NON str.format).
   `generate_sql`/`review_answer` recuperano da Langfuse e **registrano** la versione
   usata in `_LAST_PROMPT_REF` (via `_record_prompt_ref`/`last_prompt_ref`).
3. `app/observability/seed_prompts.py` — carica i due prompt su Langfuse etichettati
   `production` (idempotente in senso Langfuse: rilanci → nuova versione, `production`
   punta all'ultima). Importa i testi da `gemini_client.py` (una sola fonte di verità).
4. Link prompt→trace: `prompt_ref_sql`/`prompt_ref_review` aggiunti allo `AgentState`
   e alla `GraphResponse`. I **nodi** (`sql_executor_node`, `reviewer_node`) leggono
   `last_prompt_ref(...)`, lo mettono nello stato e sui metadata trace via
   `update_current_trace`.

**Trap v4 risolte** (verificate sul client 4.13.2):
- Variabili prompt = **`{{var}}`** (doppia graffa) compilate con `prompt.compile(**vars)`,
  NON `str.format` (`{var}`). Il fallback locale usa lo stesso `{{var}}` (replace
  manuale in `_render_fallback`) così UN solo testo vale sia su Langfuse sia offline.
- **`update_current_generation` da dentro `generate_sql` è un NO-OP**: la chiamata
  Gemini gira nel thread del nodo, FUORI dallo span OTel aperto dal CallbackHandler
  LangGraph → "No active span in current context" (verificato). Soluzione: linkare
  il ref DAI NODI (dove il contesto trace è attivo), non da dentro il client Gemini.
- `get_prompt` accetta `fallback=` nativo (stringa per type `text`) → non serve
  try/except attorno per la robustezza, ma lo teniamo comunque per host irraggiungibile.

**API v4 usate** (verificate): `create_prompt(name=,prompt=,type=,labels=,commit_message=)`,
`get_prompt(name, label=, type=, fallback=, cache_ttl_seconds=)`, `.compile(**vars)`,
`update_prompt(name=, version=, new_labels=)`, `clear_prompt_cache`, `update_current_trace`.

**Verificato dal vivo**: prompt `bizquery-sql-system@v1` e `bizquery-reviewer@v1` nel
cloud; `get_prompt` scarica e compila (`from_langfuse: True`); **hot-swap dimostrato**
(creata v2 con sentinella → `get_prompt` serve subito v2 senza toccare codice →
rollback a v1 spostando l'etichetta `production`); grafo reale (DB vivo) propaga
`prompt_ref_*@v1` nello stato e nella risposta. 47 test verdi. (La trace nel cloud
non ri-verificata via `/ask-graph` per 503 Gemini transitorio + timeout API lettura
Langfuse — problemi esterni, non di codice; il link è provato tramite lo stato.)

**Criterio acquisita** ✅: cambio un prompt dalla UI/API Langfuse e il comportamento
cambia **senza toccare il codice** (hot-swap v1↔v2 dimostrato); la run porta con sé
la versione di prompt usata (`prompt_ref_*` nello stato/risposta e sui metadata trace).

---

## Capacità 4 — Feedback online & Scores dal vivo ⬜

**Differenza chiave (offline vs online)**:
- *offline* (cap. 2) = valuti su un dataset fisso, in laboratorio.
- *online* = valuti le run **reali di produzione**, es. un pollice su/giù dell'utente,
  o uno score automatico su ogni chiamata vera.

**Cosa costruiremo**: un endpoint `/feedback` (o un bottone nella UI web esistente
su `GET /`) che, dato il `trace_id` di una risposta, scrive uno **Score** sulla trace
(`score_current_trace` / `create_score` con il trace id). Così colleghi il giudizio
dell'utente alla run.

**Criterio acquisita**: dopo una risposta, invio un feedback e lo vedo comparire come
Score sulla trace corrispondente nella UI.

---

## Capacità 5 — LLM-as-a-judge / Evaluators ⬜

**Concetto**: invece di valutare a mano, un **secondo LLM giudica** la qualità
(es. "la risposta è pertinente? c'è allucinazione?") e produce uno Score automatico.
Langfuse ha **Evaluators** server-side (sezione Evaluators/Scores nella UI) e/o si
può fare via codice.

**Aggancio col progetto**: hai GIÀ un reviewer LLM (`review_answer` in
`gemini_client.py`) che dà ok/retry. Il passo è trasformarlo in uno **Score**
registrato su Langfuse (non solo una decisione interna al grafo), e/o configurare un
Evaluator Langfuse per hallucination/relevance.

**API**: `run_batched_evaluation`, `cl.api.score_configs`, sezione UI Evaluators.
LLM connection per il judge: `cl.api.llm_connections`.

**Criterio acquisita**: ogni run ottiene automaticamente uno score di qualità
generato da un LLM-judge, visibile e filtrabile nella UI.

---

## Capacità 6 — Dashboards & Metrics ⬜

**Concetto**: dai singoli trace ai **trend aggregati**: costo per giorno/tenant,
latenza media per nodo, tasso di retry, tasso di rifiuto guardrail, andamento dello
score qualità nel tempo (= **drift**, parola degli annunci).

**Cosa costruiremo**: esplorare i **Dashboards** pronti di Langfuse e costruirne uno
custom sulle metriche BizQuery (usa `cl.api.metrics`). Non serve molto codice: è
soprattutto saper leggere/costruire i grafici e spiegarli.

**Criterio acquisita**: una dashboard che mostri costo+latenza+qualità nel tempo, e
sai dire "guarda, qui lo score è calato → possibile drift/regressione".

---

## Capacità 7 — Experiments / A-B ⬜

**Concetto**: confrontare **due versioni** (prompt A vs B, o Flash vs Pro) sullo
stesso dataset e vedere quale vince, in modo riproducibile. È la base del *safe
rollout* (feature flag, canary, A/B) chiesto da FanDuel r.37.

**Cosa costruiremo**: usare `run_experiment` per girare il dataset con due prompt
diversi (le versioni della cap. 3) e confrontare gli Score. Collega cap. 2+3+7.

**Criterio acquisita**: un confronto A/B tra due prompt sullo stesso dataset, con
verdetto numerico ("prompt B: 14/15 vs prompt A: 13/15").

---

## Capacità 8 — Human Annotation & Sessions ⬜

**Human Annotation**: code di revisione (`api.annotation_queues`) dove un umano
etichetta le trace (buona/cattiva) → crea **ground truth** per migliorare eval e
few-shot (si sposa col **data flywheel** già nel progetto: `app/flywheel.py`).

**Sessions**: raggruppano più trace in una **conversazione** (per app multi-turn).
BizQuery oggi è single-turn, ma sapere cos'è una Session serve per le chat.

**Criterio acquisita**: so creare una annotation queue e spiegare a cosa serve una
Session; ho annotato almeno qualche trace a mano.

---

## Match con le job offer reali (perché tutto questo conta)

Estratti da `../job offer riferimento/`:

- **FanDuel (USA, $170-213k)** — `usa/linkedin12` r.35-37:
  - *"automated **evaluation** (offline + online)"* → cap. 2 + 4
  - *"**telemetry/monitoring**"* → cap. 1 + 6
  - *"**prompt/version management**"* → cap. 3
  - *"**latency/cost controls**"* → cap. 1 + 6
  - *"**guardrails**"* → già nel grafo (guardrail.py)
  - *"LLM **evals** in CI"* → cap. 2 dentro la pipeline CI/CD
  - *"**A/B tests**, safe rollout"* → cap. 7
- **linkedin1** r.31: *"monitor performance, **drift**, **hallucination rates** in
  production"* → cap. 5 + 6.
- **linkedin9 (USA)** r.7,18: *"robust **evaluation frameworks** ensuring
  reproducibility and continuous improvement"* → cap. 2 + 7.
- **linkedin7 (UE)** r.26: *"production-grade AI systems that are **monitored** and
  scalable"* → cap. 1 + 6 (+ deploy/CI, punti separati del progetto).

**In sintesi**: Langfuse coperto bene = tre pilastri degli annunci in un colpo —
**observability, evaluation, prompt management**. È il moltiplicatore che trasforma
"so chiamare le API" in "so operare LLM in produzione".

---

## Ordine consigliato di lavoro

`2 → 3 → 4 → 5 → 6 → 7 → 8`

Motivo: 2 e 3 costruiscono le fondamenta (dataset + prompt versionati) su cui tutto
il resto si appoggia (4 usa gli score, 5 automatizza gli score, 6 li aggrega, 7 li
confronta tra versioni di prompt, 8 aggiunge il giudizio umano). Ogni capacità è
**verificabile dal vivo** prima di passare alla successiva — stesso metodo del resto
del progetto.
```
