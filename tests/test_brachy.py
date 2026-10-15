"""
Unit tests for brachytherapy well-chamber source strength calculations.
"""

import pytest
from app.calculations.brachy import (
    calculate_air_kerma_strength,
    BrachyWellInput,
    decay_factor,
)


def test_basic_ir192():
    inp = BrachyWellInput(
        raw_reading=12.5,          # nA
        N_SK=0.85,                 # example calibration factor
        temperature_C=20.0,
        pressure_hPa=1013.25,
        nuclide="Ir-192",
    )
    result = calculate_air_kerma_strength(inp)
    expected = 12.5 * 0.85
    assert abs(result.air_kerma_strength - expected) < 1e-9
    assert abs(result.decay_factor - 1.0) < 1e-9


def test_decay_factor_ir192():
    # Roughly one half-life later should be ~0.5
    df = decay_factor(
        "Ir-192",
        "2025-01-01T00:00:00",
        "2025-03-15T00:00:00",   # ~73 days
    )
    assert 0.48 < df < 0.52
