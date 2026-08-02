from orders.pricing import total


def test_total_sums_lines():
    assert total([{"qty": 2, "unit_price": 3.0}]) == 6.0
