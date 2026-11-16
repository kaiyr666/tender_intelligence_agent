from app.pipeline import basic_facts, run


def test_largest_amount_is_found():
    assert basic_facts("Lot 1 £1,200 and lot 2 £45,000.50")["max_amount_gbp"] == 45000.50


def test_text_without_amounts_returns_none():
    assert basic_facts("No money mentioned")["max_amount_gbp"] is None


def test_run_returns_basic_facts():
    assert run("three short words") == {"word_count": 3, "max_amount_gbp": None}
