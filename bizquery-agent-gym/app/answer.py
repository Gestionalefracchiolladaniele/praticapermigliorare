"""Formatta il risultato della query in linguaggio naturale (pezzo dello step 4).

v0: le domande producono un numero (count/sum) o poche righe. Qui SI FORMATTA in
modo deterministico, senza un secondo giro di LLM: per numeri è gratis, istantaneo
e testabile. Il report generato da LLM (piu' discorsivo) e' roba da Livello 3
(answer/report agent). Questo modulo e' gia' isolato cosi' a regime diventa quel
nodo senza spostare codice.

Regola di forma: se il risultato e' un singolo scalare -> frase con la domanda +
il valore. Se sono piu' righe -> le elenca compatte. Se vuoto -> lo dice.
"""
from __future__ import annotations

from decimal import Decimal


def _fmt_value(v) -> str:
    """Numeri interi senza decimali, i float/Decimal con 2 decimali."""
    if isinstance(v, Decimal):
        v = float(v)
    if isinstance(v, float):
        # 68786.45 -> "68786.45", ma 15.0 -> "15"
        if v.is_integer():
            return str(int(v))
        return f"{v:.2f}"
    return str(v)


def format_answer(question: str, rows: list) -> str:
    """rows = lista di liste (come le ritorna main.ask). Ritorna una frase IT."""
    if not rows:
        return f"Nessun risultato per: «{question}»."

    # Caso tipico v0: una riga, una colonna (un count o una sum).
    if len(rows) == 1 and len(rows[0]) == 1:
        val = _fmt_value(rows[0][0])
        return f"Risposta a «{question}»: {val}."

    # Una riga, piu' colonne: elenca i valori.
    if len(rows) == 1:
        vals = ", ".join(_fmt_value(c) for c in rows[0])
        return f"Risposta a «{question}»: {vals}."

    # Piu' righe: le mostra compatte (fino a 20 per non esplodere).
    shown = rows[:20]
    lines = "; ".join(
        " | ".join(_fmt_value(c) for c in r) for r in shown
    )
    suffix = "" if len(rows) <= 20 else f" (+{len(rows) - 20} righe)"
    return f"Risultati per «{question}» ({len(rows)} righe): {lines}{suffix}."
