from cartelera.scrapers.price import (
    eur_amounts,
    eur_price,
    eur_to_float,
    format_eur,
    format_eur_range,
    format_pyg,
    format_pyg_range,
    pyg_amounts,
    pyg_price,
)


def test_single_price_when_equal():
    assert format_eur_range(20, 20) == "20€"


def test_minor_spread_collapses_to_high():
    # high < 2× low → not a meaningful range, show the highest price.
    assert format_eur_range(12, 16) == "16€"
    assert format_eur_range(38, 68) == "68€"
    assert format_eur_range(28, 38) == "38€"
    assert format_eur_range(50, 60) == "60€"


def test_boundary_just_under_2x_collapses():
    # 2× low is the threshold: just under stays collapsed.
    assert format_eur_range(40, 79) == "79€"


def test_meaningful_spread_keeps_range():
    # high >= 2× low → keep both ends.
    assert format_eur_range(40, 80) == "40–80€"
    assert format_eur_range(27, 85) == "27–85€"
    assert format_eur_range(35, 75) == "35–75€"
    assert format_eur_range(55, 220) == "55–220€"


# --- euro free-text helpers (Dutch venues) ----------------------------------


def test_format_eur_house_convention():
    assert format_eur(15.5) == "15,50€"
    assert format_eur(9.0) == "9€"
    assert format_eur(7.95) == "7,95€"
    assert format_eur(14.95) == "14,95€"  # float noise doesn't leak
    assert format_eur(25) == "25€"
    assert format_eur(0) == "free"


def test_eur_to_float_accepts_comma_or_dot():
    assert eur_to_float("15,50") == 15.5
    assert eur_to_float("15.5") == 15.5
    assert eur_to_float("9") == 9.0


def test_eur_amounts_ignore_times_before_the_sign():
    assert eur_amounts("/ Early entry before 23:30 €15") == [15.0]
    assert eur_amounts("€ 15.5") == [15.5]
    assert eur_amounts("Aan de deur altijd €5,50") == [5.5]
    assert eur_amounts("12,50 €") == [12.5]
    assert eur_amounts("Voorverkoop €12, deur €15") == [12.0, 15.0]
    assert eur_amounts("Doors 20:00") == []


def test_eur_price_single_amount():
    assert eur_price("€25,-") == "25€"
    assert eur_price("€ 26,50") == "26,50€"
    assert eur_price("14.95") == "14,95€"
    assert eur_price("20") == "20€"


def test_eur_price_minor_spread_takes_highest():
    assert eur_price("Presale €12,50 / door €15") == "15€"
    assert eur_price("€28 - €45") == "45€"


def test_eur_price_meaningful_spread_keeps_range():
    assert eur_price("€10 - €20") == "10–20€"
    assert eur_price("€7,50 / €25") == "7,50–25€"


def test_eur_price_zero_and_missing():
    assert eur_price("€0") == "free"
    assert eur_price("€0 / €10") == "10€"  # a free tier doesn't make a range
    assert eur_price("gratis") is None
    assert eur_price("") is None
    assert eur_price(None) is None
    assert eur_price("€ 1500") is None  # >= 1000 is not a ticket price


def test_eur_price_require_symbol_skips_bare_numbers():
    text = "Doors 20.00, 3 acts, tickets €18"
    assert eur_price(text, require_symbol=True) == "18€"
    assert eur_price("Line-up of 3 acts", require_symbol=True) is None


# --- Paraguayan guaraní (Asunción) -------------------------------------------


def test_format_pyg_dot_thousands_and_symbol():
    assert format_pyg(40000) == "40.000₲"
    assert format_pyg(380000) == "380.000₲"
    assert format_pyg(1250000) == "1.250.000₲"
    assert format_pyg(500) == "500₲"
    assert format_pyg(0) == "free"


def test_format_pyg_range_two_x_rule():
    assert format_pyg_range(40000, 40000) == "40.000₲"
    assert format_pyg_range(50000, 80000) == "80.000₲"  # < 2x: highest
    assert format_pyg_range(40000, 80000) == "40.000–80.000₲"
    assert format_pyg_range(0, 0) == "free"
    assert format_pyg_range(0, 50000) == "50.000₲"  # a free tier is no range


def test_pyg_amounts_need_a_currency_marker():
    assert pyg_amounts("Gs300.000") == [300000]
    assert pyg_amounts("Gs380000") == [380000]
    assert pyg_amounts("Gs. 80.000") == [80000]
    assert pyg_amounts("40.000 PYG") == [40000]
    assert pyg_amounts("₲ 50.000 / ₲100.000") == [50000, 100000]
    assert pyg_amounts("Entrada: 30.000 Gs.") == [30000]
    assert pyg_amounts("Platea 150.000 guaraníes") == [150000]
    assert pyg_amounts("16 oct 2026, 21:00") == []
    assert pyg_amounts("Sala 2, 20.000 personas") == []


def test_pyg_price_convention():
    assert pyg_price("40.000 PYG") == "40.000₲"
    assert pyg_price("Gs. 50.000 – Gs. 80.000") == "80.000₲"
    assert pyg_price("Gs. 40.000 / Gs. 120.000") == "40.000–120.000₲"
    assert pyg_price("Gs. 0") == "free"
    assert pyg_price("Gratuito") is None  # wording is the caller's call
    assert pyg_price("") is None
    assert pyg_price(None) is None
