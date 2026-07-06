# Deploy AWS free tier — v0 (step 7)

> Note operative, non codice: il deploy usa il tuo account AWS via console/CLI.
> Bloccato finché lo step 6 (Docker) non è verificato in locale — l'app deve già
> girare in container prima di deployarla.

## Scelta consigliata: 1 EC2 `t3.micro` (free tier) con docker compose

**Perché non ECS Fargate + RDS**: sembrano la scelta "seria", ma **non** sono
free tier reali (Fargate si paga a vCPU/ora, RDS free tier è limitato e scade).
Per una palestra a costo zero, una singola istanza EC2 `t2.micro`/`t3.micro`
(750 ore/mese gratis per 12 mesi) che gira `docker compose up` è la strada
onesta: stesso artefatto del locale, zero servizi a pagamento nascosti.

## Passi

1. **Immagine**: build in locale, push su un registry.
   - Opzione free: **ECR** (500 MB/mese gratis) o Docker Hub pubblico.
   - `docker build -t bizquery .` → tag → push.
2. **EC2**: lancia una `t3.micro`, Amazon Linux 2023, security group che apre
   **solo** la porta 8000 (e 22 per SSH dal tuo IP). Niente 5432 aperta: il
   Postgres resta interno alla rete docker, non esposto a internet.
3. **Sull'istanza**: installa Docker + compose plugin, copia
   `docker-compose.yml`, crea un `.env` con `GEMINI_API_KEY`.
4. **Avvia**: `docker compose up -d`, poi una tantum
   `docker compose run --rm app python -m app.db.seed`.
5. **Verifica**: `curl http://<ip>:8000/health` e una POST a `/ask`.

## Sicurezza minima (anche in palestra)

- La `GEMINI_API_KEY` va nel `.env` sull'istanza, mai nell'immagine né nel repo.
- Postgres non esposto pubblicamente (porta 5432 non nel security group).
- L'app si connette come ruolo `bizquery_app` (RLS forzata), non come superuser.

## Criterio "step 7 fatto" (da PROJECT.md)

L'app containerizzata risponde a `/ask` da un URL AWS pubblico su dati reali,
con guardrail attivo. Non serve HA/scaling: è v0.

## Dopo v0

CI/CD (build+test+deploy automatici a ogni push) è **Livello 2**, non v0. Qui il
deploy resta manuale di proposito.
