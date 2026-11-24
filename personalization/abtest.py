"""Two-proportion z-test for comparing click-through between two variants."""
import math


def z_test(clicks_a: int, n_a: int, clicks_b: int, n_b: int) -> dict:
    if min(n_a, n_b) <= 0:
        raise ValueError("each variant needs at least one impression")
    p_a, p_b = clicks_a / n_a, clicks_b / n_b
    pooled = (clicks_a + clicks_b) / (n_a + n_b)
    se = math.sqrt(pooled * (1 - pooled) * (1 / n_a + 1 / n_b))
    z = 0.0 if se == 0 else (p_b - p_a) / se
    p = math.erfc(abs(z) / math.sqrt(2))  # two-sided
    return {"rate_a": p_a, "rate_b": p_b, "lift": (p_b - p_a) / p_a if p_a else None, "z": z, "p_value": p,
            "significant": p < 0.05}
