"""Prompt Management con Langfuse (Capacità 3 del percorso LEARN_LANGFUSE).

PROBLEMA che risolve: i prompt (`_SYSTEM_PROMPT`, `_REVIEW_PROMPT`) erano
hardcoded in `gemini_client.py`. Cambiarli significava toccare il codice e fare
redeploy, senza storico né possibilità di sapere "quale versione di prompt ha
prodotto quel risultato". In produzione i prompt si versionano FUORI dal codice.

COSA FA questo modulo: recupera un prompt da Langfuse Prompt Management a runtime
(`get_prompt`, con cache locale gestita dall'SDK), lo compila con le variabili, e
ritorna anche un RIFERIMENTO alla versione usata (`name@version`) da appendere ai
metadata della trace — così ogni run è tracciabile fino alla versione di prompt.

PRINCIPIO DI ROBUSTEZZA (identico a langfuse_setup.py, eval.py, flywheel.py): se
Langfuse non è configurato/raggiungibile, NON si rompe nulla. `get_prompt` di v4
accetta un `fallback` nativo: se non riesce a recuperare il prompt dal server usa
la stringa hardcoded che gli passiamo. Quindi il comportamento a freddo è identico
a prima (stesso testo), solo senza versionamento. Nessun pezzo del sistema dipende
dalla presenza di Langfuse — Prompt Management è puro "sopra".

CONVENZIONE VARIABILI (v4, verificata sul client 4.13.2): Langfuse usa `{{var}}`
(doppia graffa) per i placeholder, compilati con `prompt.compile(var=...)`. È
DIVERSO dal vecchio `str.format` che usava graffa singola `{var}`: i prompt
caricati su Langfuse vanno scritti con `{{tenant_id}}`, `{{schema}}`, ecc.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.observability.langfuse_setup import get_client


@dataclass
class ResolvedPrompt:
    """Un prompt risolto: il testo pronto per il modello + da dove viene.

    `ref` è `name@version` se preso da Langfuse, oppure `name@fallback` se si è
    ricaduti sull'hardcoded — utile da mettere nei metadata della trace per sapere
    a posteriori quale prompt ha guidato quella run."""

    text: str
    ref: str
    from_langfuse: bool


def get_prompt(
    name: str,
    fallback_template: str,
    *,
    label: str = "production",
    **variables: object,
) -> ResolvedPrompt:
    """Recupera il prompt `name` da Langfuse e lo compila con `variables`.

    `fallback_template`: la stringa hardcoded (con `{{var}}`) usata se Langfuse è
    offline/non configurato — garantisce che il sistema funzioni comunque.
    `label`: quale versione servire (Langfuse usa etichette come `production`); a
    freddo, senza il prompt caricato sul server, si ignora e si usa il fallback.

    Ritorna sempre un ResolvedPrompt: chi chiama non deve gestire il caso None.
    """
    client = get_client()

    # Tracing/Prompt off (chiavi mancanti) → si usa direttamente il fallback,
    # compilato con la stessa sostituzione {{var}} che userebbe Langfuse.
    if client is None:
        return ResolvedPrompt(
            text=_render_fallback(fallback_template, variables),
            ref=f"{name}@fallback",
            from_langfuse=False,
        )

    try:
        # `fallback` è nativo in v4: se il fetch dal server fallisce (prompt non
        # ancora caricato, rete giù), get_prompt NON solleva — costruisce un
        # client sul fallback. cache_ttl_seconds: l'SDK cachea, non colpisce la
        # rete a ogni chiamata (default 60s, lo lasciamo esplicito per chiarezza).
        prompt = client.get_prompt(
            name,
            label=label,
            type="text",
            fallback=fallback_template,
            cache_ttl_seconds=60,
        )
        text = prompt.compile(**variables)
        # `prompt.version` è None quando si è ricaduti sul fallback interno di v4.
        version = getattr(prompt, "version", None)
        if version is None:
            return ResolvedPrompt(text, f"{name}@fallback", from_langfuse=False)
        return ResolvedPrompt(text, f"{name}@v{version}", from_langfuse=True)
    except Exception:  # noqa: BLE001 — il prompt management non deve mai rompere l'app
        return ResolvedPrompt(
            text=_render_fallback(fallback_template, variables),
            ref=f"{name}@fallback",
            from_langfuse=False,
        )


def _render_fallback(template: str, variables: dict[str, object]) -> str:
    """Sostituisce i placeholder `{{var}}` nel fallback, come farebbe Langfuse.

    Non usiamo str.format perché i prompt sono scritti con la sintassi Langfuse
    (doppia graffa): così lo STESSO template funziona sia caricato su Langfuse sia
    come fallback locale, senza doverne mantenere due versioni diverse."""
    text = template
    for key, value in variables.items():
        text = text.replace("{{" + key + "}}", str(value))
    return text
