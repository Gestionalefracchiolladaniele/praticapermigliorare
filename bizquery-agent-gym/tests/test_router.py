"""Test del model router (L2). Puro, no DB/rete."""
from app.llm.router import route_model, TIER_FLASH, TIER_PRO


def test_simple_count_uses_flash():
    d = route_model("Quanti clienti abbiamo?")
    assert d.complexity == "simple"
    assert d.model == TIER_FLASH


def test_simple_sum_uses_flash():
    d = route_model("Qual e' il fatturato totale degli ordini pagati?")
    assert d.complexity == "simple"


def test_trend_over_time_uses_pro():
    d = route_model("Mostrami il trend del fatturato mese per mese")
    assert d.complexity == "complex"
    assert d.model == TIER_PRO


def test_top_ranking_uses_pro():
    d = route_model("Dammi la top 5 clienti per spesa")
    assert d.complexity == "complex"


def test_per_each_grouping_uses_pro():
    d = route_model("Quanti ordini per ogni paese?")
    assert d.complexity == "complex"


def test_percentage_uses_pro():
    d = route_model("Che percentuale di ordini e' stata rimborsata sul totale?")
    assert d.complexity == "complex"


def test_plan_text_also_considered():
    # Domanda neutra ma plan che rivela complessita' -> Pro.
    d = route_model("Analizza gli ordini", plan="join tra orders e customers, media per paese")
    assert d.complexity == "complex"
