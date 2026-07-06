"""Tool send_notification (Livello 3).

A regime: invia email/Slack quando una risposta è pronta o una query va approvata.
v0/L3-base: stub locale che REGISTRA la notifica invece di inviarla davvero —
inviare richiederebbe credenziali (SMTP/Slack) fuori scope ora. Lo stub ha la
stessa firma del tool reale, così il grafo/MCP lo usa già e in futuro si sostituisce
solo il corpo, senza cambiare i chiamanti.

Ritorna un dict con l'esito: un tool non deve stampare e basta, deve dire al
chiamante se ha funzionato.
"""
from __future__ import annotations

from datetime import datetime, timezone

# memoria in-process delle notifiche "inviate": utile ai test e come traccia.
_SENT: list[dict] = []


def send_notification(recipient: str, subject: str, body: str) -> dict:
    entry = {
        "recipient": recipient,
        "subject": subject,
        "body": body,
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "delivered": False,   # stub: non inviato davvero
    }
    _SENT.append(entry)
    return {"ok": True, "note": "stub locale: notifica registrata, non inviata", **entry}


def sent_notifications() -> list[dict]:
    """Per test/ispezione: cosa è stato 'inviato'."""
    return list(_SENT)
