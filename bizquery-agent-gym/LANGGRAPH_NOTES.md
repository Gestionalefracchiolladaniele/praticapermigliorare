# Note di studio LangGraph — preparazione Livello 2 (NON è ancora codice del grafo)

> Perché questo file: il metodo di PROJECT.md dice che per i framework con
> convenzioni precise (LangGraph) scriviamo da zero **ma dopo aver guardato come
> la doc ufficiale struttura il pattern**, così il codice somiglia a qualcosa di
> riconoscibile da un senior invece di essere inventato. Queste sono quelle note.
> Convenzioni verificate sulla doc ufficiale (docs.langchain.com, luglio 2026).
>
> **Non si scrive il grafo finché v0 non è FATTO** (regola dei livelli). Questo
> file serve a partire col pattern giusto quando ci arriviamo.

## Il modello mentale (5 pezzi)

1. **State** — un oggetto condiviso che attraversa tutti i nodi. Ogni nodo lo
   legge e ne ritorna un aggiornamento parziale.
2. **Nodi** — funzioni `state -> dict`. Il dict è l'aggiornamento allo state.
3. **Edge** — fissi (`add_edge`) o condizionali (`add_conditional_edges` + una
   funzione di routing che ritorna il nome del prossimo nodo).
4. **START / END** — costanti che marcano ingresso e uscita.
5. **Compile + checkpointer** — `builder.compile(checkpointer=...)`; serve un
   checkpointer per persistere lo stato → indispensabile per `interrupt`.

## Convenzioni con firme corrette

### State — TypedDict + reducer, oppure Pydantic
```python
from typing import Annotated, TypedDict
import operator

class State(TypedDict):
    messages: Annotated[list, operator.add]  # reducer: concatena invece di sovrascrivere
    retry_count: int                          # senza Annotated: sovrascrive
```
- **Reducer** (`Annotated[tipo, funzione]`): quando due aggiornamenti toccano lo
  stesso campo, il reducer dice come combinarli (es. `operator.add` per liste).
  Senza reducer, l'ultimo scrive vince.
- PROJECT.md prevede `AgentState` **Pydantic** — supportato: `class State(BaseModel)`.
  Pydantic dà validazione dei tipi, TypedDict è più leggero. Per noi Pydantic è
  coerente con lo stack (già usiamo pydantic in v0).

### Nodo — funzione che ritorna l'aggiornamento
```python
def sql_executor(state: State) -> dict:
    sql = generate_sql(state["question"], state["tenant_id"])
    return {"sql_candidate": sql}   # aggiorna SOLO questo campo
```
Il nodo NON muta `state` in place: ritorna un dict coi campi da aggiornare.

### Edge fissi e condizionali
```python
from langgraph.graph import START, END, StateGraph

builder = StateGraph(State)
builder.add_node("sql_executor", sql_executor)
builder.add_node("guardrail", guardrail_node)

builder.add_edge(START, "sql_executor")     # ingresso
builder.add_edge("sql_executor", "guardrail")

# routing condizionale: la funzione ritorna il NOME del prossimo nodo (o END)
def route_after_guardrail(state: State) -> str:
    v = state["guardrail_verdict"]
    if v == "rejected":
        return END
    if v == "needs_human":
        return "human_approval"
    return "db_executor"

builder.add_conditional_edges("guardrail", route_after_guardrail)
```

### interrupt — human-in-the-loop (il pezzo nuovo del Livello 3)
```python
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import InMemorySaver

def human_approval(state: State) -> dict:
    decision = interrupt({"sql": state["sql_candidate"], "reason": "query rischiosa"})
    return {"human_approved": bool(decision)}

graph = builder.compile(checkpointer=InMemorySaver())  # checkpointer OBBLIGATORIO
config = {"configurable": {"thread_id": "run-123"}}

graph.invoke({...}, config=config)          # gira fino all'interrupt, poi si ferma
graph.invoke(Command(resume=True), config=config)  # riprende dallo stesso checkpoint
```
- **Serve un checkpointer** (persiste lo stato) e un **thread_id** (cursore della
  sessione). Senza, `interrupt` non può sospendere/riprendere.
- `interrupt(x)` espone `x` a chi ha chiamato (una UI); `Command(resume=valore)`
  fa sì che `valore` diventi il ritorno di `interrupt` dentro il nodo.
- In produzione il checkpointer non è in-memory ma su Postgres (`langgraph-checkpoint-postgres`)
  — abbiamo già Postgres, quindi riusabile.

## Mappatura sul NOSTRO grafo (da PROJECT.md)

Lo pseudo-grafo di PROJECT.md tradotto nelle convenzioni sopra:

| Nodo PROJECT.md | Tipo LangGraph | Ritorna nello state |
|-----------------|----------------|---------------------|
| memory | nodo (no LLM) | `chat_history` |
| planner | nodo (Gemini Flash) | `plan` — o interrupt se ambigua |
| model router | funzione routing | sceglie Flash/Pro (non è un nodo) |
| sql_executor | nodo (Gemini) | `sql_candidate` |
| guardrail | nodo (il nostro `check_sql`!) | `guardrail_verdict` |
| cost_guardian | nodo | verdetto budget |
| human-in-the-loop | nodo con `interrupt` | `human_approved` |
| db_executor | nodo (il nostro `tenant_session`!) | `query_result` |
| reviewer | nodo (Gemini Flash) | `review_verdict` |
| answer | nodo (il nostro `format_answer`!) | `final_answer` |

**Punto chiave**: il grafo del Livello 2 NON butta v0. `check_sql`,
`tenant_session`, `generate_sql`, `format_answer` diventano il *corpo* dei nodi.
LangGraph aggiunge l'orchestrazione (stato, routing, retry, interrupt) sopra
funzioni che abbiamo già scritto e testato. Ecco perché v0 va finito prima.

### Il retry loop (criterio "v1 FATTO")
```python
def route_after_review(state: State) -> str:
    if state["review_verdict"] == "ok":
        return "answer"
    if state["retry_count"] < 2:
        return "sql_executor"   # ritenta: genera nuovo SQL
    return END                   # arreso dopo 2 retry, log per flywheel

builder.add_conditional_edges("reviewer", route_after_review)
```
Il reviewer rifiuta → si torna a sql_executor con `retry_count` incrementato →
secondo tentativo. Questo è il caso che PROJECT.md chiede di dimostrare.

## Dipendenze da aggiungere (quando si parte col Livello 2)
```
langgraph
langgraph-checkpoint-postgres   # checkpointer su Postgres (già disponibile)
```
Non aggiunte ora a requirements.txt di proposito: v0 non le usa.

## Cosa verificare sul campo al Livello 2 (non deducibile dalla doc)
- Versione esatta di `langgraph` e nome import di `interrupt`/`Command` al momento
  del build (l'API si evolve: ricontrollare la doc allora, non fidarsi di queste note).
- Se il free tier Gemini regge il numero di chiamate del grafo (più nodi LLM per run).
