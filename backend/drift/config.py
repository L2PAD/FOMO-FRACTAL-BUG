"""
Drift Monitoring — Configuration
"""

# Drift score weights
DRIFT_WEIGHTS = {
    "psi": 0.4,
    "dir_hit_drop": 0.3,
    "mae_growth": 0.2,
    "flip_spike": 0.1,
}

# ML Weight decay
ALPHA = 2.0  # exp(-alpha * driftScore)

# PSI bins
PSI_BINS = 10

# Thresholds
PSI_WATCH = 0.10
PSI_DRIFT = 0.20
KS_WATCH = 0.12
KS_DRIFT = 0.20
ECE_WATCH = 0.08
ECE_DRIFT = 0.12

# Calibration gate: mlWeight *= exp(-ECE_ALPHA * ECE)
ECE_ALPHA = 3.0

# Rolling windows
PERF_WINDOW_DAYS = 60
FEATURE_WINDOW_DAYS = 60
