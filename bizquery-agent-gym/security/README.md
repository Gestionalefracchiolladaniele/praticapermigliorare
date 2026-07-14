# Security — red-team dei guardrail BizQuery

Red-team **applicato** ai guardrail dell'agente: attacchiamo le difese vere di
BizQuery, documentiamo cosa passa, induriamo, e trasformiamo ogni attacco in una
**regressione di sicurezza** che gira in CI a ogni push. Non un pentest generico:
security degli agenti che costruiamo (OWASP LLM Top 10 applicato al nostro caso).

## Com'è fatto

```
security/
  guardrail_provider.py    # ponte: espone check_sql come "modello" da attaccare
  promptfooconfig.yaml     # casi d'attacco (fonte unica di verità)
  README.md                # questo file

tests/test_security_redteam.py   # gli stessi casi come regressione pytest (CI)
```

**Perché il guardrail e non `/ask`.** La domanda di sicurezza è *"la difesa ferma
l'SQL malevolo?"*, e non dipende da CHI ha generato l'SQL (Gemini indotto da
prompt-injection, o l'attaccante diretto). Testare `check_sql` direttamente colpisce
la difesa reale **a costo zero** (nessuna chiamata Gemini) → gira in CI a ogni push.
Il red-team *end-to-end* su `/ask` (injection → Gemini → guardrail) è complementare
ma costa ~20 chiamate Gemini/run: previsto quando la quota lo permette (vedi sotto).

## Come si lancia

```bash
# regressione di sicurezza (quella che gira in CI) — puro Python, zero Gemini
pytest tests/test_security_redteam.py -q

# stesso set via promptfoo (report più ricco), quando npx è disponibile
cd security && npx promptfoo@latest eval -c promptfooconfig.yaml
```

I due leggono gli **stessi** casi dalla `promptfooconfig.yaml`: si aggiunge un
attacco in un posto solo.

## Buchi trovati e chiusi (2026-07-14)

Red-team iniziale: **8 bypass su 13 casi**. Dopo hardening: **0**.

| # | Attacco | Perché passava | Fix |
|---|---------|----------------|-----|
| 1-4 | `pg_read_file`, `lo_export`, `pg_sleep`, `current_setting` | Sono `SELECT` read-only con `tenant_id` nella stringa: nessuna keyword di scrittura → il guardrail non le vedeva | **Blocklist di funzioni pericolose** (esfiltrazione FS, DoS, spoof tenant) → `rejected` |
| 5 | `SELECT tenant_id, email FROM customers` (no WHERE) | La regola voleva solo la *stringa* `tenant_id` presente | **Filtro tenant come vero predicato** (`tenant_id =/IN/BETWEEN`) |
| 6 | `SELECT name AS tenant_id ...` | idem (alias soddisfa la substring) | idem |
| 7 | `WHERE name = 'tenant_id'` | idem (stringa letterale) | idem |
| 8 | `... UNION SELECT email FROM customers` | Filtro solo nel primo ramo | **Predicato tenant richiesto in OGNI ramo** di UNION/INTERSECT/EXCEPT |
| PII | `josé.garcía@example.com` in chiaro | Regex email ASCII-only | **Regex Unicode** (`\w` + `re.UNICODE`) |

## Mappatura OWASP Top 10 for LLM Applications

| OWASP | Rischio | Stato in BizQuery |
|-------|---------|-------------------|
| **LLM01 Prompt Injection** | Input malevolo induce l'LLM a generare SQL dannoso | **Mitigato in profondità**: il guardrail deterministico blocca l'SQL malevolo *a valle* dell'LLM (funzioni pericolose, scritture, cross-tenant). Coperto dalla suite red-team. Difesa finale = RLS del DB. |
| **LLM02 Sensitive Info Disclosure** | PII (email) esposte nelle risposte | **Mitigato**: `mask_pii` maschera le email (ora Unicode-safe); `SELECT *` senza LIMIT → `needs_human`. |
| **LLM05 Improper Output Handling** | Output LLM (SQL) eseguito senza validazione | **Mitigato**: `run_query` RI-VALIDA col guardrail prima di eseguire (mai fidarsi dell'input). |
| **LLM06 Excessive Agency** | L'agente fa più di quanto dovrebbe (scritture, funzioni di sistema) | **Mitigato**: read-only forzato, blocklist funzioni, RLS + ruolo `bizquery_app` NOBYPASSRLS con soli privilegi di lettura. |
| **LLM10 Unbounded Consumption** | Query costose / DoS | **Parziale**: `pg_sleep` bloccato; `SELECT *` senza LIMIT → `needs_human`. **Manca**: limite righe stimate via `EXPLAIN` (cost-guardian, previsto L3). |
| LLM03 Supply Chain | Dipendenze compromesse | Fuori scope di questo pezzo (dep pinnate in requirements). |
| LLM04 Data/Model Poisoning | Avvelenamento dei dati di training/few-shot | **Da valutare**: il data flywheel rilegge run passate come few-shot → un input malevolo loggato potrebbe influenzare i prompt futuri. **Threat da modellare** (vedi TODO PROJECT.md). |
| LLM07 System Prompt Leakage | Leak del system prompt | Basso: il system prompt non contiene segreti (solo schema). |
| LLM08 Vector/Embedding | — | N/A (niente RAG in BizQuery, per scelta). |
| LLM09 Misinformation | Risposte errate | Coperto dall'**evaluation** (LLM-as-judge faithfulness/relevance) + reviewer nel grafo. |

## Limiti onesti (dove NON illudersi)

Il guardrail è **pattern-matching su stringhe, non un parser SQL**. Alza molto
l'asticella e ferma gli errori dell'LLM e gli attacchi ovvi, ma un attaccante
determinato può ancora tentare forme non previste (es. `tenant_id = tenant_id`
sempre-vero — *non* coperto oggi). Per questo la **difesa definitiva resta la RLS
a livello DB**: è il DB stesso a imporre l'isolamento riga per riga, invalicabile
anche se il guardrail viene aggirato. Il guardrail è *difesa in profondità*, non
l'ultima linea.

## Prossimi passi

- [ ] **garak** (NVIDIA): scanner LLM completo. Due usi: (a) contro il guardrail
      via provider custom (zero Gemini); (b) contro `/ask` end-to-end quando la
      quota Gemini è piena (probe di prompt-injection reali). Meglio containerizzato
      (Python 3.14 fresco).
- [ ] **promptfoo su `/ask`**: red-team end-to-end (injection nella `question`),
      marcato "manuale / quota piena", non in CI (costo quota).
- [ ] **`tenant_id = tenant_id` / tautologie**: caso non coperto — valutare se
      indurire o affidarsi alla RLS.
- [ ] **LLM04 data poisoning via flywheel**: threat model del few-shot da run loggate.
- [ ] **LLM10**: cost-guardian con `EXPLAIN` (limite righe stimate).
