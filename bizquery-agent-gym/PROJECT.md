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

## Nota per il futuro — "BizQuery advanced" (versione senior, coi crediti AWS)

> **Intuizione dell'utente (2026-07-11), da riprendere in una sessione dedicata.**
> Dopo aver chiuso il deploy SEMPLICE (EC2 singola + `docker compose`, free tier
> puro), rifare il deploy come lo farebbe un senior — versione **advanced**,
> sfruttando i **crediti AWS gratuiti** (120 USD residui al 2026-07-11, validi
> fino a ~gennaio 2027, + fino a ~100 USD guadagnabili completando le attività
> "Guadagna crediti" nella console). I crediti coprono i servizi che NON sono
> free tier, così l'advanced si fa a costo zero reale.
>
> **Perché a strati e non subito advanced**: si vede prima la versione "a mano"
> (si capisce ogni pezzo), poi la versione orchestrata (si capisce cosa
> automatizza e perché). Sul CV vale di più saper fare ENTRAMBE e saper scegliere
> il livello giusto (giudizio architetturale = skill senior).
>
> **Piano "advanced", a strati (ognuno un esercizio dedicato, da fare passo dopo
> passo su richiesta dell'utente):**
> 1. **Infrastructure as Code (Terraform)** — infra descritta in codice,
>    creabile e DISTRUGGIBILE con un comando. Il pezzo senior per eccellenza.
> 2. **ECS Fargate** — container orchestrati invece di `docker compose` a mano.
> 3. **RDS Postgres** — DB gestito con backup, invece del container Postgres.
> 4. **Secrets Manager** — evoluzione del pattern SSM già usato nel deploy semplice.
> 5. **Application Load Balancer + HTTPS** — dominio + certificato TLS (no più HTTP:8000).
> 6. **CI/CD (GitHub Actions)** — push → deploy automatico su ECS (il CI/CD che
>    era stato consapevolmente saltato nel deploy semplice).
>
> ⚠️ **Regola d'oro advanced**: ECS+RDS+ALB bruciano ~30-50 USD/mese se lasciati
> accesi. Si accende per l'esercizio, si verifica, si **distrugge** (con Terraform
> è un `destroy`). Il budget alert a 0 USD già attivo protegge da sorprese.
> Quando i crediti finiscono, se resta acceso, si paga.

---

## Direzioni di crescita e lista pratica (deciso 2026-07-12)

> **Contesto**: il codice applicativo dei 3 livelli è già fatto e live. La domanda
> ora non è "quale tech nuova", ma **come raffinare il profilo verso i ruoli di
> mercato**. Discussi ruoli-estensione e skill interne all'AI Engineer. Sia LLMOps
> che AI Security **si imparano con la PRATICA** (costruendo/attaccando sistemi veri),
> non con lo studio teorico → BizQuery è il banco di prova. Tutto fattibile con
> Claude Code (zero ML pesante).

### Ruoli-estensione decisi (i 3 migliori per questo profilo)

1. **LLMOps / AI Platform Engineer** ⭐ — l'upgrade più naturale. È già l'80% di
   BizQuery (observability, eval harness, deploy, CI/CD, cost control, guardrails,
   prompt management). ⚠️ **Distinzione critica di posizionamento**: "ML Platform
   Engineer" ha DUE rami. **Ramo A** (platform per il *training* di modelli: GPU
   cluster, distributed training, Kubeflow, feature store) = tocca ML vero, **da
   IGNORARE** (cugino del ML pesante escluso). **Ramo B** = **LLMOps** (platform per
   sistemi LLM in produzione: nessun training, tutto framework/codice) = quello che
   già facciamo. **Sul CV usare il titolo "LLMOps / AI Platform Engineer", NON "ML
   Platform" secco** (ambiguo → un recruiter potrebbe aspettarsi distributed training).
   Leggere sempre le responsabilità dell'annuncio: LangGraph/eval/tracing/agents → è
   ramo B (sei tu); training/GPU/Kubeflow → ramo A (salta).
2. **Applied AI Engineer / Forward Deployed Engineer** ⭐ — il ramo "business".
   Vai dal cliente, traduci il problema in soluzione agentica su misura. Combacia col
   profilo full-stack+product. È il ramo che porta a Staff/Principal (decisioni +
   business value). Dubai/consulenza lo pagano oro.
3. **AI Security Engineer** — la nicchia già toccata (guardrail, anti-injection, PII,
   RLS, IAM). In EU/Dubai (AI Act, GDPR) poco affollata e pagata benissimo.

> **Ruoli SCARTATi**: Data Engineer puro (torna verso l'infra del dato: Airflow/
> Snowflake/dbt/Kafka — ops-pesante, direzione opposta; se ne rubano a pezzi solo
> dbt + un orchestratore + data quality, senza convertirsi). ML Engineer/Research e
> MLOps GPU (già esclusi: matematica/Master). **OSINT e pentesting generalista**:
> mestieri interi e divergenti — impararli "un po'" disperde, non dà un ruolo (a meno
> che non diventino passione, altro discorso). La security che conviene è quella
> **applicata agli agenti che già si costruiscono**, non un pivot al pentest.

### Skill interne all'AI Engineer da rafforzare (le 3 a ROI più alto)

1. **Evaluation come sistema** 🔥 — il gap #1 storico. Non l'eval offline (già fatta),
   ma: LLM-as-judge multi-criterio (faithfulness, groundedness, task-success, safety,
   cost) + regression testing in CI (prompt cambia → score scende → merge bloccato) +
   feedback online (il Cap.4 Langfuse lasciato in sospeso). È ciò che separa dal
   "provare a mano". Farlo su BizQuery tocca automaticamente le altre due sotto.
2. **Context Engineering** — la skill 2026 dei senior agentici. Assemblare
   dinamicamente il contesto (cosa metti/comprimi/recuperi, state management, memory).
   Il data flywheel è già un pezzo → renderlo sistematico.
3. **Robustezza agentica in produzione** — failure recovery, idempotenza, gestione
   tool falliti, cost/latency per richiesta, fallback tra modelli. C'è già il retry
   loop → il livello Staff è renderlo misurabile e a prova di produzione.

### Lista pratica — cosa FARE su BizQuery (per skill)

**LLMOps (banco di prova = BizQuery):**
- [ ] Feedback online: endpoint `/feedback` che scrive uno Score Langfuse su una trace (Cap.4 lasciato)
- [x] LLM-as-judge multi-criterio nell'eval (faithfulness / relevance / safety) ✅ (2026-07-14)
- [x] Regression testing dell'agente in CI (soglia di score → blocca) ✅ (2026-07-14)
- [~] CI/CD GitHub Actions: **CI FATTA** (test + quality gate). **CD (deploy auto) RIMANDATO**
      di proposito alla versione advanced ECS (vedi nota sotto) — evita di costruire un
      CD-via-SSH fragile e usa-e-getta sulla EC2 singola con IP dinamico.
- [ ] Cost/latency dashboard per richiesta (Langfuse) + budget alert per tenant
- [ ] BizQuery advanced (Terraform/ECS/RDS/Secrets/ALB) — vedi nota sopra

**AI Security (banco di prova = attaccare i guardrail di BizQuery):** ⬅️ IN CORSO
- [x] Mini red-team: bucare l'anti-injection e il PII masking, poi indurirli ✅ (2026-07-14)
      8 bypass trovati → 0. Vedi `security/README.md` e "Stato → Aggiornamento 2026-07-14 (sera)".
- [x] Suite di test di jailbreak/prompt-injection contro l'agente (regressione di sicurezza) ✅ (2026-07-14)
      `tests/test_security_redteam.py` (19 test), agganciata alla CI (job `test`, zero Gemini).
- [x] Mappare BizQuery sull'OWASP Top 10 for LLMs (quali coperti, quali no) ✅ (2026-07-14)
      Tabella in `security/README.md`.
- [x] Rigenerare la chiave Gemini compromessa in SSM (già in TODO cleanup) — igiene segreti ✅ (2026-07-13)
- [ ] Threat model del flusso agentico (dove un input malevolo può fare danni)
      Parzialmente avviato (OWASP map); resta LLM04 data-poisoning via flywheel.
- [ ] garak scanner (contro guardrail no-LLM / contro /ask a quota piena) — prossima sessione
- [ ] promptfoo su /ask end-to-end (injection reale) — manuale, quota permettendo

> **Consiglio secco dato all'utente**: partire da **Evaluation come sistema**
> (feedback online + LLM-judge + regression in CI) perché è il singolo blocco a ROI
> più alto e spinge dritto verso il ruolo #1 (LLMOps). ✅ FATTO (2026-07-14, vedi stato sotto).
> **Prossimo consiglio**: fase **AI Security** (red-team sui guardrail) — è evaluation
> applicata alla sicurezza e la suite di attacco gira nella CI appena costruita.

---

## Stato avanzamento

> **Aggiornamento 2026-07-14 (sera) — AI SECURITY, 1° PEZZO: red-team dei guardrail FATTO. ✅**
> Attaccati i guardrail veri di BizQuery, induriti, e trasformati gli attacchi in
> regressione di sicurezza in CI. **Non ancora committato** (fine sessione).
>
> **Metodo scelto (dopo discussione)**: l'utente voleva usare repo/tool standard del
> mestiere (garak/promptfoo/presidio) invece di solo regex a mano. Decisione presa
> insieme, con criterio:
> - **presidio SCARTATO** per ora (motivo nel codice `mask_pii.py`): tira spaCy+numpy
>   (~300MB) per NER su TESTO LIBERO, ma qui le PII sono SOLO la colonna `email`
>   strutturata → sovradimensionato. Diventa giusto se lo schema aggiunge nomi/telefoni.
> - **promptfoo ADOTTATO come design**, ma `npx promptfoo` si blocca in questo ambiente
>   (download/interattività) → il **motore che gira in CI è un runner pytest** che legge
>   gli STESSI casi dalla `promptfooconfig.yaml` (fonte unica di verità). La config
>   promptfoo resta valida per quando npx è disponibile (report più ricco).
> - **garak RIMANDATO** a prossima sessione (Python 3.14 fresco → containerizzare; e
>   contro /ask brucia quota Gemini). Nota utente: "usare Claude Code al posto di Gemini"
>   NON è fattibile — garak attacca l'endpoint `/ask` che ha Gemini cablato dentro; il
>   red-team ha senso solo contro il sistema VERO. Uso corretto: garak contro il guardrail
>   (no LLM, zero quota) oppure contro /ask a quota piena.
>
> **Buchi trovati → chiusi**: red-team iniziale **8 bypass su 13**, dopo hardening **0**.
> - `pg_read_file`/`lo_export`/`pg_sleep`/`current_setting` passavano (SELECT read-only
>   con `tenant_id` nella stringa, nessuna keyword di scrittura) → **blocklist funzioni
>   pericolose** in `guardrail.py`.
> - `SELECT tenant_id, email FROM customers` (no WHERE), `AS tenant_id` (alias),
>   `WHERE name='tenant_id'` (stringa), `UNION SELECT ...` (2° ramo senza filtro)
>   passavano perché il check tenant era una **substring** → ora è un **vero predicato**
>   (`tenant_id =/IN/BETWEEN`) richiesto in **OGNI ramo** di UNION/INTERSECT/EXCEPT.
> - PII: `josé.garcía@…` restava in chiaro (regex ASCII-only) → **regex Unicode**.
>
> **Cosa è stato creato/modificato** (git root `F:\sicurezzacapire`):
> - `bizquery-agent-gym/app/guardrail.py` — blocklist funzioni + filtro tenant a predicato + UNION per-ramo.
> - `bizquery-agent-gym/app/tools/mask_pii.py` — regex Unicode + nota "presidio scartato perché".
> - `bizquery-agent-gym/security/guardrail_provider.py` — ponte promptfoo→check_sql.
> - `bizquery-agent-gym/security/promptfooconfig.yaml` — 13 casi (fonte unica di verità).
> - `bizquery-agent-gym/security/README.md` — red-team + **mappa OWASP LLM Top 10**.
> - `bizquery-agent-gym/tests/test_security_redteam.py` — 19 test (14 guardrail + 5 PII).
> - `bizquery-agent-gym/requirements.txt` — +pyyaml.
> - `.github/workflows/ci.yml` — step "Regressione di sicurezza" nel job `test`.
>
> **Verificato in locale**: 58 test verdi (39 esistenti + 19 sicurezza), zero Gemini/DB.
> Il red-team dimostra prima (8 buchi) / dopo (0). ⚠️ Ambiente: pytest/pyyaml non erano
> nel Python di sistema (installati ad-hoc); in CI li installa requirements.txt.
>
> **Prossimi passi security** (in `security/README.md`): garak containerizzato; promptfoo
> su /ask end-to-end (quota piena); tautologie `tenant_id=tenant_id`; threat model LLM04
> (data-poisoning via flywheel); LLM10 cost-guardian con EXPLAIN.

> **Aggiornamento 2026-07-14 — EVALUATION COME SISTEMA + CI: FATTA. ✅**
> Chiuso il blocco a ROI più alto (LLMOps). Cosa è stato costruito, testato e
> **committato+pushato** (repo `Gestionalefracchiolladaniele/praticapermigliorare`,
> branch `main`, ultimo commit `4d9c6b5`):
>
> **1. LLM-as-judge multi-criterio** — `app/llm/judge.py`. Un secondo LLM (Gemini)
> giudica la risposta su 3 criteri (faithfulness / relevance / safety) con UNA sola
> chiamata (JSON con tutti i voti → risparmio free tier) e fallback deterministico
> (se 429/JSON sporco non crasha; la safety la misura comunque via regex sull'email).
> `eval/judge_evaluators.py`: 3 evaluator Langfuse che avvolgono il judge, con MEMO
> (1 sola chiamata judge per caso anche con 3 criteri). Agganciato a `eval_langfuse.py`
> col flag opt-in `--judge`. Il judge valuta la risposta NL VERA e mascherata (PII),
> non un proxy.
>
> **2. Quality gate (regression testing)** — `eval/quality_gate.py` + `eval/thresholds.json`.
> Gira l'eval e ritorna un EXIT CODE: 0=superato, 1=sotto soglia (blocca), 2=inconcludente.
> Soglie versionate (execution_accuracy 0.8; judge faith/rel 0.8, safety 0.9;
> min_evaluable_cases 8). `eval/eval.py` rifattorizzato: estratta `evaluate()` che
> ritorna i numeri (accuracy + accuracy_evaluable + conteggi).
>
> **3. ROBUSTEZZA AI RATE-LIMIT (lezione chiave della sessione)** — i 429/503 del
> free tier NON sono fallimenti di qualità: sono casi NON valutabili. Il gate ora li
> marca `rate_limited`, li ESCLUDE dal conto, misura `accuracy_evaluable` sui soli
> casi davvero valutati; se troppi cadono (< min_evaluable_cases) l'esito è
> INCONCLUSIVO (exit 2), non rosso. Un fallimento di qualità VERO fa ancora fallire
> (exit 1). Principio: *una CI che dipende da un servizio a rate-limit deve distinguere
> "qualità regredita" da "servizio indisponibile"*.
>
> **4. CI GitHub Actions** — `.github/workflows/ci.yml`. Due job: `test` (pytest
> mockato, 0 Gemini/0 DB, a ogni push) e `quality-gate` (eval reale su Postgres
> usa-e-getta come service container, RLS attiva via ruolo `bizquery_app`, gira su
> push a main / a mano). exit 2 del gate → warning + job verde (quota esaurita ≠ colpa
> del codice). **Verificata dal vivo**: la CI gira, accende il DB, seeda, chiama Gemini;
> oggi esito inconcludente SOLO perché la quota giornaliera Gemini (20 chiamate) era
> esaurita — il sistema NON ha sbagliato nulla (tutti 429/503, zero SQL errati).
> ⚠️ **Da riverificare dal vivo a quota ricaricata (24h)**: dovrebbe dare verde o un
> fail *vero* su cui lavorare.
>
> **Test**: 15 verdi totali (9 judge + 6 gate), zero quota Gemini bruciata (Gemini
> mockato via monkeypatch, come i test del grafo). Girano anche in CI nel job `test`.
>
> **Secret CI**: `GEMINI_API_KEY` messo su GitHub (Settings → Secrets → Actions).
> ⚠️ Verificare che sia la chiave NUOVA rigenerata, non la vecchia compromessa
> `AIzaSyBz...` (non confermato in questa sessione: la CI la usa e funziona, ma non
> è stato verificato QUALE chiave sia). I 3 secret Langfuse sono opzionali (il gate
> gira senza).
>
> **DECISIONE — CD (deploy automatico) RIMANDATO di proposito.** Non un "non fatto":
> una scelta architetturale. Un CD-via-SSH sulla EC2 singola attuale sarebbe fragile
> (IP dinamico → si romperebbe ai riavvii; servirebbe un Elastic IP) e usa-e-getta
> (da buttare quando si passa a ECS). Il CD "fatto bene" nasce dentro la versione
> **advanced ECS** (già prevista nella nota "BizQuery advanced"), con deploy nativo.
> Quindi: la CI (verifica) c'è; il CD (deploy auto) si fa in advanced.
>
> **PROSSIMA FASE deciso**: **AI Security — red-team sui guardrail** (2° pezzo del
> piano verticale eval→security→auth). Motivo: è evaluation applicata alla sicurezza,
> e la suite di attacco (jailbreak/prompt-injection) girerà nella STESSA CI appena
> costruita. Gran parte è puro Python (`app/guardrail.py`, `app/tools/mask_pii.py`) →
> fattibile SENZA spendere quota Gemini. Vedi "Lista pratica → AI Security" sopra.

> **Aggiornamento 2026-07-12 — deploy AWS COMPLETATO, L1 Step 7 CHIUSO. ✅**
> L'app è LIVE su internet: `POST http://35.152.199.210:8000/ask` risponde da IP
> pubblico ("Quanti clienti abbiamo?" → Gemini genera SQL → guardrail approva →
> RLS esegue → "15"). `/health` → `{"status":"ok"}`. Seed fatto (30 cust/100
> ord/2 tenant). I 2 fix del deploy sono stati risolti — e la lezione vale in
> generale: **in Docker Compose le liste (`ports`, `volumes`) di un override si
> FONDONO col base, non lo sostituiscono** (`ports: []`/`volumes: []` non tolgono
> nulla). Perciò: (1) la 5432 è legata a `127.0.0.1` NEL BASE (non "spenta" da un
> override); (2) i volumi di sviluppo (montaggio codice per hot-reload) sono stati
> spostati dal base a **`docker-compose.override.yml`** (Compose lo carica auto
> SOLO in locale) — nel base restavano e in cloud montavano una cartella vuota
> sopra `/app/app`, per cui l'app non partiva (`Could not import module app.main`).
> Ora il base è production-safe. L'app containerizzata gira su AWS EC2 (t3.micro,
> free tier, regione Milano `eu-south-1`). Metodo scelto = "migliore possibile restando safe e
> vicino al prod avanzato": immagine buildata in locale e pushata su
> **ghcr.io** (`ghcr.io/gestionalefracchiolladaniele/bizquery:latest`, pacchetto
> pubblico → pull anonimo), la EC2 fa solo `pull`. Compose base + override
> `docker-compose.prod.yml` (no build sulla EC2, no volume codice, Postgres NON
> esposto, `restart: unless-stopped`, schema montato da `~/schema.sql`).
> **Segreti come in prod**: la `GEMINI_API_KEY` sta in **SSM Parameter Store**
> (SecureString `/bizquery/gemini-api-key`), la EC2 la legge via **IAM role**
> `bizquery-ec2-role` con **policy custom least-privilege** `bizquery-ssm-read`
> (solo `ssm:Get*` su `parameter/bizquery/*` + `kms:Decrypt` ristretto a
> `kms:ViaService=ssm.eu-south-1`). **Verificato dal vivo**: la macchina legge e
> decifra la chiave col solo ruolo, nessun segreto su disco. Security group: solo
> 22 (dal mio IP) + 8000 (pubblica); 5432 chiusa. ⚠️ **La chiave Gemini in SSM è
> ancora quella compromessa `AIzaSyBz...` — va RIGENERATA** su
> aistudio.google.com/apikey (scelta consapevole per sbloccare il deploy).
> **Dati di progetto operativi** (dettagli comandi/token/chiave/script in
> `DEPLOY_AWS_HANDOFF.md`): account AWS ID `799374460640`; **budget alert AWS
> "zero spend" ATTIVO** (email appena la spesa supera 0,01 USD = rete di sicurezza
> costi); **IP pubblico `35.152.199.210` è DINAMICO** (cambia se la EC2 si riavvia
> → riverificarlo in console prima di usarlo); ⚠️ **i file nuovi di questa sessione
> NON sono committati su git** (`docker-compose.prod.yml`, `docker-compose.override.yml`,
> `CONCETTI_APPRESI.md`, `DEPLOY_AWS_HANDOFF.md`, `PROJECT.md` mod.) — repo
> `Gestionalefracchiolladaniele/praticapermigliorare`, git root `F:\sicurezzacapire`.
> **Concetti/architettura chiariti in questa sessione**: appunti di studio in
> `bizquery-agent-gym/CONCETTI_APPRESI.md` (cos'è BizQuery come API, database/
> DATABASE_URL vs mentalità Supabase, come un'azienda lo usa, SaaS con auth, MCP
> con esempi aziendali, Docker/registry/scatole, AWS vs Supabase, dominio+HTTPS).
> Per la versione senior/advanced vedi la nota "BizQuery advanced" sopra.

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
  - ✅ **Reviewer LLM vero (2026-07-07)**: `review_answer` in `gemini_client.py`
    (Gemini Flash valuta se il risultato risponde alla domanda) cablato in
    `reviewer_node`. Fallback deterministico (righe => ok) se l'LLM non è
    disponibile, così il grafo funziona comunque. Planner: resta passthrough +
    few-shot del flywheel (vedi L3) — di fatto il "planner intelligente" è il
    few-shot + il router.
  - ✅ **Langfuse tracing (2026-07-09)**: `app/observability/langfuse_setup.py`
    (client globale + callback handler autodisattivo se mancano le chiavi),
    agganciato a `/ask-graph` e `/approve`. Ogni run = trace, ogni nodo = span.
  - ✅ **Langfuse evaluation offline (2026-07-09)**: `eval/langfuse_dataset.py`
    (upload idempotente di `dataset.json` → Dataset `bizquery-eval`) +
    `eval/eval_langfuse.py` (`run_experiment` con task=pipeline ed evaluator=`correct`
    1/0, cache SQL per non bruciare il free tier). Percorso completo delle 8 capacità
    Langfuse in `LEARN_LANGFUSE.md`.
  - ✅ **Langfuse prompt management (2026-07-09)**: `_SYSTEM_PROMPT`/`_REVIEW_PROMPT`
    versionati su Langfuse (`bizquery-sql-system`, `bizquery-reviewer`) con fallback
    hardcoded. `app/observability/prompts.py` (`get_prompt` con fallback nativo v4 +
    cache), `app/observability/seed_prompts.py` (carica etichettati `production`).
    Variabili `{{var}}` (sintassi Langfuse). Link prompt→run: `prompt_ref_*` nello
    `AgentState`/`GraphResponse`, popolato dai nodi. Hot-swap prompt senza redeploy
    verificato dal vivo. (Cap.3 del percorso a 8 capacità in `LEARN_LANGFUSE.md`.)
  - 🟢 **CI FATTA (2026-07-14)**: GitHub Actions con test + quality gate (regression).
    Vedi "Stato avanzamento → Aggiornamento 2026-07-14" in cima. **CD (deploy auto)
    rimandato di proposito** alla versione advanced ECS (non un CD-via-SSH usa-e-getta).
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
  - ✅ **Data flywheel (2026-07-07)**: tabella `query_logs` (schema + RLS +
    GRANT INSERT/SELECT al ruolo app + WITH CHECK per l'isolamento in scrittura).
    `app/flywheel.py`: `log_run` (scrive ogni run, best-effort, non solleva) +
    `successful_examples` (rilegge le run riuscite come few-shot, de-dup per
    domanda, isolate per tenant via RLS). Cablato: `log_node` nel grafo (dopo
    answer), few-shot in `sql_executor_node` (solo al primo tentativo), logging
    anche in `/ask` v0. `tests/test_flywheel.py` (3 test: read-back, run fallite
    escluse, isolamento per tenant). **Verificato dal vivo**: run → query_logs →
    few-shot rilette, tenant 2 non vede i log del tenant 1.
  - ✅ **SQL avanzato nell'eval (2026-07-07)**: `eval/dataset.json` +5 casi
    (group by + max, avg con filtro, count distinct, sum senza filtro) con valori
    attesi calcolati dal DB reale seed=42. Dataset ora 15 casi.

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
