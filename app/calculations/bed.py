"""
Biological Effective Dose (BED) and EQD2 calculators.

Standard LQ model:
  BED  = n * d * (1 + d / (α/β))
  EQD2 = n * d * (d + α/β) / (2 + α/β)
       = BED / (1 + 2/(α/β))

For continuous / brachy high-dose-rate with incomplete repair (optional g-factor):
  BED_br = D * (1 + g * D / (α/β))
  When g=1 (complete repair between fractions / HDR point-dose approximation),
  same form as fractionated BED with n=1, d=D.

EBRT + Brachy:
  BED_total  = BED_EBRT + BED_brachy
  EQD2_total = EQD2_EBRT + EQD2_brachy
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


def bed_fractionated(n: float, d: float, alpha_beta: float) -> float:
    """BED for n fractions of dose d (Gy) with tissue α/β."""
    if alpha_beta <= 0:
        raise ValueError("α/β must be > 0")
    if n < 0 or d < 0:
        raise ValueError("n and d must be ≥ 0")
    return float(n) * float(d) * (1.0 + float(d) / float(alpha_beta))


def eqd2_fractionated(n: float, d: float, alpha_beta: float) -> float:
    """EQD2 (equivalent dose in 2 Gy fractions)."""
    if alpha_beta <= 0:
        raise ValueError("α/β must be > 0")
    if n < 0 or d < 0:
        raise ValueError("n and d must be ≥ 0")
    return float(n) * float(d) * (float(d) + float(alpha_beta)) / (2.0 + float(alpha_beta))


def bed_from_total_dose(total_dose: float, n: float, alpha_beta: float) -> float:
    """BED when total dose and fraction count are known (d = total/n)."""
    if n <= 0:
        raise ValueError("Number of fractions must be > 0")
    d = float(total_dose) / float(n)
    return bed_fractionated(n, d, alpha_beta)


def eqd2_from_total_dose(total_dose: float, n: float, alpha_beta: float) -> float:
    if n <= 0:
        raise ValueError("Number of fractions must be > 0")
    d = float(total_dose) / float(n)
    return eqd2_fractionated(n, d, alpha_beta)


def bed_single_dose(dose: float, alpha_beta: float, g: float = 1.0) -> float:
    """
    BED for a single continuous / HDR dose.
    g = incomplete-repair factor (0–1). Default 1 = full recovery model / HDR approx.
    """
    if alpha_beta <= 0:
        raise ValueError("α/β must be > 0")
    if dose < 0:
        raise ValueError("Dose must be ≥ 0")
    g = max(0.0, min(1.0, float(g)))
    return float(dose) * (1.0 + g * float(dose) / float(alpha_beta))


def eqd2_single_dose(dose: float, alpha_beta: float, g: float = 1.0) -> float:
    bed = bed_single_dose(dose, alpha_beta, g)
    return bed / (1.0 + 2.0 / float(alpha_beta))


@dataclass
class BedEqd2Result:
    n: float
    d: float
    total_dose: float
    alpha_beta: float
    bed: float
    eqd2: float
    tissue_label: str


def calculate_bed_eqd2(
    total_dose: float,
    n_fractions: float,
    alpha_beta: float,
    tissue_label: str = "",
) -> BedEqd2Result:
    n = float(n_fractions)
    if n <= 0:
        raise ValueError("Number of fractions must be > 0")
    d = float(total_dose) / n
    bed = bed_fractionated(n, d, alpha_beta)
    eqd2 = eqd2_fractionated(n, d, alpha_beta)
    return BedEqd2Result(
        n=n, d=d, total_dose=float(total_dose),
        alpha_beta=float(alpha_beta), bed=bed, eqd2=eqd2,
        tissue_label=tissue_label or f"α/β={alpha_beta}",
    )


@dataclass
class CombinedBedResult:
    ebrt_n: float
    ebrt_d: float
    ebrt_total: float
    ebrt_ab: float
    ebrt_bed: float
    ebrt_eqd2: float
    brachy_dose: float
    brachy_ab: float
    brachy_g: float
    brachy_bed: float
    brachy_eqd2: float
    total_bed: float
    total_eqd2: float
    # Optional second tissue (e.g. OAR)
    ebrt_ab_oar: Optional[float] = None
    ebrt_bed_oar: Optional[float] = None
    ebrt_eqd2_oar: Optional[float] = None
    brachy_ab_oar: Optional[float] = None
    brachy_bed_oar: Optional[float] = None
    brachy_eqd2_oar: Optional[float] = None
    total_bed_oar: Optional[float] = None
    total_eqd2_oar: Optional[float] = None


def calculate_ebrt_brachy_bed(
    ebrt_total_dose: float,
    ebrt_n: float,
    ebrt_alpha_beta: float,
    brachy_dose: float,
    brachy_alpha_beta: float,
    brachy_g: float = 1.0,
    *,
    ebrt_alpha_beta_oar: Optional[float] = None,
    brachy_alpha_beta_oar: Optional[float] = None,
) -> CombinedBedResult:
    """Combined EBRT (fractionated) + brachy (single continuous/HDR) BED & EQD2."""
    if ebrt_n <= 0:
        raise ValueError("EBRT fraction number must be > 0")
    ebrt_d = float(ebrt_total_dose) / float(ebrt_n)
    ebrt_bed = bed_fractionated(ebrt_n, ebrt_d, ebrt_alpha_beta)
    ebrt_eqd2 = eqd2_fractionated(ebrt_n, ebrt_d, ebrt_alpha_beta)
    br_bed = bed_single_dose(brachy_dose, brachy_alpha_beta, brachy_g)
    br_eqd2 = eqd2_single_dose(brachy_dose, brachy_alpha_beta, brachy_g)

    result = CombinedBedResult(
        ebrt_n=float(ebrt_n), ebrt_d=ebrt_d, ebrt_total=float(ebrt_total_dose),
        ebrt_ab=float(ebrt_alpha_beta), ebrt_bed=ebrt_bed, ebrt_eqd2=ebrt_eqd2,
        brachy_dose=float(brachy_dose), brachy_ab=float(brachy_alpha_beta),
        brachy_g=float(brachy_g), brachy_bed=br_bed, brachy_eqd2=br_eqd2,
        total_bed=ebrt_bed + br_bed, total_eqd2=ebrt_eqd2 + br_eqd2,
    )

    if ebrt_alpha_beta_oar is not None and brachy_alpha_beta_oar is not None:
        ebrt_bed_o = bed_fractionated(ebrt_n, ebrt_d, ebrt_alpha_beta_oar)
        ebrt_eqd2_o = eqd2_fractionated(ebrt_n, ebrt_d, ebrt_alpha_beta_oar)
        br_bed_o = bed_single_dose(brachy_dose, brachy_alpha_beta_oar, brachy_g)
        br_eqd2_o = eqd2_single_dose(brachy_dose, brachy_alpha_beta_oar, brachy_g)
        result.ebrt_ab_oar = float(ebrt_alpha_beta_oar)
        result.ebrt_bed_oar = ebrt_bed_o
        result.ebrt_eqd2_oar = ebrt_eqd2_o
        result.brachy_ab_oar = float(brachy_alpha_beta_oar)
        result.brachy_bed_oar = br_bed_o
        result.brachy_eqd2_oar = br_eqd2_o
        result.total_bed_oar = ebrt_bed_o + br_bed_o
        result.total_eqd2_oar = ebrt_eqd2_o + br_eqd2_o

    return result


# Common clinical α/β presets (Gy)
ALPHA_BETA_PRESETS = {
    "Tumour (early, α/β=10)": 10.0,
    "Prostate (α/β=1.5)": 1.5,
    "Late responding tissue (α/β=3)": 3.0,
    "Spinal cord (α/β=2)": 2.0,
    "Skin late (α/β=3)": 3.0,
    "Custom": None,
}
