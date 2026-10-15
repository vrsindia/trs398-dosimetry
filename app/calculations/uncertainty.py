"""
Simple uncertainty propagation helpers for TRS-398 style calculations.

This is a practical starting point. Full clinical uncertainty budgets
should follow TRS-398 Appendix and institutional protocols.
"""

from __future__ import annotations
from typing import Dict
import math


def relative_uncertainty_product(components: Dict[str, float]) -> float:
    """
    Combine relative standard uncertainties in quadrature
    (independent contributions).

    components: dict of {name: relative_uncertainty} e.g. {"N_Dw": 0.007, "k_Q": 0.01}
    Returns combined relative uncertainty (1-sigma).
    """
    return math.sqrt(sum(u**2 for u in components.values()))


def example_photon_uncertainty() -> Dict[str, float]:
    """
    Typical relative standard uncertainties for a high-energy photon
    absolute dose measurement (illustrative values only).
    """
    return {
        "N_Dw": 0.007,          # calibration coefficient
        "k_Q": 0.010,           # beam quality correction
        "M_raw": 0.002,         # electrometer reading (Type A)
        "k_pol": 0.001,
        "k_s": 0.003,
        "k_TP": 0.001,
        "positioning": 0.004,
        "other": 0.005,
    }
