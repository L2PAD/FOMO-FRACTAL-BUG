import { useMemo } from "react";
import { useTerminal } from "../../../store/terminalStore";

// Helper: Decision Strength
const getDecisionStrength = (confidence, rr, mode) => {
  if (mode === "bootstrap") {
    return { label: "EXPLORATION", color: "bg-gray-100 text-gray-700 border-gray-300" };
  }

  if (confidence >= 70 && rr >= 2) {
    return { label: "STRONG SETUP", color: "bg-green-100 text-green-700 border-green-300" };
  }

  if (confidence >= 55) {
    return { label: "MODERATE EDGE", color: "bg-blue-100 text-blue-700 border-blue-300" };
  }

  return { label: "WEAK SETUP", color: "bg-yellow-100 text-yellow-700 border-yellow-300" };
};

export default function DecisionCommandCenter({ decision, explainability, heatmap }) {
  const { state } = useTerminal();
  
  // Calculate RR
  const rr = useMemo(() => {
    if (!decision) return null;
    const entry = Number(decision.entry || 0);
    const stop = Number(decision.stop || 0);
    const target = Number(decision.target || 0);
    if (!entry || !stop || !target) return null;
    const risk = Math.abs(entry - stop);
    const reward = Math.abs(target - entry);
    return risk > 0 ? (reward / risk).toFixed(2) : null;
  }, [decision]);

  // Calculate confidence (normalized score)
  const confidence = decision ? Math.round((decision.score || 0) * 100) : 0;

  // Execution quality
  const executionQuality = useMemo(() => {
    if (!decision) return { text: "N/A", color: "text-neutral-500" };
    const slippage = decision.execution_quality?.expected_slippage_bps || 5;
    const latency = decision.execution_quality?.expected_latency_ms || 120;
    if (slippage < 8 && latency < 150) return { text: "Acceptable", color: "text-green-700" };
    if (slippage < 12) return { text: "Moderate", color: "text-yellow-700" };
    return { text: "Poor", color: "text-red-700" };
  }, [decision]);

  // Portfolio fit
  const portfolioFit = useMemo(() => {
    const heat = state.portfolio?.risk_heat || 0;
    if (heat < 0.5) return { text: "High", color: "text-green-700" };
    if (heat < 0.7) return { text: "Medium", color: "text-yellow-700" };
    return { text: "Low", color: "text-red-700" };
  }, [state.portfolio]);

  // Risk state
  const riskState = explainability?.risk?.reason || "normal";
  const riskText = riskState.includes("normal") ? "Normal" : "Elevated";
  const riskColor = riskState.includes("normal") ? "text-green-700" : "text-yellow-700";

  // Reasoning
  const reasoning = useMemo(() => {
    if (!decision) return "";
    const strategy = decision.strategy || "unknown";
    const side = decision.side;
    const regime = explainability?.regime || "unknown";
    
    if (strategy.includes("meanrev")) {
      return `Mean reversion ${side.toLowerCase()} setup in ${regime.toUpperCase()} regime`;
    }
    if (strategy.includes("trend")) {
      return `Trend ${side.toLowerCase()} signal in ${regime.toUpperCase()} conditions`;
    }
    if (strategy.includes("breakout")) {
      return `Breakout ${side.toLowerCase()} opportunity after consolidation`;
    }
    return `${strategy} strategy ${side.toLowerCase()} signal`;
  }, [decision, explainability]);

  // What next (invalidation)
  const whatNext = useMemo(() => {
    if (!decision) return "";
    const side = decision.side;
    const stop = Number(decision.stop || 0);
    
    if (side === "SHORT") {
      return `If price reclaims above ${stop.toFixed(0)} → invalidate short thesis`;
    }
    return `If price breaks below ${stop.toFixed(0)} → invalidate long thesis`;
  }, [decision]);

  // Heatmap connection
  const liquidityContext = useMemo(() => {
    if (!decision || !heatmap?.summary) return null;
    
    const entry = Number(decision.entry || 0);
    const bidWall = heatmap.summary.top_bid_wall;
    const askWall = heatmap.summary.top_ask_wall;
    const side = decision.side;
    
    if (side === "SHORT" && askWall && askWall > entry) {
      const distance = ((askWall - entry) / entry * 100).toFixed(2);
      return {
        text: `Ask wall at ${askWall.toFixed(0)} (+${distance}%)`,
        implication: "Potential rejection zone nearby",
        color: "text-red-700"
      };
    }
    
    if (side === "LONG" && bidWall && bidWall < entry) {
      const distance = ((entry - bidWall) / entry * 100).toFixed(2);
      return {
        text: `Bid support at ${bidWall.toFixed(0)} (-${distance}%)`,
        implication: "Support zone below entry",
        color: "text-green-700"
      };
    }
    
    return null;
  }, [decision, heatmap]);

  // Early return AFTER all hooks
  if (!decision) {
    return (
      <div className="bg-white border border-neutral-200 rounded-lg p-6 mb-4">
        <div className="text-center text-neutral-500 text-sm">
          No active decision for this symbol
        </div>
      </div>
    );
  }

  const sideColor = decision.side === "LONG" ? "bg-green-100 text-green-900" : "bg-red-100 text-red-900";
  const sideBorderColor = decision.side === "LONG" ? "border-green-300" : "border-red-300";

  return (
    <div className={`bg-white border-2 ${sideBorderColor} rounded-lg p-6 mb-4 shadow-sm`}>
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="text-xs font-semibold text-neutral-500 tracking-wide">🧠 SYSTEM ACTION</div>
          <div className={`px-3 py-1 rounded-md font-bold text-sm ${sideColor}`}>
            {decision.side} {state.selectedSymbol}
          </div>
          <div className={`inline-flex px-2 py-1 rounded-md text-xs font-semibold border ${strength.color}`}>
            {strength.label}
          </div>
          <div className="px-2 py-1 rounded bg-green-50 text-green-800 text-xs font-semibold border border-green-200">
            BOOTSTRAP
          </div>
          <div className="px-2 py-1 rounded bg-neutral-100 text-neutral-700 text-xs font-semibold">
            {explainability?.regime?.toUpperCase() || "CHOP"}
          </div>
        </div>
      </div>

      {/* Core Metrics */}
      <div className="grid grid-cols-5 gap-4 mb-4 pb-4 border-b border-neutral-200">
        <div>
          <div className="text-xs text-neutral-500 mb-1">Confidence</div>
          <div className="text-lg font-bold text-neutral-900">{confidence}%</div>
        </div>
        <div>
          <div className="text-xs text-neutral-500 mb-1">RR</div>
          <div className="text-lg font-bold text-neutral-900">{rr || "N/A"}</div>
        </div>
        <div>
          <div className="text-xs text-neutral-500 mb-1">Execution</div>
          <div className={`text-sm font-semibold ${executionQuality.color}`}>{executionQuality.text}</div>
        </div>
        <div>
          <div className="text-xs text-neutral-500 mb-1">Portfolio Fit</div>
          <div className={`text-sm font-semibold ${portfolioFit.color}`}>{portfolioFit.text}</div>
        </div>
        <div>
          <div className="text-xs text-neutral-500 mb-1">Risk State</div>
          <div className={`text-sm font-semibold ${riskColor}`}>{riskText}</div>
        </div>
      </div>

      {/* Reason */}
      <div className="mb-4">
        <div className="text-xs font-semibold text-neutral-500 mb-1">Reason</div>
        <div className="text-sm text-neutral-800 leading-relaxed">
          {reasoning}
        </div>
      </div>

      {/* Liquidity Context */}
      {liquidityContext && (
        <div className="mb-4 p-3 bg-neutral-50 rounded border border-neutral-200">
          <div className="flex items-center gap-2">
            <div className="text-xs font-semibold text-neutral-600">Liquidity:</div>
            <div className={`text-xs font-semibold ${liquidityContext.color}`}>
              {liquidityContext.text}
            </div>
            <div className="text-xs text-neutral-600">→ {liquidityContext.implication}</div>
          </div>
        </div>
      )}

      {/* What Next */}
      <div className="mb-4">
        <div className="text-xs font-semibold text-neutral-500 mb-1">What Next</div>
        <div className="text-sm text-neutral-800">
          {whatNext}
        </div>
      </div>

      {/* Expected Outcome */}
      <div className="mb-4 p-3 bg-blue-50 rounded-lg border border-blue-200">
        <div className="text-xs font-semibold text-blue-700 mb-2">Expected Outcome</div>
        
        <div className="flex gap-4 text-xs text-blue-900">
          <div>
            <span className="text-blue-600">Win Prob:</span>{" "}
            <span className="font-semibold">{confidence >= 65 ? "65%" : confidence >= 55 ? "58%" : "52%"}</span>
          </div>
          <div>
            <span className="text-blue-600">Avg RR:</span>{" "}
            <span className="font-semibold">{rr || "1.5"}</span>
          </div>
          <div>
            <span className="text-blue-600">EV:</span>{" "}
            <span className="font-bold text-green-700">
              {rr ? `+${((confidence >= 65 ? 0.65 : 0.55) * Number(rr)).toFixed(2)}R` : "+0.75R"}
            </span>
          </div>
        </div>

        <div className="text-[11px] text-blue-700 mt-2">
          → {Number(rr) >= 1.5 && confidence >= 55 ? "Positive expectancy trade" : "Edge-based decision"}
        </div>

        {/* Confidence Calibration */}
        <div className="mt-2 pt-2 border-t border-blue-200 text-xs text-blue-800">
          Confidence: {confidence}%
          <span className="ml-1 text-blue-600">
            → Historically: {Math.round(historicalWinRate * 100)}% win rate
          </span>
        </div>
      </div>

      {/* If You Take This Trade (USER-CENTRIC - КРИТИЧНО) */}
      <div className="mb-4 p-4 bg-gradient-to-br from-gray-50 to-gray-100 rounded-xl border-2 border-gray-300">
        <div className="text-xs font-semibold text-gray-700 mb-3">
          💰 If You Take This Trade
        </div>

        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-gray-600">Risk if wrong</span>
            <span className="text-red-600 font-bold">
              -${riskUsd.toFixed(0)}
            </span>
          </div>

          <div className="flex justify-between text-sm">
            <span className="text-gray-600">Potential if correct</span>
            <span className="text-green-600 font-bold">
              +${rewardUsd.toFixed(0)}
            </span>
          </div>
        </div>

        <div className="text-xs text-gray-600 mt-3 pt-2 border-t border-gray-300">
          → You are risking <span className="font-semibold text-red-700">{riskPct.toFixed(2)}%</span>{" "}
          to gain <span className="font-semibold text-green-700">{rewardPct.toFixed(2)}%</span> of your capital
        </div>
      </div>

      {/* Position Impact (PROP DESK LEVEL) */}
      <div className="mb-4 p-4 bg-white border-2 border-orange-200 rounded-xl">
        <div className="text-xs font-semibold text-orange-700 mb-3">
          📊 Position Impact
        </div>

        <div className="space-y-2 text-sm text-gray-700">
          <div className="flex justify-between items-center">
            <span>Portfolio Heat:</span>
            <span>
              {currentHeat}% → 
              <span className={`ml-1 font-bold ${newHeat > 70 ? "text-red-600" : "text-orange-600"}`}>
                {newHeat}%
              </span>
            </span>
          </div>

          <div className="flex justify-between items-center">
            <span>{state.selectedSymbol.replace("USDT", "")} Exposure:</span>
            <span>
              {currentExposure}% →
              <span className="ml-1 font-semibold">
                {newExposure}%
              </span>
            </span>
          </div>
        </div>

        <div className="text-xs text-gray-600 mt-3 pt-2 border-t border-orange-200">
          → {newHeat > 70 
            ? "⚠️ High portfolio stress — risk of drawdown increases"
            : "✓ Portfolio remains within safe risk range"}
        </div>
      </div>

      {/* Do Nothing Option (ANTI-FOMO) */}
      <div className="mb-4 p-3 bg-purple-50 rounded-lg border border-purple-200">
        <div className="text-xs font-semibold text-purple-700 mb-2">
          🧘 Alternative
        </div>

        <div className="text-sm text-purple-900">
          No trade → preserves capital in {regime.toUpperCase()} regime
        </div>

        <div className="text-xs text-purple-700 mt-2">
          → Waiting may provide better entry conditions
        </div>
      </div>

      {/* Action Row */}
      <div className="flex items-center gap-2">
        <button
          className="px-4 py-2 bg-neutral-900 text-white text-xs font-semibold rounded hover:bg-neutral-800 transition-colors"
          data-testid="view-on-chart-btn"
        >
          VIEW ON CHART
        </button>
        <button
          className="px-4 py-2 bg-neutral-100 text-neutral-800 text-xs font-semibold rounded hover:bg-neutral-200 transition-colors"
          data-testid="execution-context-btn"
        >
          EXECUTION CONTEXT
        </button>
        <button
          className="px-4 py-2 bg-neutral-100 text-neutral-800 text-xs font-semibold rounded hover:bg-neutral-200 transition-colors"
          data-testid="why-not-others-btn"
        >
          WHY NOT OTHERS
        </button>
      </div>
    </div>
  );
}
