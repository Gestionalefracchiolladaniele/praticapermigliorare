# 🎯 ROADMAP — Da AI Engineer competente a Mostro Sacro

> **Documento di riferimento personale + bussola completa.** Costruito e verificato su:
> (1) i progetti reali dell'utente, (2) 12 annunci di lavoro reali "AI Engineer"
> (mercati IT/UE/USA/Dubai), (3) le sue priorità esplicite.
> Ultimo aggiornamento: 2026-07-04.
>
> **Questo file è autosufficiente:** se lo leggi in una chat nuova a freddo, contiene tutto il
> necessario per ripartire senza contesto perso. Leggilo tutto prima di rispondere.

---

## 🤝 COME LAVORARE CON ME (istruzioni per Claude — leggere per prime)

Sono uno **sviluppatore full-stack con AI già forte** (NON principiante): Claude Code, Supabase
(Postgres+RLS+pgvector), Next.js, Expo, API Claude/Gemini, GitHub Actions, Stripe, Vercel, pnpm.
JS/TS + Python medio. Obiettivo: diventare **AI Engineer di altissimo livello ("mostro sacro")**.
Mercati target: **Italia + Dubai**.

**Come voglio che tu ti comporti:**
- **Rispondi in italiano**, diretto, con **raccomandazioni secche** — non liste neutre di opzioni.
  Quando c'è una scelta migliore, dimmela e argomenta il perché.
- **Non rifarmi le basi che so già** (vedi "Dove sei ora"). Sarebbe tempo perso e me ne accorgo.
- **Il mio valore NON è scrivere codice** (quello lo fa Claude Code) — è la **COMPRENSIONE e le
  DECISIONI architetturali**. Quindi: quando costruiamo, **spiegami ogni decisione** (perché questa
  scelta, quando l'alternativa, cosa si rompe), non limitarti a produrre codice.
- **Metodo di studio:** partire da **repo GitHub reali** → me li spieghi → li adatto ai miei
  progetti → mi alleno sulle decisioni. Non tutorial finti: cose vere.
- **Sii onesto sui trade-off**, anche scomodi. Preferisco la verità ("questo è difficile / non
  vale la pena / ti serve laurea") a una risposta che mi fa sentire bravo.
- Se serve, **cerca conferme sul mercato reale** (annunci, dati) invece di andare a memoria.

---

## 🧠 CONTESTO STRATEGICO (i ragionamenti chiave, così non si perdono)

Sintesi di come siamo arrivati a questa roadmap — serve a un Claude a freddo per capire il *perché*.

- **Sono già oltre le "basi".** Ho spedito prodotti AI veri (RAG con pgvector, agenti con tool,
  semantic caching, pipeline multi-modello cost-aware). Non sono "uno che deve imparare l'AI" —
  sono "uno che la fa già a livello competente e deve fare il salto a senior/staff".
- **Ramo scelto = AI Engineer AGENTIC/APPLICATIVO**, NON ML classico. L'AI Engineering moderno
  (RAG, agenti, LLM in produzione) è un ramo **separato** dal ML/BigData (matematica, training,
  GPU). Posso diventare top **senza mai addestrare un modello da zero**. Confermato: 11/12 annunci
  sono applicativi, 1/12 è ML pesante (Dubai, barriera PhD).
- **~90% della roadmap è fattibile con Claude Code** (è codice/integrazione/architettura). L'unico
  ramo dove Claude Code aiuta poco è il ML pesante → per questo è **escluso**.
- **I miei 3 gap veri** (assenti nei miei progetti, presenti negli annunci): **(1) infrastruttura
  seria** (Docker/AWS/CI-CD/observability), **(2) evaluation** (misuro a intuito, mai
  scientificamente — è il gap #1, in 7/12 annunci), **(3) agenti veri/LangGraph** (faccio pipeline
  lineari, non orchestrazione stateful).
- **Il livello massimo (Principal €140-270k+) NON è codice.** Gli annunci top lo dicono esplicito:
  "translate business problems into commercial outcomes", "define what AND how". È architettura +
  business + decisioni. Non si delega a un tool: si costruisce sul campo, su progetti veri.
- **La verità sui livelli:** Senior = tecnicamente fortissimo (ci arrivo con Claude Code, ~12 mesi).
  Staff = "le decisioni giuste sono state prese perché c'ero io". Principal = shift qualitativo
  (business/ambiguità/org). Il "facile" è capire i concetti; il difficile è portarli a **produzione
  vera** (regge a scala, non brucia soldi, non allucina, è sicuro, è misurato).

---

## 📍 DOVE SEI ORA (livello reale, verificato dai tuoi progetti)

Non sei un principiante. Sei un **AI/product engineer competente** che ha già spedito prodotti veri.

**Già padroneggiato** (verificato in WhatsApp+Gmail Assistant, Dictra, Dopit, Clientivo, SoleUp):
- ✅ Integrazione LLM in produzione (Claude, Gemini — modello giusto per task, cost-aware)
- ✅ **RAG vero** (pgvector 1536D, HNSW, chunking, task type RETRIEVAL_DOCUMENT/QUERY, category filter)
- ✅ **Semantic caching** (SHA256, 60% hit — era "Fase 5", già fatto)
- ✅ **Agenti con tool** (calendar/meeting/email tool call — non solo pipeline)
- ✅ Prompt engineering serio, structured output, retry/cleanup
- ✅ Supabase/RLS/multi-tenant avanzato, Stripe/webhook, cron, monorepo, Expo mobile

**Traduzione:** lavori già come AI Engineer, ma in JS/TS invece che Python, e ti mancano
i pezzi "da senior" (infrastruttura seria + misurazione).

---

## 🧭 LA STRATEGIA (3 mosse, in ordine)

1. **MOSSA 1 — Dominare il ramo AI Engineer APPLICATIVO** (allineato a 11/12 annunci) ← FOCUS ORA
2. **MOSSA 2 — Estendersi a Data Engineering + DevOps/Platform** (i complementi naturali)

> **Nota:** ML pesante / fine-tuning / CUDA / inference optimization = **fuori scope, escluso.**
> È un altro mestiere (barriera Master/PhD + matematica, Claude Code aiuta poco). Non è la tua traiettoria.

**Principio-guida (il tuo insight vincente):**
> Claude Code scrive qualsiasi codice. Quindi il mio valore NON è la sintassi — è la
> **COMPRENSIONE e le DECISIONI architetturali**. Imparo partendo da **repo GitHub reali**,
> me li faccio spiegare, li adatto ai miei progetti, e mi alleno sulle DECISIONI, non sul digitare.

---

# 🥇 MOSSA 1 — AI ENGINEER APPLICATIVO (focus attuale)

> Questi sono i gap che compaiono negli annunci e che NON hai ancora.

## ⭐ ORDINE DI PRIORITÀ (leggere prima — cosa imparare e in che sequenza)

Non studiare tutto in parallelo. Segui quest'ordine, costruito su **dipendenze reali**
(cosa serve prima di cosa) + **frequenza negli annunci** + **valore aggiunto**.

### 🔴 LIVELLO 1 — ASSOLUTAMENTE NECESSARI (le fondamenta, senza queste non parti)
> Sono in 8-11 annunci su 12. Sono la base "produzione-ready". Falli PRIMA di tutto.

1. **Python + FastAPI** (gap 1.1) — la lingua dell'AI, serve per tutto il resto. `[prerequisito di tutto]`
2. **Docker** (dentro 1.2) — il mattone dell'infrastruttura, tutto gira qui sopra. `[prerequisito di deploy/queue]`
3. **Evaluation base** (gap 1.3) — il tuo GAP #1, in ogni tuo progetto manca. Misurare, non intuire.
4. **AWS free tier** (dentro 1.2) — deploy enterprise: Lambda + S3 + Bedrock. `[dopo Docker]`

### 🟡 LIVELLO 2 — MOLTO IMPORTANTI (il salto a "senior vero")
> In 6-9 annunci. Ti rendono affidabile e misurabile in produzione.

5. **Observability con Langfuse** (dentro 1.2) — vedere costi/latenza/errori. `[OpenTelemetry DOPO, è lo standard sotto]`
6. **Agenti + LangGraph** (gap 1.4) — orchestrazione stateful, dove sono i soldi 2026.
7. **CI/CD avanzata** (dentro 1.2) — deploy automatico, rollback. `[usi già GH Actions base]`
8. **Message queue** (dentro 1.2) — agenti async che non crashano. `[il cuore dei sistemi distribuiti]`

### 🟢 LIVELLO 3 — VALORE AGGIUNTO (ti distinguono, ma dopo le fondamenta)
> In 6 annunci o meno, o skill "avanzate". Alto valore ma NON prima dei livelli 1-2.

9. **Sicurezza AI + guardrails + PII** (gap 1.5) — oro in EU/Dubai. `[dopo aver un sistema in produzione]`
10. **MCP** (dentro 1.4) — costruire tool riutilizzabili, hai il vantaggio Claude Code.
11. **Ottimizzazione LLM** (gap 1.6) — model routing, prompt caching (semantic caching già fatto ✅).
12. **SQL avanzato** (gap 1.7) — query complesse dentro Supabase (non solo il wrapper).
13. **Reranking + hybrid search / Agent evaluation** (dentro 1.3/1.4) — il livello "profondo" di RAG e eval.
14. **Terraform, OpenTelemetry, incident response** (dentro 1.2) — approfondimenti infra `[quando l'infra base è solida]`.

> **Regola:** finisci il 🔴 prima di toccare il 🟢. Un sistema in Docker+AWS con evaluation vale
> più di 10 tool avanzati imparati a metà. Prima solido, poi brillante.

---

> Sotto: il dettaglio di ogni gap (cosa fa, perché, cosa costruire).

## 1.1 — Python + FastAPI  `[gap piccolo]`
- **Cosa:** la lingua madre dell'AI. Ogni framework serio (LangGraph, eval) è Python.
- **Perché:** 11/12 annunci lo chiedono esplicito. Tu programmi già, è questione di settimane.
- **Cosa costruire:** riscrivi UN endpoint di un tuo progetto in Python/FastAPI (es. l'agente
  del WhatsApp assistant) → capisci le differenze da TS.

## 1.2 — INFRASTRUTTURA / MLOps  `[GAP PRINCIPALE — il cuore del focus]`
> In 8-11 annunci su 12. È qui che diventi "produzione-ready", non "demo-ready".

- **Docker** — impacchetti l'app in un container che gira identico ovunque.
  - Modello mentale: immagine (ricetta) / container (piatto) / volume (dove restano i dati).
- **Cloud enterprise (AWS)** — Bedrock (modelli), Lambda (serverless), S3 (storage), ECS.
  - Perché: Vercel/Supabase = mondo startup; enterprise e Dubai girano su AWS/Azure/GCP.
- **CI/CD serio** `[in 8/12 annunci — skill autonoma, non solo "parte dell'infra"]` —
  matrix build, caching, deploy multi-ambiente, rollback automatici, feature flags,
  canary / blue-green, migrazioni DB sicure in produzione. Tu usi già GitHub Actions base → portalo a questo livello.
- **Message queue** (SQS / Redis / BullMQ) — agenti asincroni che non crashano sotto carico.
- **Terraform (IaC)** — l'infrastruttura come codice, riproducibile.
- **Observability LLM** (Langfuse / Phoenix + Sentry) — tracing per-step, costi, latenza, drift.
- **On-call / incident response** `[emerso in linkedin12]` — cosa fai quando il sistema si rompe
  in produzione: playbook, alerting, diagnosi rapida, post-mortem. È la differenza tra "funziona"
  e "so tenerlo in piedi h24". Fa parte del produzione-ready vero.
- **Cosa costruire:** prendi il WhatsApp+Gmail assistant → Docker → deploy AWS → queue → Langfuse
  → un alert che ti avvisa quando qualcosa va storto + un mini-playbook di risposta.

## 1.3 — EVALUATION + TESTING LLM  `[GAP #1 — la skill che ti distingue]`
> In 7/12 annunci. È l'UNICO gap presente in OGNI tuo progetto (spedisci a intuito, non misuri).

- **Cosa:** misurare scientificamente se RAG/agente funziona (faithfulness, groundedness,
  task success, hallucination rate, latenza, costo).
- **Tool:** RAGAS, DeepEval, promptfoo, LLM-as-judge.
- **Testing LLM:** unit + integration + LLM evals + feature flags + canary + A/B (linkedin12).
- **Agent evaluation** `[avanzato — la versione "seria" del gap]` — valutare un agente
  *multi-step* è MOLTO più difficile che valutare un RAG: non basta "la risposta è giusta?",
  devi valutare se ha scelto i tool giusti, nell'ordine giusto, recuperando dai fallimenti.
  Skill a sé, da affrontare dopo il RAG-eval base.
- **Cosa costruire:** un evaluation harness sul WhatsApp assistant → set di domande con risposte
  attese → misuri se il RAG recupera il chunk giusto e se l'agente agisce bene.

## 1.4 — AGENTI AVANZATI + LANGGRAPH  `[dove sono i soldi 2026]`
> In 9/12 annunci (orchestrazione, multi-agent, tool use).

- **LangGraph** — orchestrazione stateful, checkpoint, loop, human-in-the-loop.
- **Multi-agente** — pattern planner / executor / reviewer / critic.
- **Reranking + hybrid search** — il livello sopra il tuo RAG attuale (keyword+semantico, riordino).
- **Memory systems** — memoria a lungo termine (episodica/semantica).
- **Context engineering** — assemblare dinamicamente il contesto.
- **Data flywheel** — telemetria → eval automatica → l'agente migliora da solo.
- **MCP (Model Context Protocol)** `[standard 2026 — hai un vantaggio, sei già in Claude Code]` —
  costruire TU i tool che gli agenti usano, come server riutilizzabili e portabili tra agenti.
  Citato anche in un annuncio (linkedin1). Non è un dettaglio: è come si estendono gli agenti seri.
- **Cosa costruire:** trasforma una pipeline lineare (es. Dictra) in un agente LangGraph
  che pianifica, esegue, si autocorregge + esponi un tool tuo come server MCP.

## 1.5 — SICUREZZA AI + GUARDRAILS  `[oro in EU/Dubai]`
> In 6/12 annunci (AI safety, OWASP for LLMs, responsible AI).

- **Prompt injection defense**, jailbreak prevention.
- **PII detection & redaction** (non far leakare dati personali).
- **Guardrails** input + output filtering.
- **AI compliance** (EU AI Act, GDPR sugli LLM) — pagato oro in enterprise.
- **Cosa costruire:** aggiungi guardrail + PII redaction al WhatsApp assistant (è aziendale, credibile).

## 1.6 — OTTIMIZZAZIONE LLM  `[semantic caching già fatto ✅]`
> In 6/12 annunci (cost/latency optimization).

- **Model routing** — Haiku vs Opus automatico per difficoltà (lo fai a mano, automatizzalo).
- **Prompt caching (Anthropic)** `[risparmio immediato — lo usi già molto]` — marcare le parti
  stabili del prompt (system, few-shot, documenti) come cache → Anthropic non le ri-processa →
  fino a ~90% di risparmio sui token in input + meno latenza. Da applicare subito ai tuoi progetti
  che ripetono lo stesso contesto (Dictra few-shot, WhatsApp system prompt).
- **Structured generation garantita** — JSON/grammar forzato.

## 1.7 — SQL avanzato  `[rafforzare]`
> Emerso in linkedin1, linkedin4. Hai la base (Supabase), va portato a livello data modeling serio.

---

# 🥈 MOSSA 2 — ESTENSIONE (dopo aver dominato la Mossa 1)

> I due campi correlati che ti trasformano da "faccio AI" a "faccio AI e la porto in produzione
> a scala". Entrambi codice+infrastruttura → Claude Code al 100%.

## 2.1 — Data Engineering
- **Cosa:** costruire le pipeline che portano dati puliti/freschi ai tuoi sistemi AI.
- **Perché:** ogni agente/RAG è forte quanto i dati che riceve. Citato in linkedin1,4,6.
- **Tool:** Airflow / Dagster (orchestrazione), Kafka (streaming), dbt (trasformazione),
  BigQuery / warehouse, ETL.

## 2.2 — DevOps / Platform Engineering
- **Cosa:** l'infrastruttura su cui girano i sistemi, resa solida e riproducibile.
- **Perché:** è l'estensione diretta della Mossa 1.2. In 8-11/12 annunci.
- **Tool:** Kubernetes (a scala), Terraform, Prometheus/Grafana, GitLab CI/GitHub Actions avanzate.

---

# 📚 SPECIALIZZAZIONI ULTRA-SENIOR (mirate, quando un progetto le chiede)

Non da studiare a tappeto — da prendere quando servono. Ti distinguono.

| Area | Cosa fa | Quando |
|---|---|---|
| **Browser use agent** | Agente che usa il browser come un umano (siti senza API) | Molto pratico, utile subito |
| **GraphRAG (Neo4j)** | RAG su knowledge graph — collega info sparse, non solo "trova paragrafo" | Ti distingue, pochi lo sanno |
| **Voice AI** | Agenti vocali realtime (STT→agente→TTS + gestione latenza/interruzioni) | Wow-effect, mercato caldo |
| **Multimodale video/audio** | Video = frame+audio; audio = trascrizione. Sai già immagini+testo | Estensione facile |
| **Realtime AI** | WebSocket, streaming bidirezionale, agenti live | Per voice/chat fluide |
| **Edge / on-device AI** | Modelli sul telefono (privacy, zero costi, offline). Hai Expo = vantaggio | Privacy-critical |
| **Distributed AI** | Code, retry, idempotenza, eventual consistency per agenti a scala | L'infra che dà "idee avanzate" |

---

# 👑 IL LIVELLO NON-CODICE (ciò che ti fa Principal — €140-270k)

> Confermato ESPLICITAMENTE negli annunci top pagati. NON si delega a Claude Code.
> Si costruisce sul campo, prendendo decisioni su progetti veri con altri.

- **AI architecture** — disegnare sistemi, non scrivere funzioni.
- **Tradurre AI in valore di business** — "translate business problems into commercial outcomes"
  (linkedin7 €150-220k), "define what AND how" (linkedin12 Principal).
- **Prioritizzazione per valore di business**, gestione ambiguità, ownership.
- **Costi a scala** — far quadrare i conti con 100k+ utenti.
- **Mentoring + technical standards** — "the right decisions happened because I was involved".

---

# 🛠️ IL METODO (come studiare, ogni volta)

1. **Trova il repo GitHub di riferimento** che fa già la cosa (RAG production, LangGraph, RAGAS…).
2. **Fatti spiegare da Claude Code** riga per riga — capisci il PERCHÉ, non memorizzi la sintassi.
3. **Adatta/ricomponi** sul tuo progetto reale (parti dai progetti che già hai).
4. **Allenati sulle DECISIONI architetturali** (perché questa scelta? quando l'alternativa? cosa si rompe?).
5. **Costruisci** — la comprensione arriva costruendo, non leggendo.

---

# 🎯 I 2 PROGETTI-PORTFOLIO (dove applicare tutto)

## Progetto 1 — "Production AI Platform" (profondità: infra + misura)
Evolvi il tuo **WhatsApp+Gmail Assistant** a livello enterprise:
Docker → AWS → message queue → Langfuse (observability) → evaluation harness →
guardrails + PII → data flywheel.
→ Racconta: *"so prendere un sistema AI e renderlo affidabile, misurato, sicuro, in produzione."*

## Progetto 2 — "Agente avanzato" (ampiezza: frontier)
Da un repo LangGraph di riferimento → agente multi-step (planner/executor/reviewer) su un
caso tuo, con browser use o GraphRAG.
→ Racconta: *"non faccio solo l'ordinario, padroneggio anche il frontier."*

---

# ✅ PROSSIMO PASSO IMMEDIATO

Partire dal **Progetto 1**, gap **1.2 (infrastruttura) + 1.3 (evaluation)**, sul WhatsApp assistant
che già esiste. Claude Code scrive la sintassi; tu impari ogni DECISIONE architetturale.

**Mercati target:** Italia + Dubai. **Stipendi di riferimento (annunci reali):**
IT applicativo €40-60k → Senior/Founding €85-220k → Principal €190-270k+.

---

# 🚀 QUICK START (per una chat nuova a freddo)

Se stai leggendo questo file in una sessione pulita, ecco come ripartire in ordine:

1. **Leggi tutto questo file** — è la bussola completa, autosufficiente. In particolare le sezioni
   "🤝 Come lavorare con me" e "🧠 Contesto strategico" all'inizio.
2. **La strategia è già decisa e verificata** (su progetti + 12 annunci reali). Non ri-mappare da
   capo, non ripropormi ML pesante (escluso), non rifarmi le basi che già so.
3. **Focus attuale = MOSSA 1**, in particolare i gap **1.2 (infrastruttura)** e **1.3 (evaluation)**.
4. **Metodo:** partiamo da un **repo GitHub di riferimento**, me lo spieghi, lo adattiamo, io imparo
   le **decisioni** (non la sintassi — quella la scrivi tu).
5. **Primo task concreto proposto:** evolvere il mio WhatsApp+Gmail Assistant (RAG+agente+cache già
   fatti) a livello produzione → Docker → deploy → observability (Langfuse) → evaluation harness.
   Se non ricordi dov'è il progetto, chiedimelo — te lo indico io.
6. **Prima di scrivere codice**, se sto imparando qualcosa di nuovo, spiegami il concetto e le
   decisioni architetturali. Voglio capire, non solo eseguire.

> Nota: il mio profilo e questa roadmap sono anche nella memoria di Claude Code, quindi in teoria
> mi conosci già all'avvio. Questo file è la versione **completa e ragionata** — la fonte di verità.

---

# 📊 STATO AVANZAMENTO (da compilare in corso d'opera)

> Si riempie MENTRE costruisco, non ora. A ogni chat nuova, guarda qui per sapere dove sono.
> Legenda: ⬜ da fare · 🟡 in corso · ✅ fatto (con il criterio "fatto" scritto accanto quando lo raggiungo).

> **Come si compila** (esempio dimostrativo, NON progresso reale — cancellalo quando parti sul serio):
> `🟡 1.2 Infrastruttura — fatto Docker sul WhatsApp assistant (2026-08-10). Manca: AWS deploy + Langfuse. Prossimo: Lambda.`
> Cioè: cambia ⬜→🟡→✅, scrivi in una riga COSA hai fatto + data + COSA manca + il prossimo micro-passo.

**MOSSA 1 — AI Engineer applicativo**
- ⬜ 1.1 Python + FastAPI
- ⬜ 1.2 Infrastruttura (Docker · AWS · CI/CD · queue · Terraform · observability · incident response)
- ⬜ 1.3 Evaluation + testing LLM
- ⬜ 1.4 Agenti avanzati + LangGraph + MCP
- ⬜ 1.5 Sicurezza AI + guardrails
- ⬜ 1.6 Ottimizzazione LLM (model routing · prompt caching · structured generation)
- ⬜ 1.7 SQL avanzato

**MOSSA 2 — Estensione**
- ⬜ 2.1 Data Engineering
- ⬜ 2.2 DevOps / Platform Engineering

---

# 🎯 CRITERI "FATTO" (da definire quando arrivo a ogni gap)

> Per ogni gap, il traguardo concreto che dimostra che lo padroneggio davvero (non "l'ho letto").
> Lo scrivo insieme a Claude quando inizio quel gap. Regola: deve essere una **cosa che ho
> costruito e che funziona**, non "ho studiato X". Se non è verificabile guardando un progetto, non vale.
>
> **Come si compila** (esempi dimostrativi del formato — sostituiscili con i miei veri quando ci arrivo):
> - *1.2 Infrastruttura = FATTO quando ho un mio progetto in Docker, deployato su AWS, con Langfuse
>   che mostra i costi per richiesta reali.*
> - *1.3 Evaluation = FATTO quando ho un harness che dà un punteggio automatico al mio RAG su un set
>   di 20 domande, e so dire "recupera il chunk giusto l'85% delle volte".*
> - *1.4 Agenti = FATTO quando ho un agente LangGraph con planner/executor/reviewer che si autocorregge,
>   e un mio tool esposto come server MCP.*

(i criteri reali si scrivono qui, uno per gap, in corso d'opera)

---

# 📦 REPO GITHUB DI RIFERIMENTO (da raccogliere strada facendo)

> I repo reali da cui partire per ogni gap (li scegliamo quando arrivo a quel punto).
> Formato: `gap → repo → cosa impararci`.

(vuoto — si compila in corso d'opera)

---

# ⚙️ SETUP OPERATIVO (come lavoriamo concretamente)

**Dove:** tutto in `F:\sicurezzacapire\` (cartella-madre del percorso, separata dai progetti "veri"
in OneDrive). NON usare OneDrive per i progetti-palestra (sincronizzerebbe node_modules inutilmente).

**Struttura:** un progetto = una sottocartella isolata, numerata per gap. Es:
```
F:\sicurezzacapire\
├── ROADMAP-AI-ENGINEER.md      ← questa bussola
├── job offer riferimento\       ← annunci di riferimento
├── 01-infra-docker\             ← progetto gap 1.2
├── 02-evaluation\               ← progetto gap 1.3
└── ...
```
Ogni sottocartella ha il suo package.json / node_modules / venv — **non si mischiano**.

**Tooling nel terminale** (tutto normale, come già faccio): `pnpm`/`npm` per JS/TS, `git clone`
per i repo, `pip`+`venv` per Python (una cartella isolata per progetto, sintassi diversa da pnpm —
me la spiega Claude al primo progetto Python).

**Da zero vs repo — regola decisa insieme (2026-07-04):**
- Se il valore è **capire la meccanica di base** (es. Docker, AWS) → **costruisco DA ZERO** su
  un'app minima (leggere un Dockerfile già fatto non insegna; farlo dalla prima riga sì).
- Se il valore è **imparare un'architettura avanzata** (LangGraph, GraphRAG, agenti multi-step) →
  **parto da un REPO production-grade e lo modifico** (reinventarlo è lento e rischio di farlo male).
- Evaluation → repo dello strumento (RAGAS/promptfoo) applicato ai miei dati.
- Si sceglie caso per caso a ogni gap.

**NON per forza sui miei progetti esistenti:** posso partire da zero, da repo, o evolvere un mio
progetto. Per imparare l'INFRA pulita conviene isolare la variabile nuova (app minima da zero).

---

# 🗣️ CHIARIMENTO LINGUAGGI (per togliere l'ansia "devo impararne tanti nuovi")

**NO, non servono nuovi linguaggi per il ramo applicativo.** Equivoco comune da sfatare:
- **Docker / AWS / Kubernetes NON sono linguaggi.** Sono **configurazione + concetti** sopra il
  codice che scrivo già. Dockerfile = ~10 istruzioni. AWS = servizi che configuro; il codice dentro
  (Lambda) è lo stesso Node/Python che uso. K8s = YAML (già lo conosco). Terraform = HCL, config
  dichiarativa semplice, non programmazione vera.
- **Lo stack che ho basta:** JS/TS + Python + SQL coprono il 100% del ramo AI Engineer applicativo.
- **Unico "da rafforzare":** Python (da "un po'" a "solido", gap 1.1) e SQL (gap 1.7). Non sono
  nuovi, sono da approfondire.
- Java/Go compaiono solo in alcuni ruoli Principal enterprise = "nice to have", non un requisito ora.
- C++/CUDA erano SOLO nel ramo ML pesante, che è **escluso**.
→ Conclusione: l'infrastruttura è "config + comprensione", non una lingua aliena. Rilassati.
