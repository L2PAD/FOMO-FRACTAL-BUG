"""
ML Overlay — Residual correction on top of rule-based forecast.

Learns: error = real_return - rule_return
Applies: final_return = rule_return + clip(ml_correction, -cap, +cap)
"""
