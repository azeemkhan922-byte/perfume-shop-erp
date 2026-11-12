"""Cost maths. Money in rupees as Decimal (2 places); oil quantities in grams."""
from decimal import Decimal, ROUND_HALF_UP

_M = Decimal("0.01")
_C = Decimal("0.0001")  # cost-per-gram keeps 4 decimals to avoid rounding drift


def _d(v) -> Decimal:
    return v if isinstance(v, Decimal) else Decimal(str(v))


def money(x) -> Decimal:
    return _d(x).quantize(_M, rounding=ROUND_HALF_UP)


def weighted_avg_cost(stock_g, stock_cost_per_g, bought_g, bought_total_price) -> Decimal:
    """New average cost per gram after a purchase (moving-average costing)."""
    s, c, b, p = _d(stock_g), _d(stock_cost_per_g), _d(bought_g), _d(bought_total_price)
    if b <= 0:
        raise ValueError("purchased grams must be positive")
    if s < 0 or c < 0 or p < 0:
        raise ValueError("stock, cost and price cannot be negative")
    return ((s * c + p) / (s + b)).quantize(_C, rounding=ROUND_HALF_UP)


def batch_cost(oil_grams, oil_cost_per_g, bottle_cost_each, bottles, other_costs=0):
    """Total and per-bottle cost of a filling batch."""
    n = int(bottles)
    if n <= 0:
        raise ValueError("bottles must be positive")
    total = money(_d(oil_grams) * _d(oil_cost_per_g) + _d(bottle_cost_each) * n + _d(other_costs))
    return total, money(total / n)


def profit(revenue, cost) -> Decimal:
    return money(_d(revenue) - _d(cost))
