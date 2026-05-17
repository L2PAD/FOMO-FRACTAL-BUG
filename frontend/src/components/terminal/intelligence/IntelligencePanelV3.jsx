import { useMemo } from "react";

export default function IntelligencePanelV3({ decision, explainability, portfolio, heatmap }) {
  const regime = explainability?.regime || "CHOP";
  const volatility = explainability?.volatility || "LOW";
  const hasDecision = !!decision;
  const liquidity = heatmap?.imbalance_side || "BALANCED";
  const bias = decision ? decision.side : "NONE";

  return (
    <div className="flex flex-col h-full gap-4" data-testid="intelligence-panel-v3">
      
      {/* Section 1: MARKET */}
      <div className="bg-white rounded-xl p-4 border border-neutral-200 transition-all duration-150 hover:bg-neutral-50">
        <h3 className="text-xs font-bold text-neutral-500 mb-3 uppercase tracking-wider">
          MARKET
        </h3>

        <div className="space-y-2 text-sm mb-3">
          <div className="flex items-center gap-2">
            <div className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
            <div className="font-bold text-neutral-900 text-base">{regime.toUpperCase()}</div>
          </div>
          <div className="text-neutral-700">Volatility: {volatility.toUpperCase()}</div>
          <div className="text-neutral-700">Liquidity: {liquidity.toUpperCase()}</div>
        </div>

        <p className="text-sm text-neutral-600 italic">
          {hasDecision ? "→ Directional bias" : "→ No directional bias"}
        </p>
      </div>

      {/* Section 2: LOOKING FOR */}
      <div className="bg-blue-50 rounded-xl p-4 border border-blue-200 transition-all duration-150 hover:bg-blue-100">
        <h3 className="text-xs font-bold text-blue-900 mb-3 uppercase tracking-wider">
          LOOKING FOR
        </h3>

        <ul className="space-y-1.5 text-sm text-blue-900">
          {hasDecision ? (
            <>
              <li>• continuation</li>
              <li>• volume confirmation</li>
              <li>• follow-through</li>
            </>
          ) : (
            <>
              <li>• breakout</li>
              <li>• volatility expansion</li>
              <li>• liquidity imbalance</li>
            </>
          )}
        </ul>

        <p className="text-xs text-blue-900 mt-3 italic">
          {hasDecision ? "→ Monitoring confirmation" : "→ Waiting for confirmation"}
        </p>
      </div>

      {/* Section 3: INVALIDATION */}
      <div className="bg-orange-50 rounded-xl p-4 border border-orange-200 transition-all duration-150 hover:bg-orange-100">
        <h3 className="text-xs font-bold text-orange-900 mb-3 uppercase tracking-wider">
          INVALIDATION
        </h3>

        <ul className="space-y-1.5 text-sm text-orange-900">
          {hasDecision ? (
            <>
              <li>• stop hit</li>
              <li>• volume divergence</li>
            </>
          ) : (
            <>
              <li>• break above resistance</li>
              <li>• strong move down</li>
            </>
          )}
        </ul>

        <p className="text-xs text-orange-900 mt-3 italic">
          → Bias will change
        </p>
      </div>

    </div>
  );
}
