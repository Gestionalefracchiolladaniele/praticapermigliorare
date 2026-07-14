"""Test dell'LLM-as-judge (Evaluation come sistema). No rete: Gemini e' mockato.

Il judge fa UNA chiamata Gemini per giudicare una risposta su 3 criteri. Qui NON
vogliamo spendere quota ne' dipendere dalla rete: sostituiamo il client Gemini con
un finto (`monkeypatch.setattr` su `judge._client`, come gli altri test del grafo).
Cosi' controlliamo la logica che DEVE reggere: parsing, clamp, fallback, degrado.
"""
import app.llm.judge as J
from app.llm.judge import judge, _parse_scores, _fallback, CRITERIA


class _FakeResp:
    def __init__(self, text):
        self.text = text


def _fake_client(text):
    """Ritorna un finto client Gemini che risponde sempre `text`."""
    class _Models:
        def generate_content(self, **kwargs):
            return _FakeResp(text)

    class _Client:
        models = _Models()

    return lambda: _Client()


# --- parsing puro (nessun client) ---------------------------------------------

def test_parse_clean_json():
    p = _parse_scores('{"faithfulness":0.9,"relevance":1.0,"safety":1.0,"reasoning":"ok"}')
    assert p == {"faithfulness": 0.9, "relevance": 1.0, "safety": 1.0}


def test_parse_json_wrapped_in_fences_and_prose():
    # Il free tier a volte incolla ```json e testo intorno: dobbiamo reggere.
    dirty = 'Giudizio:\n```json\n{"faithfulness":0.5,"relevance":0.5,"safety":0.5}\n```\nfine'
    assert _parse_scores(dirty) == {"faithfulness": 0.5, "relevance": 0.5, "safety": 0.5}


def test_parse_clamps_out_of_range():
    # Un giudice puo' sbagliare e scrivere 1.7 o -0.3: vanno riportati in [0,1].
    assert _parse_scores('{"faithfulness":1.7,"relevance":-0.3,"safety":0.4}') == {
        "faithfulness": 1.0, "relevance": 0.0, "safety": 0.4,
    }


def test_parse_incomplete_returns_none():
    # Manca un criterio -> None, cosi' il chiamante degrada invece di inventare.
    assert _parse_scores('{"faithfulness":1.0}') is None


# --- fallback deterministico ---------------------------------------------------

def test_fallback_flags_clear_email():
    fb = _fallback("q", "sql", [], "Il cliente e' mario.rossi@example.com")
    assert fb.degraded is True
    assert fb.get("safety") == 0.0            # PII in chiaro -> non sicuro


def test_fallback_masked_email_is_safe():
    fb = _fallback("q", "sql", [], "Il cliente e' m***@example.com")
    assert fb.get("safety") == 1.0            # gia' mascherata -> sicuro


# --- judge() end-to-end col client mockato ------------------------------------

def test_judge_parses_good_llm_output(monkeypatch):
    monkeypatch.setattr(
        J, "_client",
        _fake_client('{"faithfulness":1.0,"relevance":0.8,"safety":1.0,"reasoning":"buona"}'),
    )
    res = judge("Quanti clienti?", "SELECT count(*)", [[15]], "Risposta: 15.")
    assert res.degraded is False
    assert res.get("faithfulness") == 1.0
    assert res.get("relevance") == 0.8
    assert res.reasoning == "buona"


def test_judge_degrades_on_unparsable_output(monkeypatch):
    # LLM risponde qualcosa che non e' JSON -> degrado, non crash.
    monkeypatch.setattr(J, "_client", _fake_client("non ho capito la domanda"))
    res = judge("q", "sql", [], "Risposta.")
    assert res.degraded is True
    assert set(res.scores) == set(CRITERIA)   # comunque tutti i criteri presenti


def test_judge_degrades_on_client_error(monkeypatch):
    # Il client solleva (simula 429 / chiave assente): judge NON deve propagare.
    def _boom():
        raise RuntimeError("simulato 429 RESOURCE_EXHAUSTED")

    monkeypatch.setattr(J, "_client", _boom)
    res = judge("q", "sql", [], "Il cliente e' mario.rossi@example.com")
    assert res.degraded is True
    assert res.get("safety") == 0.0           # il fallback misura comunque la PII
