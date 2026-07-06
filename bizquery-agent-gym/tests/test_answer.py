"""Test della formattazione NL (pezzo dello step 4). Puro Python, no DB."""
from decimal import Decimal

from app.answer import format_answer


def test_single_scalar_int():
    out = format_answer("Quanti clienti?", [[15]])
    assert "15" in out and "Quanti clienti?" in out


def test_single_scalar_decimal_two_places():
    # sum() da Postgres torna Decimal: deve uscire con 2 decimali.
    out = format_answer("Fatturato?", [[Decimal("68786.45")]])
    assert "68786.45" in out


def test_float_integer_has_no_decimals():
    out = format_answer("Quanti?", [[15.0]])
    assert "15" in out and "15.00" not in out


def test_empty_result():
    out = format_answer("Clienti in Giappone?", [])
    assert "Nessun risultato" in out


def test_single_row_multi_cols():
    out = format_answer("Nome e paese?", [["Marco Rossi", "Italy"]])
    assert "Marco Rossi" in out and "Italy" in out


def test_many_rows_truncated():
    rows = [[i] for i in range(25)]
    out = format_answer("Elenca id", rows)
    assert "25 righe" in out and "+5 righe" in out
