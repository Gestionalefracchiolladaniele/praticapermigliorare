# BizQuery — Concetti chiave chiariti (appunti di studio)

> Raccolta dei chiarimenti concettuali emersi lavorando al deploy AWS (2026-07-12).
> Serve a fissare le fondamenta capite parlando, non solo scrivendo codice.
> Taglio "spiegato semplice", per ripasso.

---

## 1. Cos'è BizQuery davvero (e cosa gira su AWS)

BizQuery **è un'API** (un server web interrogabile), non un sito da guardare. Espone
"endpoint" HTTP ordinabili come piatti di un menù: `/ask` (fai una domanda in italiano
→ risposta), `/health`, `/ask-graph`, `/approve`. Chiunque (un frontend, un altro
programma, `curl`) manda una richiesta e ottiene un JSON.

Su AWS girano **2 container (scatole) Docker** sulla EC2:
- **app** = backend FastAPI/Python + un frontend minimale (paginetta HTML servita
  dall'endpoint `/`).
- **db** = Postgres coi dati.

L'app è **read-only** di proposito (il guardrail blocca INSERT/UPDATE/DELETE): serve a
*interrogare* i dati, non a inserirli. È un tool di Business Intelligence conversazionale.

**Gira anche a PC spento**: vive sulla EC2 (macchina Amazon accesa 24/7), non sul PC
dell'utente. Il PC serviva solo a crearla/configurarla. È il senso del deploy cloud.

**Non si trova su Google**: ha solo un IP numerico, nessun dominio indicizzato. È
raggiungibile solo da chi conosce l'indirizzo `http://35.152.199.210:8000`.

---

## 2. Il database — sganciarsi dalla mentalità Supabase

**Un database Postgres è solo un programma che gira su una macchina.** "Dove" è il DB =
"su quale macchina gira quel programma". Supabase NON era speciale: era "un Postgres che
gira sui server di Supabase", ci si collegava col suo indirizzo. Il Postgres su EC2 è la
stessa cosa, con indirizzo `db` (stessa macchina) invece di `db.xxx.supabase.co`.

Il collegamento avviene tramite il **DATABASE_URL** — una "ricetta di connessione" con 5
ingredienti:
```
postgresql://UTENTE:PASSWORD@INDIRIZZO:PORTA/NOME_DATABASE
```
- Con **Supabase**: la stringa te la dà pronta la dashboard (per questo sembrava magia).
- Con il **Postgres su EC2**: l'hai composta tu (valori scelti nel docker-compose.yml:
  utente `bizquery_app`, host `db`, porta 5432, db `bizquery`).
- Con il **DB di un'azienda cliente**: te la dà il loro IT.

**Stessa app, database diverso = si cambia solo il DATABASE_URL.** L'app non cambia.

**Supabase vs Postgres-su-EC2**: sotto è lo STESSO Postgres. Supabase = Postgres +
comodità già pronte (dashboard grafica, API auto-generate, auth, backup). EC2 = Postgres
nudo, gestisci tutto tu. Scelto il secondo APPOSTA, per capire cosa Supabase nasconde.

---

## 3. Come un'AZIENDA userebbe BizQuery (esempio reale)

Azienda "TechShop" (e-commerce, 50 dipendenti) ha già un gestionale con dietro Postgres
pieno di dati veri. Il capo vendite Marco non sa scrivere SQL. Tu gli vendi BizQuery:
1. **Deployi** BizQuery su una macchina (EC2).
2. Cambi **una riga**: il `DATABASE_URL` punta al DB di TechShop (con utente **read-only**).
3. **Adatti lo schema** mandato a Gemini perché conosca le tabelle di TechShop.
4. Marco apre il browser su `https://bi.techshop.com` e scrive "quanto abbiamo venduto
   ieri?" → Gemini traduce in SQL → guardrail controlla → esegue sul DB vero → "12.450€
   su 87 ordini".

**Come la usa l'azienda**: tramite il BROWSER, andando all'indirizzo dove l'hai
deployato. Non installano nulla. Tu hai scritto il codice; loro lo collegano ai LORO dati.

**I nuovi dati** NON entrano da BizQuery: entrano dal gestionale dell'azienda (che scrive
nel DB). BizQuery legge il DB dal vivo → vede sempre i dati aggiornati in automatico.

### Collegare BizQuery al DB di un cliente — procedura
1. Chiedi al loro IT i 5 dati del DATABASE_URL.
2. Chiedi un **utente READ-ONLY** (BizQuery deve solo leggere; buona pratica di sicurezza).
3. Metti il DATABASE_URL come **segreto** (SSM/env, MAI nel codice/GitHub) — stesso
   pattern della chiave Gemini.
4. Adatta lo schema per Gemini.
5. Concorda l'accesso di rete/firewall col loro IT (spesso il DB non accetta connessioni
   da fuori).

---

## 4. Fare un SaaS con AUTH senza Supabase

L'autenticazione non è magia di Supabase, è codice scrivibile ovunque. I pezzi:
1. **Tabella utenti** (email, password CIFRATA, a quale azienda/tenant appartiene).
2. **Endpoint `/login`**: verifica email+password → restituisce un **token** (biglietto
   temporaneo che prova il login).
3. **Ogni richiesta** porta il token → BizQuery lo valida → sa chi sei e di che azienda →
   mostra solo i tuoi dati (usando il `tenant_id` che BizQuery HA GIÀ + la RLS).
4. Il token **scade** dopo un po'.

Supabase dava i punti 1-4 pronti. Senza, li scrivi tu con librerie standard (es. Python:
`passlib` per le password, `PyJWT` per i token). BizQuery ha già `tenant_id` + RLS: manca
solo il "cancello d'ingresso" (login) davanti. Aggiungerlo = trasformarlo in vero SaaS
multi-azienda. **Ottimo prossimo esercizio** per staccarsi da Supabase.

---

## 5. MCP — dare strumenti a un'AI (esempi aziendali su BizQuery)

MCP (Model Context Protocol, standard Anthropic) = modo uniforme per dare **tool** a un
agente AI, così può FARE azioni, non solo parlare. Il server MCP di BizQuery
(`app/mcp_server/server.py`) espone 3 tool: `run_query`, `mask_email`, `send_notification`.

**Come lo colleghi a un'AI** (es. Claude Desktop): in un file di config (es.
`claude_desktop_config.json`) registri il server MCP. L'AI lo avvia, "vede" i tool, e
durante la chat decide DA SOLO quando usarli. È come dare le chiavi degli attrezzi a un
dipendente.

**Esempi aziendali (su BizQuery):**
- `run_query`: manager chiede a Claude "confronta le vendite di questo trimestre con lo
  scorso" → Claude chiama `run_query` due volte, confronta, scrive un mini-report. Nessun
  SQL scritto a mano.
- `mask_email`: "dammi i clienti che si sono lamentati" → l'AI prende i dati ma passa le
  email da `mask_email` → il supporto vede `m***@gmail.com` (GDPR rispettato in automatico).
- `send_notification`: "avvisami se un cliente fa un ordine sopra 10.000€" → l'AI monitora
  con `run_query` e quando succede chiama `send_notification` (email/Slack al manager).

Visione: AI + tuoi tool MCP = un "analista dati virtuale" che interroga, rispetta la
privacy, avvisa. Il salto da "chatbot che parla" a "agente che lavora". Già costruito (L3).

NB supporto: MCP funziona bene coi client che lo supportano (Claude Desktop/Code, API
Anthropic). GPT storicamente usava function calling proprio; il concetto è identico.

---

## 6. Docker, registry, "scatole"

**Docker** impacchetta l'app (codice + Python + librerie + config) in una **scatola
sigillata** (immagine) che gira IDENTICA ovunque (Windows, EC2 Linux, PC del collega).
Uccide il "funziona sul mio computer". Flusso:
```
CODICE (GitHub) --docker build--> IMMAGINE (registry ghcr.io) --docker pull--> gira su AWS
```
- **GitHub = la fonte** (codice sorgente, backup, storia, base per ricostruire l'immagine
  e per il CI/CD futuro).
- **Registry (ghcr.io) = il magazzino** delle immagini (scatole pronte). `docker push`
  carica, `docker pull` scarica. È il punto d'incontro tra il PC che builda e la EC2 che
  esegue. Altri registry: Docker Hub (il più famoso, ma ha rate limit sui pull gratis),
  AWS ECR (per la versione advanced).

**Perché ghcr.io e non Docker Hub**: il codice è già su GitHub (tutto in un posto), auth
già pronta col token GitHub, nessun rate limit fastidioso.

**Quante scatole ora**: 2 (app+frontend minimale, database). Comunicano via rete privata
Docker (l'app chiama il db per nome `db`). Il `docker-compose.yml` è il direttore
d'orchestra (quali scatole, in che ordine, come si collegano).

**Come divide le scatole un SENIOR**: UNA responsabilità per scatola. Versione seria:
frontend | backend/API | database | reverse proxy (Nginx/Caddy per HTTPS) | cache (Redis) |
worker. Perché: scala indipendente, aggiorni un pezzo alla volta, se uno si rompe gli altri
reggono, team paralleli. La versione advanced di BizQuery separerebbe il frontend +
aggiungerebbe il reverse proxy per HTTPS.

---

## 7. AWS vs Supabase (perché le aziende scelgono AWS) + costi + sicurezza

Non è "AWS serio, Supabase per principianti" (molte startup usano Supabase in prod). Ma
le aziende grandi/regolamentate scelgono AWS per:
1. **Controllo/personalizzazione** (200+ servizi combinabili vs menù fisso di Supabase).
2. **Fiducia** (Amazon esiste da 20 anni; una banca si fida più che di una startup).
3. **Conformità** (certificazioni HIPAA/SOC2/ISO, data center in nazioni specifiche).
4. **Scala enorme** con controllo fine.
5. **"Abbiamo già tutto su AWS"** (un posto, una fattura, un team).
Si sceglie **Supabase** per: startup, MVP, velocità di sviluppo > controllo.

**Costi (indicativi):**
- Supabase: piano free reale (fino a ~500MB DB, ~50k utenti auth/mese); poi ~25$/mese Pro.
  Prezzo **pacchettizzato e prevedibile**.
- AWS: free tier 12 mesi (EC2 750h) + alcuni servizi sempre-gratis con limiti; poi paghi
  **ogni cosa separatamente** (ore macchina, GB storage, GB traffico...). Potente ma
  **imprevedibile** se non stai attento → per questo il budget alert.
Differenza chiave: Supabase = prezzo prevedibile; AWS = a consumo, granulare.

**Sicurezza (modello di responsabilità condivisa):**
- Supabase: sicurezza infrastruttura INCLUSA (tu pensi solo alla tua app). Difficile
  sbagliare, meno controllo.
- AWS: sicurezza è RESPONSABILITÀ TUA (firewall/security group, accessi SSH, segreti — come
  fatto nel deploy). AWS protegge il data center, TU proteggi la macchina. Più potente, ma
  se lasci un buco è colpa tua. Le aziende con team di sicurezza preferiscono questo controllo.

---

## 8. Dominio + HTTPS + Google (per rendere l'app "vera su internet")

### FASE A — Dominio (da IP a `tuonome.it`)
1. Compra un dominio da un registrar (Cloudflare/Namecheap/Aruba, ~10€/anno).
2. Nelle impostazioni DNS crea un **record "A"**: `tuonome.it → 35.152.199.210`.
3. Aspetti la propagazione (minuti-ore).
4. `http://tuonome.it:8000` risponde.

### FASE B — HTTPS (il "lucchetto")
Il lucchetto = **connessione cifrata**. Con `http://` i dati viaggiano in chiaro (come una
cartolina leggibile dagli intermediari); con `https://` viaggiano cifrati (cassaforte).
Serve per sicurezza (password/dati protetti), fiducia (i browser marchiano `http` come "Non
sicuro"), ed è ormai obbligo di fatto.
5. Installa un **reverse proxy** sulla EC2 — **Caddy** è il più facile (fa HTTPS da solo).
6. Configuralo: riceve su 443 (HTTPS), gira le richieste all'app sulla 8000, ottiene un
   **certificato gratis da Let's Encrypt** (ottenuto in SECONDI, si rinnova da solo ogni 90gg).
7. Apri la porta **443** nel security group AWS.
8. `https://tuonome.it` col lucchetto, senza più `:8000`.

### FASE C — Google Search Console (indicizzazione)
9-14. Registri il dominio su Search Console, verifichi la proprietà (record DNS "TXT"),
invii la sitemap, aspetti che Google indicizzi.
⚠️ NB: un'API/tool interno come BizQuery di solito NON si mette su Google (non è contenuto
da cercare). FASE A+B sono l'esercizio utile; FASE C serve per siti/blog pubblici.
