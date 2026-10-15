"""
Unit tests for TRS-398 Photon absolute dosimetry calculations.
These tests use realistic example values and known expected results.
"""

import pytest
from app.calculations.photon import (
    calculate_k_TP,
    calculate_dose_to_water_photon,
    PhotonMeasurementInput,
)


def test_k_TP_standard_conditions():
    """At reference conditions k_TP must be exactly 1.0"""
    k = calculate_k_TP(temperature_C=20.0, pressure_hPa=1013.25)
    assert abs(k - 1.0) < 1e-9


def test_k_TP_higher_temperature():
    """Higher temperature → k_TP > 1"""
    k = calculate_k_TP(temperature_C=22.0, pressure_hPa=1013.25)
    assert k > 1.0
    # Expected ≈ (295.15 / 293.15) ≈ 1.0068
    assert abs(k - 1.00682) < 0.0001


def test_k_TP_lower_pressure():
    """Lower pressure → k_TP > 1"""
    k = calculate_k_TP(temperature_C=20.0, pressure_hPa=1000.0)
    assert k > 1.0


def test_basic_dose_calculation():
    """
    Simple end-to-end calculation with realistic numbers.

    Example:
    - Raw charge 20.5 nC
    - N_Dw = 0.045 Gy/nC (typical Farmer chamber order of magnitude)
    - k_Q = 0.994 (example for 6 MV)
    - All other factors = 1.0
    - Standard T/P
    """
    inp = PhotonMeasurementInput(
        raw_charge_nC=20.5,
        N_Dw=0.045,
        k_Q=0.994,
        k_pol=1.0,
        k_s=1.0,
        temperature_C=20.0,
        pressure_hPa=1013.25,
    )

    result = calculate_dose_to_water_photon(inp)

    expected = 20.5 * 0.045 * 0.994
    assert abs(result.dose_to_water_Gy - expected) < 1e-9
    assert abs(result.k_TP - 1.0) < 1e-9
    assert result.factors_used["k_Q"] == 0.994


def test_with_all_corrections():
    """Calculation including polarity, recombination and T/P."""
    inp = PhotonMeasurementInput(
        raw_charge_nC=18.75,
        electrometer_calibration_factor=1.002,
        N_Dw=0.0482,
        k_Q=0.991,
        k_pol=1.0015,
        k_s=1.004,
        temperature_C=21.5,
        pressure_hPa=1008.2,
    )

    result = calculate_dose_to_water_photon(inp)

    # Just check that it runs and returns positive dose
    assert result.dose_to_water_Gy > 0
    assert result.k_TP > 1.0
    assert "k_TP" in result.factors_used
