from cartelera.scrapers.price import format_eur_range


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
