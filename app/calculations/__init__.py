"""
Pure physics calculation library.
No FastAPI, no database, no side effects.
Easy to unit-test and later reuse.
"""

from .photon import calculate_dose_to_water_photon

__all__ = ["calculate_dose_to_water_photon"]
