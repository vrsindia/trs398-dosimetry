"""
Biological effective dose (BED) and EQD2 calculators.

Standard LQ model:
  BED  = n * d * (1 + d / (a/b))
  EQD2 = n * d * (d + a/b) / (2 + a/b)

Brachy (single or multi-fraction HDR):
  Each fraction: BED_i = d_i * (1 + g * d_i / (a/b))
  Total brachy BED = sum(BED_i)

Gap correction (treatment interruption):
  Proliferation term K (Gy/day) over gap days G:
  BED_loss ≈ K * G
  Extra physical dose at remaining fraction size d to compensate:
  d_extra ≈ BED_loss / (1 + d/(a/b))  per remaining course logic
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional


def bed_fractionated(n: float, d: float, alpha_beta: float) -> float:
    if alpha_beta <= 0:
        raise ValueError("Alpha/beta must be > 0")
    if n < 0 or d < 0:
        raise ValueError("n and d must be >= 0")
    return float(n) * float(d) * (1.0 + float(d) / float(alpha_beta))


def eqd2_fractionated(n: float, d: float, alpha_beta: float) -> float:
    if alpha_beta <= 0:
        raise ValueError("Alpha/beta must be > 0")
    if n < 0 or d < 0:
        raise ValueError("n and d must be >= 0")
    return float(n) * float(d) * (float(d) + float(alpha_beta)) / (2.0 + float(alpha_beta))


def bed_single_dose(dose: float, alpha_beta: float, g: float = 1.0) -> float:
    if alpha_beta <= 0:
        raise ValueError("Alpha/beta must be > 0")
    if dose < 0:
        raise ValueError("Dose must be >= 0")
    g = max(0.0, min(1.0, float(g)))
    return float(dose) * (1.0 + g * float(dose) / float(alpha_beta))


def eqd2_single_dose(dose: float, alpha_beta: float, g: float = 1.0) -> float:
    bed = bed_single_dose(dose, alpha_beta, g)
    return bed / (1.0 + 2.0 / float(alpha_beta))


def bed_multi_fraction_doses(doses: List[float], alpha_beta: float, g: float = 1.0) -> float:
    """Sum BED over a list of fraction doses (e.g. multiple brachy fractions)."""
    total = 0.0
    for d in doses:
        total += bed_single_dose(float(d), alpha_beta, g)
    return total


def eqd2_multi_fraction_doses(doses: List[float], alpha_beta: float, g: float = 1.0) -> float:
    bed = bed_multi_fraction_doses(doses, alpha_beta, g)
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
        tissue_label=tissue_label or f"a/b={alpha_beta}",
    )


@dataclass
class BrachyFraction:
    dose: float
    bed: float
    eqd2: float


@dataclass
class CombinedBedResult:
    ebrt_n: float
    ebrt_d: float
    ebrt_total: float
    ebrt_ab: float
    ebrt_bed: float
    ebrt_eqd2: float
    brachy_doses: List[float]
    brachy_fractions: List[BrachyFraction]
    brachy_n: int
    brachy_total_dose: float
    brachy_ab: float
    brachy_g: float
    brachy_bed: float
    brachy_eqd2: float
    total_bed: float
    total_eqd2: float


def calculate_ebrt_brachy_bed(
    ebrt_total_dose: float,
    ebrt_n: float,
    ebrt_alpha_beta: float,
    brachy_doses: List[float],
    brachy_alpha_beta: float,
    brachy_g: float = 1.0,
) -> CombinedBedResult:
    """EBRT (fractionated) + one or more brachy fractions."""
    if ebrt_n <= 0:
        raise ValueError("EBRT fraction number must be > 0")
    doses = [float(d) for d in brachy_doses if float(d) > 0]
    if not doses:
        raise ValueError("At least one brachytherapy fraction dose is required")

    ebrt_d = float(ebrt_total_dose) / float(ebrt_n)
    ebrt_bed = bed_fractionated(ebrt_n, ebrt_d, ebrt_alpha_beta)
    ebrt_eqd2 = eqd2_fractionated(ebrt_n, ebrt_d, ebrt_alpha_beta)

    fracs: List[BrachyFraction] = []
    br_bed = 0.0
    br_eqd2 = 0.0
    for d in doses:
        b = bed_single_dose(d, brachy_alpha_beta, brachy_g)
        e = eqd2_single_dose(d, brachy_alpha_beta, brachy_g)
        fracs.append(BrachyFraction(dose=d, bed=b, eqd2=e))
        br_bed += b
        br_eqd2 += e

    return CombinedBedResult(
        ebrt_n=float(ebrt_n),
        ebrt_d=ebrt_d,
        ebrt_total=float(ebrt_total_dose),
        ebrt_ab=float(ebrt_alpha_beta),
        ebrt_bed=ebrt_bed,
        ebrt_eqd2=ebrt_eqd2,
        brachy_doses=doses,
        brachy_fractions=fracs,
        brachy_n=len(doses),
        brachy_total_dose=sum(doses),
        brachy_ab=float(brachy_alpha_beta),
        brachy_g=float(brachy_g),
        brachy_bed=br_bed,
        brachy_eqd2=br_eqd2,
        total_bed=ebrt_bed + br_bed,
        total_eqd2=ebrt_eqd2 + br_eqd2,
    )


@dataclass
class GapCorrectionResult:
    planned_n: float
    planned_d: float
    planned_total: float
    alpha_beta: float
    delivered_n: float
    gap_days: float
    k_gy_per_day: float
    planned_bed: float
    delivered_bed: float
    bed_loss_repop: float
    remaining_n: float
    remaining_bed_needed: float
    suggested_d_remaining: float
    remaining_total_dose: float
    compensated_total_bed: float


def calculate_gap_correction(
    planned_total_dose: float,
    planned_n: float,
    alpha_beta: float,
    delivered_n: float,
    gap_days: float,
    k_gy_per_day: float = 0.6,
) -> GapCorrectionResult:
    """
    Gap / treatment-interruption correction.

    BED_planned = n*d*(1+d/(a/b))
    After delivering delivered_n fractions, a gap of gap_days occurs.
    Repopulation cost ≈ K * gap_days (Gy BED).
    Remaining fractions keep same d unless adjusted; suggested d compensates
    the lost BED over remaining_n fractions.
    """
    if planned_n <= 0:
        raise ValueError("Planned fractions must be > 0")
    if delivered_n < 0 or delivered_n > planned_n:
        raise ValueError("Delivered fractions must be between 0 and planned n")
    if gap_days < 0:
        raise ValueError("Gap days must be >= 0")
    if alpha_beta <= 0:
        raise ValueError("Alpha/beta must be > 0")

    d = float(planned_total_dose) / float(planned_n)
    planned_bed = bed_fractionated(planned_n, d, alpha_beta)
    delivered_bed = bed_fractionated(delivered_n, d, alpha_beta)
    bed_loss = float(k_gy_per_day) * float(gap_days)
    remaining_n = float(planned_n) - float(delivered_n)
    if remaining_n <= 0:
        raise ValueError("No remaining fractions to compensate")

    # BED still needed from remaining course = (planned - delivered) + repopulation loss
    remaining_bed_needed = (planned_bed - delivered_bed) + bed_loss

    # Solve for d_rem in: remaining_n * d_rem * (1 + d_rem/ab) = remaining_bed_needed
    # remaining_n/ab * d^2 + remaining_n * d - remaining_bed_needed = 0
    ab = float(alpha_beta)
    a = remaining_n / ab
    b = remaining_n
    c = -remaining_bed_needed
    disc = b * b - 4 * a * c
    if disc < 0:
        raise ValueError("Cannot solve for remaining dose per fraction (check inputs)")
    d_rem = (-b + disc ** 0.5) / (2 * a)

    return GapCorrectionResult(
        planned_n=float(planned_n),
        planned_d=d,
        planned_total=float(planned_total_dose),
        alpha_beta=ab,
        delivered_n=float(delivered_n),
        gap_days=float(gap_days),
        k_gy_per_day=float(k_gy_per_day),
        planned_bed=planned_bed,
        delivered_bed=delivered_bed,
        bed_loss_repop=bed_loss,
        remaining_n=remaining_n,
        remaining_bed_needed=remaining_bed_needed,
        suggested_d_remaining=d_rem,
        remaining_total_dose=d_rem * remaining_n,
        compensated_total_bed=delivered_bed + remaining_bed_needed,
    )


ALPHA_BETA_PRESETS = {
    "Early responding tissue (a/b=10)": 10.0,
    "Prostate (a/b=1.5)": 1.5,
    "Late responding tissue (a/b=3)": 3.0,
    "Spinal cord (a/b=2)": 2.0,
    "Skin late (a/b=3)": 3.0,
    "Custom": None,
}
