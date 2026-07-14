"""Test del quality gate: la DECISIONE pass/fail/inconcludente e l'exit code.

Il gate non deve mai sbagliare il verdetto: e' cio' che blocca (o lascia passare)
un deploy. Qui mockiamo eval.evaluate() cosi' testiamo SOLO la logica di soglia,
senza DB ne' Gemini. Copre anche la robustezza ai rate-limit (429/503): un caso
perso per quota NON deve contare come fallimento di qualita'.
"""
import eval.quality_gate as qg
import eval.eval as ev


def _report(results):
    """Costruisce un report come lo farebbe evaluate(), dai casi passati."""
    total = len(results)
    passed = sum(1 for r in results if r.get("ok"))
    rl = sum(1 for r in results if r.get("status") == "rate_limited")
    evaluable = total - rl
    return lambda: {
        "accuracy": passed / total if total else 0.0,
        "accuracy_evaluable": passed / evaluable if evaluable else 0.0,
        "passed": passed, "total": total,
        "evaluable": evaluable, "rate_limited": rl,
        "results": results,
    }


def _ok(n):
    return [{"id": f"ok{i}", "status": "executed", "ok": True} for i in range(n)]


def _bad(n):
    return [{"id": f"bad{i}", "status": "executed", "ok": False,
             "got": 5, "expected": 7} for i in range(n)]


def _rl(n):
    return [{"id": f"rl{i}", "status": "rate_limited", "ok": False,
             "error": "429 RESOURCE_EXHAUSTED"} for i in range(n)]


def test_gate_passes_above_threshold(monkeypatch):
    monkeypatch.setattr(ev, "evaluate", _report(_ok(9) + _bad(1)))
    assert qg.run(with_judge=False) == 0


def test_gate_fails_below_threshold(monkeypatch):
    monkeypatch.setattr(ev, "evaluate", _report(_ok(5) + _bad(5)))
    assert qg.run(with_judge=False) == 1


def test_gate_passes_exactly_at_threshold(monkeypatch):
    # soglia 0.8 su 10 valutabili = 8 giusti. Deve PASSARE (>=).
    monkeypatch.setattr(ev, "evaluate", _report(_ok(8) + _bad(2)))
    assert qg.run(with_judge=False) == 0


def test_gate_ignores_rate_limited_cases(monkeypatch):
    # 9/10 valutabili giusti + 5 rate-limit: l'accuracy si misura sui 10 valutabili
    # (0.9 >= 0.8), i 429 non contano come fallimenti -> PASS.
    monkeypatch.setattr(ev, "evaluate", _report(_ok(9) + _bad(1) + _rl(5)))
    assert qg.run(with_judge=False) == 0


def test_gate_inconclusive_when_too_many_rate_limited(monkeypatch):
    # 5 giusti + 10 rate-limit: solo 5 valutabili < min 8 -> INCONCLUSIVO (exit 2),
    # ne' pass ne' fail. E' lo scenario "quota Gemini esaurita" della CI reale.
    monkeypatch.setattr(ev, "evaluate", _report(_ok(5) + _rl(10)))
    assert qg.run(with_judge=False) == 2


def test_real_failure_survives_some_rate_limits(monkeypatch):
    # Anche con qualche 429, se i valutabili bastano e l'accuracy e' bassa davvero,
    # il gate DEVE fallire (non nascondere un problema vero dietro i rate-limit).
    monkeypatch.setattr(ev, "evaluate", _report(_ok(5) + _bad(5) + _rl(3)))
    assert qg.run(with_judge=False) == 1
