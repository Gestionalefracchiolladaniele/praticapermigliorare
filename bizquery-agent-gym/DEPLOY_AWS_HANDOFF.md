# Deploy AWS — HANDOFF (STORICO — deploy COMPLETATO il 2026-07-12 ✅)

> ⚠️ STORICO: il deploy è FINITO. L'app è live su `http://35.152.199.210:8000`
> (`/ask` risponde da IP pubblico, `/health`→ok, DB seedato). I "2 fix" più sotto
> sono stati RISOLTI (vedi PROJECT.md, sezione deploy AWS del 2026-07-12, per la
> lezione sul merge delle liste in Docker Compose). Questo file resta come
> riferimento ai dati operativi (IP, chiave, SSM/IAM, comandi). Per rifare/gestire
> il deploy usa i comandi qui sotto. Debiti aperti ancora validi: vedi in fondo
> ("Debiti aperti") — chiave Gemini da rigenerare, EC2 da terminare quando non serve.

## Dati operativi (copiali quando riprendi)

- **EC2**: t3.micro, Amazon Linux 2023, regione **Milano `eu-south-1`**
- **IP pubblico**: `35.152.199.210` ⚠️ **è dinamico**, cambia se la macchina si
  riavvia — riverificalo in console EC2 prima di usarlo.
- **Chiave SSH**: `F:\donwloads\bizquery.chiave.pem` (nome esatto, con "donwloads")
- **Utente SSH**: `ec2-user`
- **Comando SSH**:
  `ssh -i "F:\donwloads\bizquery.chiave.pem" ec2-user@35.152.199.210`
- **Account AWS ID**: `799374460640`
- **Immagine**: `ghcr.io/gestionalefracchiolladaniele/bizquery:latest` (pubblica su ghcr.io)

## Setup di contesto già fatto (per non rifarlo)

- **Budget alert AWS** "zero spend" creato (avvisa via email appena la spesa supera
  0,01 USD) — rete di sicurezza costi ATTIVA.
- **Login a ghcr.io** fatto con un **GitHub Personal Access Token classic** (scope
  `write:packages`, scadenza 90gg dal 2026-07-11). Serve SOLO per ri-pushare
  l'immagine: `echo $TOKEN | docker login ghcr.io -u Gestionalefracchiolladaniele --password-stdin`.
  Il pull invece è anonimo (pacchetto pubblico).
- **AWS CLI** è già preinstallato su Amazon Linux 2023 (non serve installarlo).
- Il **warning SSH "post-quantum key exchange"** ad ogni connessione è INNOCUO, ignoralo.

## ⚠️ Codice NON ancora committato su git
I file nuovi/modificati di questa sessione NON sono su GitHub (repo
`Gestionalefracchiolladaniele/praticapermigliorare`, git root = `F:\sicurezzacapire`):
`docker-compose.prod.yml`, `DEPLOY_AWS_HANDOFF.md`, `PROJECT.md` (modificato).
Da committare quando si vuole (attenzione: NON committare mai `.env` né chiavi —
verificare `.gitignore` prima; il repo git-root ha anche `envchiaveesempio` in chiaro).

## Cosa è GIÀ FATTO e verificato dal vivo ✅

1. **Immagine** buildata in locale + pushata su ghcr.io (pacchetto pubblico → pull anonimo ok).
2. **EC2** creata e in esecuzione. **Security group**: 22 (solo mio IP) + 8000 (pubblica). 5432 NON aperta nel SG.
3. **Docker + compose** installati sulla EC2, attivi al boot, ec2-user nel gruppo docker.
4. **File sulla EC2** (nella home `~/`): `docker-compose.yml`, `docker-compose.prod.yml`, `schema.sql`.
   - ⚠️ Questi sono stati copiati con `scp` PRIMA dei fix qui sotto → **vanno ri-copiati** (vedi sotto).
5. **Segreti come in prod (SSM + IAM)** — il pezzo avanzato, tutto verificato:
   - Chiave Gemini in **SSM Parameter Store** SecureString: `/bizquery/gemini-api-key`
   - **IAM role** `bizquery-ec2-role` attaccato alla EC2
   - **Policy custom least-privilege** `bizquery-ssm-read` (solo `ssm:GetParameter*` su
     `parameter/bizquery/*` + `kms:Decrypt` con Condition `kms:ViaService=ssm.eu-south-1.amazonaws.com`)
   - Verificato: la macchina legge+decifra la chiave col SOLO ruolo, zero segreti su disco.
6. **Script `~/deploy.sh` sulla EC2**: legge Gemini da SSM → genera `~/.env` (chmod 600) →
   `docker compose ... pull` → `up -d`. **Eseguito**: i container sono partiti (app + db).

## Cosa RESTA (riprendi da qui) ⚠️

### FIX 1 — porta 5432 esposta (già corretto nel file locale, da ridistribuire)
Nell'output di `up -d` la 5432 risultava `0.0.0.0:5432->5432/tcp` (esposta su tutte le
interfacce). Causa: in Docker Compose le liste `ports` si FONDONO col base, quindi
`ports: []` NON toglie la `5432:5432`. **Già corretto** in `docker-compose.prod.yml`
locale: ora la lega a `127.0.0.1:5432:5432` (solo loopback). Il security group AWS
comunque non apre la 5432, quindi da internet il DB era già irraggiungibile — ma la
config va pulita (difesa a strati).
**Da fare**: ri-copiare l'override aggiornato sulla EC2 e rifare `up -d`:
```
scp -i "F:\donwloads\bizquery.chiave.pem" f:\sicurezzacapire\bizquery-agent-gym\docker-compose.prod.yml ec2-user@35.152.199.210:~/
ssh -i "F:\donwloads\bizquery.chiave.pem" ec2-user@35.152.199.210 "~/deploy.sh"
```
Poi verificare: `docker compose ... ps` NON deve più mostrare `0.0.0.0:5432`, ma
`127.0.0.1:5432` (o niente).

### FIX 2 — verificare /health e l'app
Al primo avvio `/health` rispondeva vuoto MA era solo perché l'app era "Up less than a
second" (non ancora pronta). L'endpoint `/health` ESISTE (`app/main.py:48`). Endpoint
disponibili: `/health`, `/` (UI web), `/ask`, `/ask-graph`, `/approve`.
**Da fare (E5-E6)**: dopo il FIX 1, con l'app su da qualche secondo:
```
# dal PC o via ssh sulla macchina:
curl http://35.152.199.210:8000/health          # deve rispondere ok
```
Poi il **SEED del DB** (una tantum, popola 30 cust/100 ord/2 tenant):
```
ssh -i "F:\donwloads\bizquery.chiave.pem" ec2-user@35.152.199.210 \
  "docker compose -f ~/docker-compose.yml -f ~/docker-compose.prod.yml run --rm app python -m app.db.seed"
```
Infine aprire nel browser: **http://35.152.199.210:8000/** → fare una domanda,
verificare risposta + guardrail + SQL. Questo chiude L1 Step 7.

## Debiti aperti (cleanup, dopo che tutto gira)
- ⚠️ **Rigenerare la chiave Gemini**: quella in SSM (`AIzaSyBz...`) è compromessa (comparsa
  in chiaro). Rigenerarla su aistudio.google.com/apikey, poi aggiornare il parametro SSM:
  `aws ssm put-parameter --name /bizquery/gemini-api-key --value NUOVA --type SecureString --overwrite --region eu-south-1`
- **TERMINARE la EC2** quando non serve (free tier: 1 istanza, 750h/mese — se lasciata
  accesa consuma le ore). In console EC2 → istanza → Operazioni → Stato istanza → Termina.
- Cancellare `F:\sicurezzacapire\envchiaveesempio` (chiavi in chiaro, gitignorato).

## Nota futura — versione "advanced" (senior, coi crediti AWS)
Vedi sezione "BizQuery advanced" in cima a `PROJECT.md`: dopo questo deploy semplice,
rifare con Terraform + ECS Fargate + RDS + Secrets Manager + ALB/HTTPS + CI/CD, usando
i ~120 USD di crediti AWS gratuiti. Da fare a strati, su richiesta.
