"""Evidence arithmetic for the reader commands: an exact binomial p-value and a 95% Wilson interval.

The behaviour is stated in docs/specs/reader-ab.md section 6.1 (and, for a chance other
than one half, docs/specs/reader-panel.md section 6.1). This module also holds the two
printed forms: the p-value rounded half up to 4 places, and the interval's ends rounded
outward to 3.

The module starts no program and reads no file. Its arithmetic is exact, with
fractions.Fraction, except the interval's square root, which uses decimal.Decimal at 60
digits.
"""

import decimal
import fractions
import math
from decimal import Decimal
from fractions import Fraction

# The 95% interval's z, fixed by the spec whatever alpha is.
Z = Decimal("1.959964")
SIDES = ("two", "greater", "less")


def binomial_p(k, n, side="two", q=Fraction(1, 2)):
    """Exact p-value of k successes in n trials with chance q, as a Fraction."""
    if n < 1:
        raise ValueError("n must be at least 1")
    if k < 0 or k > n:
        raise ValueError("k must be between 0 and n")
    if not isinstance(q, fractions.Fraction) or not 0 < q < 1:
        raise ValueError("q must be a Fraction strictly between 0 and 1")
    if side not in SIDES:
        raise ValueError("side must be one of %s" % ", ".join(SIDES))
    chance = [math.comb(n, i) * q ** i * (1 - q) ** (n - i) for i in range(n + 1)]
    greater = sum(chance[k:], Fraction(0))
    less = sum(chance[:k + 1], Fraction(0))
    if side == "greater":
        return greater
    if side == "less":
        return less
    return min(Fraction(1), 2 * min(greater, less))


def p_text(p):
    """A p-value (Fraction) printed rounded half up to 4 places, or "< 0.0001"."""
    r = math.floor(p * 10000 + Fraction(1, 2))
    if r == 0:
        return "< 0.0001"
    return "%d.%04d" % divmod(r, 10000)


def wilson(k, n):
    """The 95% Wilson score interval for k/n, as two strings (lower, upper), 3 places."""
    if n < 1:
        raise ValueError("n must be at least 1")
    if k < 0 or k > n:
        raise ValueError("k must be between 0 and n")
    with decimal.localcontext() as ctx:
        ctx.prec = 60
        z2 = Z * Z
        centre = 2 * k + z2
        spread = Z * (z2 + Decimal(4 * k * (n - k)) / n).sqrt()
        den = 2 * (n + z2)
        lower = (centre - spread) / den
        upper = (centre + spread) / den
        if k == 0:
            lower = Decimal(0)
        if k == n:
            upper = Decimal(1)
        lower = min(max(lower, Decimal(0)), Decimal(1))
        upper = min(max(upper, Decimal(0)), Decimal(1))
        step = Decimal("0.001")
        low = lower.quantize(step, rounding=decimal.ROUND_FLOOR)
        high = upper.quantize(step, rounding=decimal.ROUND_CEILING)
    return (str(low), str(high))
