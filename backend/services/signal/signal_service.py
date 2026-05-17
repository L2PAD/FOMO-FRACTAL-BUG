"""Signal Service — orchestrates signal computation.

Single entry point for routes that need the full signal package.
"""
from .signal_engine import compute_signal
from .reasons_engine import compute_reasons
from .drivers_engine import compute_drivers


def build_signal(features: dict) -> dict:
    """Build complete signal package: signal + reasons + drivers."""
    signal = compute_signal(features)
    reasons = compute_reasons(features, signal)
    drivers = compute_drivers(features)
    return {
        'signal': signal,
        'reasons': reasons,
        'drivers': drivers,
    }
