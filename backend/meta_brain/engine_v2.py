from __future__ import annotations
from .contracts import ProviderSignal
from .feature_builder import build_meta_features
from .rule_engine import meta_rule_decision
from .target_builder import build_targets


class MetaBrainV2:
    def __init__(self, ml_model=None):
        self.ml_model = ml_model

    def predict(
        self,
        exchange: ProviderSignal,
        sentiment: ProviderSignal,
        fractal: ProviderSignal,
        onchain: ProviderSignal,
        regime: str,
        volatility: float,
        price_now: float,
        price_change_1d: float = 0.0,
        price_change_7d: float = 0.0,
        price_change_30d: float = 0.0,
        sma20_distance: float = 0.0,
    ) -> dict:
        features = build_meta_features(
            exchange=exchange,
            sentiment=sentiment,
            fractal=fractal,
            onchain=onchain,
            regime=regime,
            volatility=volatility,
            price_change_1d=price_change_1d,
            price_change_7d=price_change_7d,
            price_change_30d=price_change_30d,
            sma20_distance=sma20_distance,
        )

        rule_out = meta_rule_decision(features)

        targets = build_targets(
            price_now=price_now,
            direction=rule_out["direction"],
            confidence=rule_out["confidence"],
            volatility=volatility,
        )

        final = {
            "direction": rule_out["direction"],
            "confidence": rule_out["confidence"],
            "score": rule_out["score"],
            "threshold": rule_out["threshold"],
            "mode": "rule_only",
            "components": rule_out["features"],
            "targets": targets,
        }

        if self.ml_model is not None:
            final["mode"] = "hybrid"

        return final
