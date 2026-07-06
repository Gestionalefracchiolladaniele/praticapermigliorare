"""Tool mask_pii — maschera dati personali (Livello 3).

PROJECT.md: il masking PII è un livello DIVERSO dalla RLS. La RLS isola per
tenant; il masking nasconde valori sensibili (email) anche a chi ha diritto di
vedere la riga. Va sopra, non al posto della RLS.

v0/L3-base: maschera le email in modo deterministico e reversibile-solo-in-parte:
  marco.rossi@example.com -> m***@example.com
Mantiene il dominio (utile per analisi tipo "quanti clienti su gmail") ma nasconde
l'identità. Non è cifratura: è offuscamento per non esporre PII nelle risposte.
"""
from __future__ import annotations

import re

_EMAIL_RE = re.compile(r"\b([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*(@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")


def mask_email(value: str) -> str:
    """Maschera una singola email. Non-email restano invariate."""
    def _mask(m: re.Match) -> str:
        return f"{m.group(1)}***{m.group(2)}"
    return _EMAIL_RE.sub(_mask, value)


def mask_pii_in_rows(rows: list[list]) -> list[list]:
    """Applica il masking a ogni stringa che sembra un'email dentro le righe.
    Lascia intatti numeri e stringhe non-email. Utile per ripulire un
    query_result prima di restituirlo all'utente."""
    out = []
    for row in rows:
        out.append([mask_email(c) if isinstance(c, str) else c for c in row])
    return out
