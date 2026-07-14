"""Tool mask_pii — maschera dati personali (Livello 3).

PROJECT.md: il masking PII è un livello DIVERSO dalla RLS. La RLS isola per
tenant; il masking nasconde valori sensibili (email) anche a chi ha diritto di
vedere la riga. Va sopra, non al posto della RLS.

v0/L3-base: maschera le email in modo deterministico e reversibile-solo-in-parte:
  marco.rossi@example.com -> m***@example.com
Mantiene il dominio (utile per analisi tipo "quanti clienti su gmail") ma nasconde
l'identità. Non è cifratura: è offuscamento per non esporre PII nelle risposte.

Nota di design (2026-07-14, dopo red-team): valutato Microsoft Presidio (lo
standard PII industriale, NER su nomi/telefoni/IBAN). SCARTATO per BizQuery:
tira dietro spaCy+numpy (~300MB) per fare NER su TESTO LIBERO, ma qui le PII
sono SOLO la colonna strutturata `customers.email`. Uno stack NLP per mascherare
un campo email è sovradimensionato. Presidio diventa la scelta giusta SOLO se in
futuro lo schema aggiunge nomi/telefoni/testo libero da mascherare. Fino ad
allora: regex, ma resa robusta all'Unicode (il red-team ha mostrato che la
versione ASCII-only lasciava `josé.garcía@…` in chiaro).
"""
from __future__ import annotations

import re

# `\w` con re.UNICODE (default in Python 3) copre lettere accentate/non-ASCII
# nella local part (josé, garcía, ...). Il red-team aveva bucato la versione
# `[A-Za-z0-9._%+-]` proprio con email a nome europeo: non venivano mascherate.
# Niente \b in testa: \b tra spazio e lettera accentata è inaffidabile in Unicode;
# ancoriamo invece su un confine "non-carattere-email" via lookbehind negativo.
_EMAIL_RE = re.compile(
    r"(?<![\w.%+-])([^\W\d_])[\w.%+-]*(@[\w.-]+\.[A-Za-z]{2,})",
    re.UNICODE,
)


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
