"""
ML Risk Overlay: Configuration & Feature Flags
All ML overlay, preflight gate, and confidence control settings.
"""
import hashlib

# ─── ML Overlay Stage 2 Config ───
ML_OVERLAY_ENABLED = True
ML_OVERLAY_MODE = "shadow_plus_live"  # shadow | shadow_plus_live | live
ML_OVERLAY_LIVE_PCT = 0.10            # 10% rollout
ML_OVERLAY_RISK_THRESHOLD = 0.85      # Only high-risk gets live modulation
ML_OVERLAY_KILL_SWITCH = False
ML_OVERLAY_CAP = 0.15                 # Max absolute confidence reduction
ML_OVERLAY_MULT_HIGH = 0.50           # Multiplier for risk >= 0.85
ML_OVERLAY_SALT = "ml_v1_stage2"      # Salt for stable hashing
ML_OVERLAY_COOLDOWN_HOURS = 24

# ─── Pre-Flight Quality Gate V1 Config ───
PREFLIGHT_ENABLED = True
PREFLIGHT_MODE = "shadow"              # shadow | live
PREFLIGHT_CONF_TARGET_THRESHOLD = 0.65
PREFLIGHT_BASE_PENALTY = 0.05
PREFLIGHT_CAP = 0.10
PREFLIGHT_USE_ML = False               # Require ML confirmation
PREFLIGHT_ML_THRESHOLD = 0.75

# ─── Global Confidence Control ───
FINAL_CONFIDENCE_FLOOR = 0.20          # Never go below this


def rollout_hash(forecast_id: str, salt: str = "") -> float:
    """
    Stable deterministic hash -> float in [0, 1).
    Same forecast_id + salt always gives same result.
    """
    h = hashlib.sha256(f"{forecast_id}{salt}".encode()).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF


def is_ml_live_eligible(forecast_id: str) -> bool:
    """Check if this forecast is in the live modulation cohort."""
    if ML_OVERLAY_KILL_SWITCH:
        return False
    if ML_OVERLAY_MODE == "shadow":
        return False
    return rollout_hash(forecast_id, ML_OVERLAY_SALT) < ML_OVERLAY_LIVE_PCT
