-- BizQuery v0 — schema minimo multi-tenant con RLS
-- Sottoinsieme del modello a regime (vedi PROJECT.md): solo le 3 tabelle
-- necessarie a v0. RLS attiva su customers e orders da subito.
--
-- Decisione chiave: RLS isola per tenant a livello DB. L'app imposta
-- `app.tenant_id` a inizio sessione/transazione con SET LOCAL, e le policy
-- filtrano su current_setting('app.tenant_id'). Senza questo, un bug applicativo
-- che dimentica il WHERE tenant_id NON causa leak cross-tenant: il DB lo blocca.

-- Pulizia idempotente (per re-run in dev). DROP in ordine inverso alle FK.
DROP TABLE IF EXISTS query_logs CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS customers CASCADE;
DROP TABLE IF EXISTS tenants CASCADE;

-- Un ruolo applicativo NON superuser: RLS viene bypassata dai superuser e dai
-- table owner (BYPASSRLS). L'app deve connettersi come questo ruolo perché le
-- policy siano davvero applicate.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bizquery_app') THEN
    CREATE ROLE bizquery_app LOGIN PASSWORD 'bizquery_app_pw' NOBYPASSRLS;
  END IF;
END
$$;

CREATE TABLE tenants (
    id    SERIAL PRIMARY KEY,
    name  TEXT NOT NULL
);

CREATE TABLE customers (
    id         SERIAL PRIMARY KEY,
    tenant_id  INTEGER NOT NULL REFERENCES tenants(id),
    name       TEXT NOT NULL,
    email      TEXT NOT NULL,          -- PII: da mascherare a livello app (Livello 3)
    country    TEXT NOT NULL
);

CREATE TABLE orders (
    id            SERIAL PRIMARY KEY,
    tenant_id     INTEGER NOT NULL REFERENCES tenants(id),
    customer_id   INTEGER NOT NULL REFERENCES customers(id),
    total_amount  NUMERIC(12, 2) NOT NULL,
    status        TEXT NOT NULL,        -- 'pending' | 'paid' | 'cancelled' | 'refunded'
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- query_logs (Livello 3 — data flywheel): registra ogni run dell'agente.
-- Alimenta due cose: l'analisi (cosa è stato chiesto, cosa ha funzionato) e il
-- flywheel (le run riuscite diventano few-shot per migliorare il planner).
-- A differenza delle tabelle business, l'app QUI scrive (INSERT) — è la sua
-- tabella operativa, non dati che l'agente interroga per rispondere.
CREATE TABLE query_logs (
    id             SERIAL PRIMARY KEY,
    tenant_id      INTEGER NOT NULL REFERENCES tenants(id),
    question       TEXT NOT NULL,
    generated_sql  TEXT,
    guardrail_verdict TEXT,        -- approved | rejected | needs_human
    review_verdict TEXT,           -- ok | retry_needed
    retry_count    INTEGER NOT NULL DEFAULT 0,
    was_flagged    BOOLEAN NOT NULL DEFAULT FALSE,  -- ha richiesto human review
    human_approved BOOLEAN,        -- esito revisione umana, se avvenuta
    success        BOOLEAN NOT NULL DEFAULT FALSE,   -- ha prodotto una risposta valida
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_customers_tenant ON customers(tenant_id);
CREATE INDEX idx_orders_tenant    ON orders(tenant_id);
CREATE INDEX idx_orders_customer  ON orders(customer_id);
CREATE INDEX idx_query_logs_tenant ON query_logs(tenant_id);

-- ---------------------------------------------------------------------------
-- Row-Level Security
-- ---------------------------------------------------------------------------
-- ENABLE attiva le policy; FORCE le applica anche al table owner (utile perché
-- in dev spesso si è owner). La policy confronta la colonna tenant_id con il
-- valore di sessione app.tenant_id. current_setting(..., true) => NULL se non
-- impostato, così una connessione senza tenant impostato non vede NULLA
-- (NULL = INTEGER è NULL → riga esclusa) invece di sollevare errore.

ALTER TABLE customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE customers FORCE  ROW LEVEL SECURITY;
ALTER TABLE orders    ENABLE ROW LEVEL SECURITY;
ALTER TABLE orders    FORCE  ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_customers ON customers
    USING (tenant_id = current_setting('app.tenant_id', true)::INTEGER);

CREATE POLICY tenant_isolation_orders ON orders
    USING (tenant_id = current_setting('app.tenant_id', true)::INTEGER);

-- query_logs: stessa isolation per tenant. Serve WITH CHECK oltre a USING perché
-- qui si fa anche INSERT: WITH CHECK impedisce di inserire un log per un tenant
-- diverso da quello di sessione (non basta filtrare in lettura).
ALTER TABLE query_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE query_logs FORCE  ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_query_logs ON query_logs
    USING      (tenant_id = current_setting('app.tenant_id', true)::INTEGER)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::INTEGER);

-- Il ruolo app può leggere (v0 è read-only) ma non scrivere sui dati business.
GRANT SELECT ON customers, orders, tenants TO bizquery_app;
-- Eccezione: su query_logs l'app scrive i propri log (INSERT) e li rilegge
-- (SELECT) per il flywheel. USAGE sulla sequence per il SERIAL id.
GRANT SELECT, INSERT ON query_logs TO bizquery_app;
GRANT USAGE, SELECT ON SEQUENCE query_logs_id_seq TO bizquery_app;
GRANT USAGE ON SCHEMA public TO bizquery_app;
