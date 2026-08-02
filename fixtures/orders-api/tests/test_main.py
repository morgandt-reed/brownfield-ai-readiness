from orders.main import get_order


def test_get_order_returns_id():
    assert get_order(7)["id"] == 7
