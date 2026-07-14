"""Suite di REGRESSIONE DI SICUREZZA — red-team dei guardrail come test.

PERCHE' ESISTE
--------------
Ogni attacco che il red-team ha trovato (2026-07-14) diventa un test: se un domani
qualcuno "semplifica" il guardrail e riapre un buco (es. rimette il check tenant a
substring), questa suite diventa ROSSA e blocca il merge. E' la differenza tra
"ho bucato il guardrail una volta a mano" e "il guardrail non si ri-buca mai piu'".
Puro Python, zero Gemini, zero DB → gira in CI a OGNI push (job `test`).

FONTE UNICA DI VERITA'
----------------------
I casi NON sono duplicati qui: si leggono da security/promptfooconfig.yaml, la
STESSA config che usa promptfoo. Aggiungi un attacco lì una volta sola e copre sia
il red-team promptfoo sia questa regressione pytest. Il contratto del verdetto è
quello del provider (security/guardrail_provider.py): "VERDICT=<...> | reason=...".

MODELLO DELLE ASSERT
--------------------
- caso [attack] → il guardrail NON deve mai dare 'approved' (l'attacco è fermato:
  rejected, oppure sospeso in needs_human — comunque NON eseguito liberamente).
- caso [legit] → deve dare 'approved' (niente falsi positivi che romperebbero
  query normali).
Le assert vengono dalla config stessa (contains / not-contains VERDICT=approved).
"""
from __future__ import annotations

import os
import sys

import pytest

# Rende importabili sia `security.guardrail_provider` sia il pacchetto app.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

_CONFIG = os.path.join(_ROOT, "security", "promptfooconfig.yaml")


def _load_cases():
    """Legge i casi dalla config promptfoo. Se manca PyYAML o il file, salta la
    suite con un motivo chiaro invece di fallire in modo criptico."""
    yaml = pytest.importorskip("yaml", reason="PyYAML serve per leggere la config red-team")
    if not os.path.exists(_CONFIG):
        pytest.skip(f"config red-team non trovata: {_CONFIG}")
    with open(_CONFIG, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    default_assert = cfg.get("defaultTest", {}).get("assert", [])
    cases = []
    for t in cfg.get("tests", []):
        sql = t["vars"]["sql"]
        asserts = t.get("assert") or default_assert
        cases.append(pytest.param(sql, asserts, id=t["description"]))
    return cases


_CASES = _load_cases()


@pytest.mark.parametrize("sql,asserts", _CASES)
def test_guardrail_redteam(sql, asserts):
    """Esegue un caso red-team contro il guardrail vero e verifica le assert
    dichiarate nella config (le stesse che userebbe promptfoo)."""
    from security.guardrail_provider import call_api

    output = call_api(sql)["output"]
    for a in asserts:
        if a["type"] == "contains":
            assert a["value"] in output, (
                f"atteso che l'output contenga {a['value']!r}, ma è {output!r} "
                f"(SQL: {sql!r}) — possibile FALSO POSITIVO su query legittima"
            )
        elif a["type"] == "not-contains":
            assert a["value"] not in output, (
                f"BUCO DI SICUREZZA: l'output contiene {a['value']!r} — l'attacco "
                f"è passato. SQL: {sql!r}, output: {output!r}"
            )
        else:
            pytest.skip(f"tipo di assert non gestito da pytest: {a['type']}")


def test_redteam_config_has_cases():
    """Sanity: la suite non deve girare a vuoto (config svuotata per errore)."""
    assert len(_CASES) >= 10, "attesi almeno 10 casi red-team nella config"


# --- Regressione PII masking (bypass unicode chiuso il 2026-07-14) -------------
# Il red-team aveva trovato che la regex email ASCII-only lasciava in chiaro le
# email a nome accentato (josé.garcía@…). Questi test blindano il fix: se qualcuno
# ripristina una regex ASCII-only, tornano rossi.
@pytest.mark.parametrize(
    "email",
    [
        "marco.rossi@example.com",      # ASCII base
        "josé.garcía@example.com",      # accenti latini
        "müller@example.de",            # umlaut
        "søren@example.dk",             # nordico
        "marco+spam@example.com",       # tag +
    ],
    ids=["ascii", "accenti", "umlaut", "nordico", "plus_tag"],
)
def test_pii_email_is_masked(email):
    """Un'email PII non deve mai comparire in chiaro dopo il masking."""
    from app.tools.mask_pii import mask_email

    out = mask_email(email)
    local = email.split("@")[0]
    assert out != email, f"email NON mascherata (in chiaro): {email!r}"
    assert local not in out, f"local-part PII trapelata: {local!r} in {out!r}"
    assert "@" in out and out.endswith(email.split("@")[1]), (
        f"il dominio deve restare per l'analisi, ma è cambiato: {out!r}"
    )
