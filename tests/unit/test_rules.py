import pytest

from nour_transfers.rules import can_transfer, days_of_cover, priority


@pytest.mark.parametrize("stock,sales,expected", [
    (10, 4, 2.5),
    (7, 2, 3.5),
    (0, 4, 0.0),
])
def test_days_of_cover_divides_stock_by_sales(stock, sales, expected):
    result = days_of_cover(stock, sales)
    assert result == expected
    assert isinstance(result, float)


@pytest.mark.parametrize("stock", [12, 0, 999])
def test_days_of_cover_is_none_when_no_sales(stock):
    assert days_of_cover(stock, 0) is None


@pytest.mark.parametrize("stock,sales", [(-1, 2), (2, -1), (-1, -1)])
def test_days_of_cover_rejects_negative_inputs(stock, sales):
    with pytest.raises(ValueError):
        days_of_cover(stock, sales)


@pytest.mark.parametrize("chronic,cover,expected", [
    (True, None, "normal"),
    (False, None, "normal"),
    (True, 2.99, "urgent"),
    (False, 2.0, "high"),
    (True, 3.0, "high"),
    (False, 6.99, "high"),
    (True, 6.99, "high"),
    (False, 7.0, "normal"),
    (True, 7.0, "normal"),
    (False, 10.0, "normal"),
])
def test_priority_table(chronic, cover, expected):
    assert priority(chronic, cover) == expected


@pytest.mark.parametrize("from_stock,quantity,reserve,expected", [
    (40, 30, 10, True),
    (6, 1, 5, True),
    (40, 31, 10, False),
    (6, 2, 5, False),
    (40, 0, 10, False),
    (40, -1, 10, False),
])
def test_can_transfer_table(from_stock, quantity, reserve, expected):
    result = can_transfer(from_stock, quantity, reserve)
    assert result is expected
    assert isinstance(result, bool)
