"""Model router (Livello 2) — sceglie il modello Gemini in base alla complessità.

Funzione DETERMINISTICA, non LLM: decidere quale modello usare non deve costare
una chiamata al modello. Regola su segnali osservabili.

Da PROJECT.md: Flash (lite) per planner/reviewer/report e query semplici; Pro per
SQL executor su task complessi (join multipli, aggregazioni, window functions).

Perché scrivibile ora (senza DB): è logica pura su testo. Riceve la domanda (e/o
un plan futuro) e ritorna il nome del modello. Il grafo L2 la userà prima del nodo
sql_executor.

Nota free tier: se il tier corrente non espone un "Pro" gratis, il router resta
valido come design — basta rimappare TIER_PRO su un modello disponibile. La
DECISIONE (semplice vs complesso) è separata dal NOME del modello di proposito.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass

# Nomi modello configurabili da env: la logica di routing non deve cambiare se
# cambiano i nomi dei modelli sul free tier.
TIER_FLASH = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")
TIER_PRO = os.environ.get("GEMINI_MODEL_PRO", "gemini-2.5-flash")

# Segnali di complessità nella domanda in NL. Non è un parser SQL: sono euristiche
# su cosa l'utente sta chiedendo. Deliberatamente conservative: nel dubbio Flash
# (più economico); si sale a Pro solo con segnali chiari di query articolata.
_COMPLEX_SIGNALS = [
    r"\bper (ogni|ciascun)\b",          # group by implicito
    r"\bmedia\b|\bmediana\b|\bpercentile\b",
    r"\btrend\b|\bnel tempo\b|\bmese per mese\b|\bcrescita\b",  # window/serie temporali
    r"\bconfronta\b|\brispetto a\b|\bvariazione\b",
    r"\btop \d+\b|\bclassifica\b|\branking\b",
    r"\bincrocia\b|\bcombinando\b|\binsieme a\b",  # join multipli
    r"\bpercentuale\b|\bsu(l| ) totale\b",
]
_COMPLEX_RE = [re.compile(p, re.IGNORECASE) for p in _COMPLEX_SIGNALS]


@dataclass(frozen=True)
class RouteDecision:
    model: str
    complexity: str   # "simple" | "complex"
    reason: str


def route_model(question: str, plan: str | None = None) -> RouteDecision:
    """Sceglie il modello. `plan` opzionale (dal planner L2): se presente, si
    valutano insieme domanda + plan."""
    text = f"{question} {plan or ''}"

    hits = [p.pattern for p in _COMPLEX_RE if p.search(text)]
    if hits:
        return RouteDecision(
            model=TIER_PRO,
            complexity="complex",
            reason=f"segnali di query articolata: {len(hits)} match",
        )

    return RouteDecision(
        model=TIER_FLASH,
        complexity="simple",
        reason="nessun segnale di complessità: conteggio/aggregazione semplice",
    )
