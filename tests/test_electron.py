"""
Unit tests for TRS-398 Electron absolute dosimetry calculations.
"""

import pytest
from app.calculations.electron import (
    calculate_dose_to_water_electron,
    ElectronMeasurementInput,
)


def test_basic_electron_dose():
    inp = ElectronMeasurementInput(
        raw_charge_nC=15.2,
        N_Dw=0.0475,
        k_Q=0.915,
        k_pol=1.0,
        k_s=1.003,
        temperature_C=20.0,
        pressure_hPa=1013.25,
        R50_cm=2.4,
        nominal_energy_MeV=9.0,
    )

    result = calculate_dose_to_water_electron(inp)

    expected = 15.2 * 0.0475 * 0.915 * 1.003
    assert abs(result.dose_to_water_Gy - expected) < 1e-9
    assert abs(result.k_TP - 1.0) < 1e-9
    assert result.factors_used["R50_cm"] == 2.4


def test_electron_with_TP_correction():
    inp = ElectronMeasurementInput(
        raw_charge_nC=12.8,
        N_Dw=0.046,
        k_Q=0.902,
        temperature_C=22.5,
        pressure_hPa=1005.0,
    )

    result = calculate_dose_to_water_electron(inp)
    assert result.dose_to_water_Gy > 0
    assert result.k_TP > 1.0
