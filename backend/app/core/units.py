"""Unit conversion for attar oil. All stock is stored in GRAMS (base unit).

Rule: 1 gram is NOT assumed to equal 1 ml. Every oil has its own density
(g per ml) that the shop owner can configure. Uses Decimal to avoid float errors.
"""
from decimal import Decimal, ROUND_HALF_UP

MASS_TO_GRAMS = {"mg": Decimal("0.001"), "g": Decimal("1"), "kg": Decimal("1000")}
VOLUME_TO_ML = {"ml": Decimal("1"), "l": Decimal("1000")}
BOTTLE_SIZES_ML = (6, 12, 30, 50, 100)
_Q = Decimal("0.001")  # 3-decimal precision for grams


def q(x: Decimal) -> Decimal:
    return x.quantize(_Q, rounding=ROUND_HALF_UP)


def _dec(v) -> Decimal:
    return v if isinstance(v, Decimal) else Decimal(str(v))


def to_grams(quantity, unit: str, density_g_per_ml=None) -> Decimal:
    """Convert a purchased/entered quantity into grams.
    kg/g/mg convert directly. ml/l need the oil's density."""
    qty, unit = _dec(quantity), unit.lower()
    if qty < 0:
        raise ValueError("quantity cannot be negative")
    if unit in MASS_TO_GRAMS:
        return q(qty * MASS_TO_GRAMS[unit])
    if unit in VOLUME_TO_ML:
        if density_g_per_ml is None or _dec(density_g_per_ml) <= 0:
            raise ValueError("density is required to convert volume to grams")
        return q(qty * VOLUME_TO_ML[unit] * _dec(density_g_per_ml))
    raise ValueError(f"unknown unit: {unit}")


def oil_grams_for_bottle(bottle_ml, density_g_per_ml, oil_fraction=Decimal("1")) -> Decimal:
    """Grams of attar oil used to fill one bottle.
    oil_fraction = share of the bottle that is pure oil by VOLUME
    (1 = pure attar, 0.25 = 25% oil diluted in carrier/base)."""
    ml, d, f = _dec(bottle_ml), _dec(density_g_per_ml), _dec(oil_fraction)
    if ml <= 0 or d <= 0:
        raise ValueError("bottle size and density must be positive")
    if not (Decimal("0") < f <= Decimal("1")):
        raise ValueError("oil_fraction must be between 0 and 1")
    return q(ml * f * d)


def deduct_stock(stock_grams, needed_grams) -> Decimal:
    """Return new stock after deduction; refuse to go negative."""
    s, n = _dec(stock_grams), _dec(needed_grams)
    if n > s:
        raise ValueError(f"insufficient stock: have {s} g, need {n} g")
    return q(s - n)
