"""
Beam Quality Index calculations for high-energy photons (TRS-398).
Supports TPR20,10 and approximate %dd(10)x.
"""

from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class QualityIndexResult:
    tpr20_10: float
    method: str
    notes: str = ""


def calculate_tpr20_10(dose_20cm: float, dose_10cm: float) -> QualityIndexResult:
    """
    Tissue Phantom Ratio TPR20,10 = D(20 cm) / D(10 cm)
    at SSD = constant (usually 100 cm) or SAD geometry.
    """
    if dose_10cm <= 0:
        raise ValueError("Dose at 10 cm must be > 0")
    tpr = dose_20cm / dose_10cm
    return QualityIndexResult(
        tpr20_10=tpr,
        method="TPR20,10",
        notes="Measured at constant SSD or SAD as per TRS-398",
    )


def approximate_kQ_from_tpr(tpr20_10: float) -> float:
    """
    Very rough illustrative mapping. In clinical use the physicist
    should look up k_Q from TRS-398 tables for the specific chamber.
    This is only a placeholder helper.
    """
    # Typical range: TPR 0.60 → ~0.997, TPR 0.70 → ~0.985, TPR 0.75 → ~0.975
    if tpr20_10 < 0.60:
        return 0.999
    if tpr20_10 > 0.80:
        return 0.970
    # linear-ish interpolation for demonstration
    return 1.020 - 0.0625 * tpr20_10
