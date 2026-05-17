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

export default function HeroBlock({ decision, explainability, heatmap }) {
  const { state } = useTerminal();

  const regime = explainability?.regime || "chop";
  const mode = explainability?.mode || "bootstrap";

  // Calculate metrics if decision exists
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

  const confidence = decision ? Math.round((decision.score || 0) * 100) : 0;
  const strength = decision ? getDecisionStrength(confidence, Number(rr), mode) : null;

  // Scenario 1: NO TRADE
  if (!decision) {
    return (
      <div className="bg-white rounded-xl shadow-sm border border-neutral-200 p-8 mb-4">
        {/* Header */}
        <div className="flex items-center gap-3 mb-4">
          <div className="text-sm font-semibold text-neutral-500 tracking-wide">🧠 MARKET STATE</div>
          <div className="px-3 py-1 rounded-md text-xs font-semibold bg-gray-100 text-gray-700 border border-gray-300">
            {mode.toUpperCase()}
          </div>
        </div>

        {/* Main Title */}
        <div className="text-2xl font-bold text-neutral-900 mb-3">
          NO HIGH-QUALITY SETUP
        </div>

        {/* Market Info */}
        <div className="text-sm text-neutral-600 mb-4">
          Market: <span className="font-semibold">{regime.toUpperCase()}</span> (range-bound)
        </div>

        {/* Implications */}
        <div className="space-y-2 text-sm text-neutral-700 mb-6">
          <div>→ No directional edge detected</div>
          <div>→ System is waiting for volatility expansion</div>
        </div>

        {/* Best Action */}
        <div className="pt-4 border-t border-neutral-200">
          <div className="text-xs font-semibold text-neutral-500 mb-2">Best Action</div>
          <div className="text-lg font-bold text-neutral-900">WAIT</div>
        </div>

        {/* Status Row */}
        <div className="flex gap-6 mt-4">
          <div>
            <div className="text-xs text-neutral-500">Confidence</div>
            <div className="text-sm font-semibold text-neutral-700">LOW</div>
          </div>
          <div>
            <div className="text-xs text-neutral-500">Opportunity</div>
            <div className="text-sm font-semibold text-neutral-700">WEAK</div>
          </div>
        </div>
      </div>
    );
  }

  // Scenario 2: ACTIVE TRADE
  const entry = Number(decision.entry || 0);
  const stop = Number(decision.stop || 0);
  const target = Number(decision.target || 0);
  const sideColor = decision.side === "LONG" ? "text-green-700" : "text-red-700";

  return (
    <div className="bg-white rounded-xl shadow-md border-2 border-neutral-300 p-8 mb-4">
      {/* Header */}
      <div className="flex items-center gap-3 mb-4">
        <div className="text-sm font-semibold text-neutral-500 tracking-wide">🧠 ACTION</div>
        <div className="px-3 py-1 rounded-md text-xs font-semibold bg-green-100 text-green-800 border border-green-300">
          {mode.toUpperCase()}
        </div>
        {strength && (
          <div className={`px-3 py-1 rounded-md text-xs font-semibold border ${strength.color}`}>
            {strength.label}
          </div>
        )}
      </div>

      {/* Main Title */}
      <div className={`text-3xl font-bold mb-2 ${sideColor}`}>
        {decision.side} {state.selectedSymbol}
      </div>

      {/* Metrics Row */}
      <div className="flex gap-6 mb-4 text-sm">
        <div>
          <span className="text-neutral-600">Confidence:</span>{" "}
          <span className="font-bold text-neutral-900">{confidence}%</span>
        </div>
        <div>
          <span className="text-neutral-600">RR:</span>{" "}
          <span className="font-bold text-neutral-900">{rr || "N/A"}</span>
        </div>
      </div>

      {/* Reasoning */}
      <div className="space-y-2 text-sm text-neutral-700 mb-6">
        <div>
          → {decision.strategy?.includes("meanrev") 
            ? `Mean reversion ${decision.side.toLowerCase()} setup in ${regime.toUpperCase()} regime`
            : `${decision.strategy} ${decision.side.toLowerCase()} signal`}
        </div>
        {heatmap?.summary && (
          <div>
            → Liquidity {decision.side === "SHORT" ? "above" : "below"} reinforces {decision.side.toLowerCase()} thesis
          </div>
        )}
      </div>

      {/* Warning */}
      <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
        <div className="text-xs font-semibold text-yellow-800 mb-1">⚠️ Invalidation</div>
        <div className="text-sm text-yellow-900">
          If price {decision.side === "SHORT" ? "reclaims above" : "breaks below"} {stop.toFixed(0)} → exit immediately
        </div>
      </div>
    </div>
  );
}
