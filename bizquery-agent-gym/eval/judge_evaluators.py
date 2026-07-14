"""Evaluator Langfuse che trasformano il judge LLM in Score confrontabili.

RUOLO NEL SISTEMA
-----------------
eval_langfuse.py separa TASK (produci l'output) da EVALUATOR (giudica l'output).
Questo file aggiunge NUOVI evaluator accanto a `correct` (execution accuracy):
uno per criterio del judge (faithfulness / relevance / safety). Cosi' in una sola
run di dataset la UI Langfuse mostra 4 score per caso — non piu' solo "giusto/no",
ma un profilo di qualita' su piu' assi. E' questo il salto da "eval base" a
"evaluation come sistema".

PERCHE' UN JUDGE SOLO, TANTI EVALUATOR
--------------------------------------
Il judge fa UNA chiamata Gemini e ritorna tutti i voti insieme (free tier!). Ma
Langfuse vuole UN evaluator per Score. Se ogni evaluator chiamasse il judge, sarebbero
3 chiamate per caso. Soluzione: il task mette l'output arricchito (con i campi che
servono al judge) e chiamiamo il judge UNA volta per caso, memoizzato per (question,
answer). Gli evaluator poi leggono solo il voto gia' calcolato.
"""
from __future__ import annotations

from langfuse import Evaluation

from app.llm.judge import CRITERIA, judge

# Memo per-processo: (question, sql, answer) -> JudgeScores gia' calcolato.
# Motivo: i 3 evaluator dello stesso caso NON devono fare 3 chiamate al judge.
# Il primo che arriva calcola, gli altri due rileggono. Chiave = i campi che
# determinano il giudizio.
_judge_memo: dict[tuple, object] = {}


def _judged(output: dict):
    """Ritorna il JudgeScores per questo output, calcolandolo una volta sola.

    `output` e' il dict arricchito prodotto dal task: deve contenere question,
    sql, rows, answer. Se manca qualcosa (es. guardrail-reject: nessuna risposta),
    ritorna None -> gli evaluator daranno 0 annotato.
    """
    if not isinstance(output, dict) or "answer" not in output:
        return None
    key = (output.get("question"), output.get("sql"), output.get("answer"))
    if key not in _judge_memo:
        _judge_memo[key] = judge(
            question=output.get("question", ""),
            sql=output.get("sql", ""),
            rows=output.get("rows", []),
            answer=output.get("answer", ""),
        )
    return _judge_memo[key]


def _make_evaluator(criterion: str):
    """Fabbrica un evaluator Langfuse per un criterio del judge.

    Ogni evaluator ha la stessa forma del tuo `correct_evaluator`: riceve
    input/output/... e ritorna un Evaluation(name, value, comment). Il value e'
    il voto 0..1 del judge per quel criterio.
    """

    def _evaluator(*, input=None, output=None, expected_output=None, metadata=None, **kwargs):
        scored = _judged(output)
        if scored is None:
            # Nessuna risposta da giudicare (es. guardrail ha bloccato): 0 annotato.
            return Evaluation(
                name=criterion, value=0.0, comment="nessuna risposta da giudicare"
            )
        value = scored.get(criterion)
        note = scored.reasoning or ""
        if scored.degraded:
            note = f"[degraded] {note}"
        return Evaluation(name=criterion, value=value, comment=note)

    _evaluator.__name__ = f"{criterion}_evaluator"
    return _evaluator


# I tre evaluator pronti da passare a run_experiment(evaluators=[...]).
JUDGE_EVALUATORS = [_make_evaluator(c) for c in CRITERIA]


def reset_memo() -> None:
    """Svuota il memo del judge (utile fra run nello stesso processo/test)."""
    _judge_memo.clear()
