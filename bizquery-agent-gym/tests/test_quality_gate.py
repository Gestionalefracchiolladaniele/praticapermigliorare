"""Test del quality gate: la DECISIONE pass/fail e l'exit code.

Il gate non deve mai sbagliare il verdetto: e' cio' che blocca (o lascia passare)
un deploy. Qui mockiamo eval.evaluate() cosi' testiamo SOLO la logica di soglia,
senza DB ne' Gemini. Il judge non e' toccato (gate base, with_judge=False).
"""
import eval.quality_gate as qg
import eval.eval as ev


def _fake_eval(accuracy):
    return lambda: {"accuracy": accuracy, "passed": 0, "total": 10, "results": []}


def test_gate_passes_above_threshold(monkeypatch):
    monkeypatch.setattr(ev, "evaluate", _fake_eval(0.9))
    assert qg.run(with_judge=False) == 0


def test_gate_fails_below_threshold(monkeypatch):
    monkeypatch.setattr(ev, "evaluate", _fake_eval(0.5))
    assert qg.run(with_judge=False) == 1


def test_gate_passes_exactly_at_threshold(monkeypatch):
    # La soglia e' >= : esattamente al valore deve PASSARE, non fallire.
    floor = qg._load_thresholds()["execution_accuracy"]
    monkeypatch.setattr(ev, "evaluate", _fake_eval(floor))
    assert qg.run(with_judge=False) == 0


def test_gate_fails_just_below_threshold(monkeypatch):
    floor = qg._load_thresholds()["execution_accuracy"]
    monkeypatch.setattr(ev, "evaluate", _fake_eval(floor - 0.01))
    assert qg.run(with_judge=False) == 1
