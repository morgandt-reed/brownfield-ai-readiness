def total(lines: list[dict]) -> float:
    return sum(line["qty"] * line["unit_price"] for line in lines)
