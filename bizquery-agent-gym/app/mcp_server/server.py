"""Server MCP che espone i tool di BizQuery (Livello 3).

Perché MCP: gli stessi tool (run_query, mask_pii, send_notification) che il grafo
LangGraph usa internamente diventano riutilizzabili da QUALSIASI client MCP (es.
un altro assistant) come tool esterni standard. Non si riscrive la logica: si
espongono le funzioni v0/L2 già scritte e testate.

Convenzione verificata su mcp 1.28.1: FastMCP + decoratore @mcp.tool(). Le
docstring e i type hint diventano lo schema del tool visto dal client — quindi
vanno scritti come contratto, non come commento interno.

Avvio (quando si vuole usare davvero, richiede DB per run_query):
    python -m app.mcp_server.server        # stdio transport (default MCP)

run_query gira davvero solo col DB su; mask_pii e send_notification (stub) girano
anche senza DB.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from app.tools.run_query import run_query as _run_query
from app.tools.mask_pii import mask_email as _mask_email
from app.tools.send_notification import send_notification as _send_notification

mcp = FastMCP("bizquery-tools")


@mcp.tool()
def run_query(sql: str, tenant_id: int) -> list[list]:
    """Esegue una query SQL SELECT in sola lettura per un tenant, con isolamento
    RLS e validazione guardrail. Rifiuta scritture, injection e query senza
    filtro tenant. Ritorna le righe come lista di liste."""
    return _run_query(sql, tenant_id)


@mcp.tool()
def mask_email(value: str) -> str:
    """Maschera un indirizzo email nascondendo l'identità ma mantenendo il dominio
    (es. marco.rossi@example.com -> m***@example.com). Le stringhe non-email
    restano invariate."""
    return _mask_email(value)


@mcp.tool()
def send_notification(recipient: str, subject: str, body: str) -> dict:
    """Invia una notifica (email/Slack) al destinatario. Nota: implementazione
    attuale è uno stub che registra la notifica senza inviarla davvero. Ritorna
    l'esito come dict."""
    return _send_notification(recipient, subject, body)


def main() -> None:
    # stdio: il transport standard con cui i client MCP lanciano un server locale.
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
