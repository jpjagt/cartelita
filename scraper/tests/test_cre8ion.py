import datetime as dt
from decimal import Decimal

from cartelera.scrapers import _cre8ion as c8

TODAY = dt.date(2026, 10, 14)


def test_parse_date_with_year():
    assert c8.parse_date("wo 14 okt 2026", TODAY) == dt.date(2026, 10, 14)
    assert c8.parse_date("vr 2 jul 2027", TODAY) == dt.date(2027, 7, 2)


def test_parse_date_without_year_uses_weekday():
    assert c8.parse_date("wo 14 oktober", TODAY) == dt.date(2026, 10, 14)
    # Next spring: di 11 mei is 2027 (11 May 2026 was a Monday).
    assert c8.parse_date("di 11 mei", TODAY) == dt.date(2027, 5, 11)
    assert c8.parse_date("vr 01 januari", TODAY) == dt.date(2027, 1, 1)


def test_parse_date_without_weekday_rolls_forward():
    assert c8.parse_date("3 februari", TODAY) == dt.date(2027, 2, 3)
    assert c8.parse_date("1 oktober", TODAY) == dt.date(2026, 10, 1)


def test_parse_time():
    assert c8.parse_time("20:00u") == dt.time(20, 0)
    assert c8.parse_time("20:00 - 21:10") == dt.time(20, 0)
    assert c8.parse_time("00:00u") is None  # the CMS's "no time"
    assert c8.parse_time("") is None


def test_amounts_and_formats():
    assert c8.amounts("€ 25,00 / € 21,00 / € 15,00") == [Decimal("25.00"), Decimal("21.00"), Decimal("15.00")]
    assert c8.amounts("€5,-") == [Decimal("5")]
    assert c8.amounts("Community €7.50 / General audience €12.50") == [Decimal("7.50"), Decimal("12.50")]
    assert c8.format_amount(Decimal("12.50")) == "12,50€"
    assert c8.format_amount(Decimal("25.00")) == "25€"


def test_seat_tiers_follow_the_two_x_rule():
    assert c8.format_tiers([Decimal(25), Decimal(21), Decimal(15)]) == "25€"
    assert c8.format_tiers([Decimal(99), Decimal(89), Decimal(79), Decimal(49)]) == "49–99€"
    assert c8.format_tiers([Decimal("30.50"), Decimal("26.50"), Decimal("20.50")]) == "30,50€"
    assert c8.format_tiers([Decimal(0)]) == "free"


def test_discount_range_takes_the_full_price():
    assert c8.row_price("Van € 10,50 tot € 21,00") == "21€"
    assert c8.row_price("€ 13,50") == "13,50€"
    assert c8.row_price("Gratis") == "free"
    assert c8.row_price("") is None
