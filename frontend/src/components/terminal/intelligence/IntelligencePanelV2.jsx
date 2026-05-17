import { useMemo } from "react";

export default function IntelligencePanelV2({ decision, explainability, portfolio, heatmap }) {
  const regime = explainability?.regime || "CHOP";
  const volatility = explainability?.volatility || "LOW";
  const hasDecision = !!decision;

  // Market Intelligence
  const marketIntel = useMemo(() => {
    const liquidity = heatmap?.imbalance_side || "BALANCED";
    const bias = decision ? decision.side : "NONE";

    return {
      regime: regime.toUpperCase(),
      volatility: volatility.toUpperCase(),
      liquidity: liquidity.toUpperCase(),
      bias,
      explanation: hasDecision
        ? "Market shows directional opportunity."
        : "Market has no directional edge. Breakout confirmation required."
    };
  }, [regime, volatility, heatmap, decision, hasDecision]);

  // What system is looking for
  const lookingFor = useMemo(() => {
    if (hasDecision) {
      return [
        "continuation in direction",
        "volume confirmation",
        "liquidity follow-through"
      ];
    }

    return [
      "volatility expansion",
      "imbalance near liquidity",
      "breakout confirmation"
    ];
  }, [hasDecision]);

  const lookingForExplanation = hasDecision
    ? "System monitors for trade confirmation signals."
    : "System remains defensive until directional confirmation appears.";

  // What invalidates
  const invalidates = useMemo(() => {
    if (hasDecision) {
      const stop = Number(decision.stop || 0);
      return [
        `stop hit at ${stop.toFixed(0)}`,
        "volume divergence",
        "liquidity reversal"
      ];
    }

    return [
      "breakout above ask wall",
      "sharp downside displacement",
      "expanding volume"
    ];
  }, [hasDecision, decision]);

  return (
    <div className="flex flex-col h-full gap-4" data-testid="intelligence-panel-v2">
      
      {/* Section 1: Market Intelligence */}
      <div className="bg-white rounded-xl p-5 border border-neutral-200">
        <h3 className="text-sm font-bold text-neutral-900 mb-4 tracking-wide">
          MARKET INTELLIGENCE
        </h3>

        <div className="space-y-2.5 text-sm mb-4">
          <div className="flex justify-between">
            <span className="text-neutral-600">Regime:</span>
            <span className="font-semibold text-neutral-900">{marketIntel.regime}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-neutral-600">Volatility:</span>
            <span className="font-semibold text-neutral-900">{marketIntel.volatility}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-neutral-600">Liquidity:</span>
            <span className="font-semibold text-neutral-900">{marketIntel.liquidity}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-neutral-600">Bias:</span>
            <span className="font-semibold text-neutral-900">{marketIntel.bias}</span>
          </div>
        </div>

        <p className="text-sm text-neutral-700 italic">
          {marketIntel.explanation}
        </p>
      </div>

      {/* Section 2: What system is looking for */}
      <div className="bg-blue-50 rounded-xl p-5 border border-blue-200">
        <h3 className="text-sm font-bold text-blue-900 mb-3 tracking-wide">
          WHAT SYSTEM IS LOOKING FOR
        </h3>

        <ul className="space-y-2 text-sm text-blue-900 mb-3">
          {lookingFor.map((item, i) => (
            <li key={i} className="flex items-start">
              <span className="mr-2">•</span>
              <span>{item}</span>
            </li>
          ))}
        </ul>

        <p className="text-sm text-blue-900 italic">
          {lookingForExplanation}
        </p>
      </div>

      {/* Section 3: What invalidates */}
      <div className="bg-orange-50 rounded-xl p-5 border border-orange-200">
        <h3 className="text-sm font-bold text-orange-900 mb-3 tracking-wide">
          {hasDecision ? "WHAT INVALIDATES TRADE" : "WHAT INVALIDATES WAITING"}
        </h3>

        <ul className="space-y-2 text-sm text-orange-900">
          {invalidates.map((item, i) => (
            <li key={i} className="flex items-start">
              <span className="mr-2">•</span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </div>

    </div>
  );
}
