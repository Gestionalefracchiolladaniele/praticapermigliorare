"""Observability con Langfuse (Livello 2).

Aggancia il grafo LangGraph a Langfuse: ogni run di `/ask-graph` diventa una
TRACE, ogni nodo del grafo uno SPAN, ogni chiamata Gemini una generation con
token/costo/latenza. Così una run smette di essere una scatola nera: dopo, nella
dashboard, vedi quale modello ha scelto il router, quanto ha impiegato ogni nodo,
quante volte è entrato in retry.

Convenzione Langfuse v4 (SDK su OpenTelemetry, verificata su 4.13.2):
  1. Si inizializza UN client Langfuse globale (`Langfuse(...)`), che legge le
     chiavi/host. Da lì in poi il resto dell'SDK usa quel client via `get_client()`.
  2. Il `CallbackHandler` (da `langfuse.langchain`) è "leggero": NON riceve le
     chiavi, le prende dal client globale. Lo si passa a
     `graph.invoke(..., config={"callbacks": [handler]})` e LangGraph lo chiama a
     ogni nodo → Langfuse costruisce l'albero trace/span da solo.

Principio di robustezza (come eval.py e flywheel.py): se le chiavi Langfuse non
sono nel .env, l'observability si DISATTIVA silenziosamente. `get_callback_handler()`
ritorna None e il grafo gira identico, senza tracing e senza errori. Nessun pezzo
del sistema dipende dalla presenza di Langfuse — è puro "sopra".
"""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

# Client Langfuse inizializzato una sola volta per processo (o None se disattivo).
# _INITIALIZED distingue "non ancora provato" da "provato e risultato None": senza
# questo flag ritenteremmo l'init a ogni chiamata anche quando sappiamo che le
# chiavi mancano.
_CLIENT = None
_INITIALIZED = False


def _is_configured() -> bool:
    """Le tre chiavi minime ci sono e sono valorizzate? Se no, tracing off."""
    return bool(
        os.environ.get("LANGFUSE_PUBLIC_KEY")
        and os.environ.get("LANGFUSE_SECRET_KEY")
        and os.environ.get("LANGFUSE_HOST")
    )


def get_client():
    """Ritorna il client Langfuse globale, o None se non configurato/non installato.

    Idempotente: inizializza al primo uso e poi riusa lo stesso client. Qualsiasi
    errore (chiavi errate, pacchetto assente, host irraggiungibile a init) NON deve
    rompere l'app: si degrada a None (nessun tracing)."""
    global _CLIENT, _INITIALIZED
    if _INITIALIZED:
        return _CLIENT

    _INITIALIZED = True
    if not _is_configured():
        _CLIENT = None
        return None

    try:
        from langfuse import Langfuse

        _CLIENT = Langfuse(
            public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
            secret_key=os.environ["LANGFUSE_SECRET_KEY"],
            host=os.environ["LANGFUSE_HOST"],
        )
    except Exception:  # noqa: BLE001 — l'observability non deve mai rompere l'app
        _CLIENT = None
    return _CLIENT


def get_callback_handler():
    """CallbackHandler da passare a graph.invoke(config={"callbacks": [handler]}).

    Ritorna None se Langfuse non è configurato o non importabile: chi chiama deve
    trattare None come "nessun tracing" e passare callbacks=[] (vedi main.py).

    In v4 il handler prende le chiavi dal client globale, quindi ci assicuriamo
    prima che il client sia inizializzato."""
    if get_client() is None:
        return None
    try:
        from langfuse.langchain import CallbackHandler

        return CallbackHandler()
    except Exception:  # noqa: BLE001
        return None


def flush() -> None:
    """Forza l'invio delle trace in coda. Langfuse bufferizza e invia in background;
    in un processo che risponde a una request e poi resta in idle va bene, ma è
    prudente chiamare flush() a fine run così la trace compare subito in dashboard
    (utile soprattutto in test/verifica manuale). No-op se tracing disattivo."""
    client = get_client()
    if client is not None:
        try:
            client.flush()
        except Exception:  # noqa: BLE001
            pass
