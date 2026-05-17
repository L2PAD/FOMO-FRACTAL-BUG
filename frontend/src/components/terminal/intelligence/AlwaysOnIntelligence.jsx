import { useMemo } from "react";

function Metric({ label, value, color }) {
  return (
    <div className="flex justify-between text-xs text-gray-600">
      <span>{label}</span>
      <span className={`font-medium ${color || ""}`}>{value}</span>
    </div>
  );
}

export default function AlwaysOnIntelligence({
  decision,
  explainability,
  portfolio,
  heatmap
}) {
  const regime = explainability?.regime || "chop";
  const mode = explainability?.mode || "bootstrap";

  // Scenario 1: NO DECISION - Show Market Intelligence
  if (!decision) {
    const volatility = heatmap?.mid_price ? "LOW" : "UNKNOWN";
    const liquidity = heatmap?.summary?.top_bid_wall ? "BALANCED" : "UNKNOWN";

    return (
      <div className="w-[320px] h-full flex flex-col gap-3 p-3 border-l border-neutral-200 bg-white overflow-y-auto">
        {/* Market Intelligence */}
        <div className="rounded-xl border border-neutral-200 p-4 bg-white shadow-sm">
          <div className="text-xs font-semibold text-neutral-500 mb-3">📊 MARKET INTELLIGENCE</div>

          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-neutral-600">Regime:</span>
              <span className="font-semibold text-neutral-900">{regime.toUpperCase()}</span>
            </div>

            <div className="flex justify-between">
              <span className="text-neutral-600">Volatility:</span>
              <span className="font-semibold text-neutral-900">{volatility}</span>
            </div>

            <div className="flex justify-between">
              <span className="text-neutral-600">Liquidity:</span>
              <span className="font-semibold text-neutral-900">{liquidity}</span>
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-neutral-200 text-xs text-neutral-600 space-y-1">
            <div>→ No directional bias</div>
            <div>→ Breakout required for entry</div>
          </div>
        </div>

        {/* System Status */}
        <div className="rounded-xl border border-neutral-200 p-4 bg-neutral-50">
          <div className="text-xs font-semibold text-neutral-500 mb-2">System Status</div>
          
          <div className="text-sm text-neutral-700">
            Scanning for imbalance
          </div>

          <div className="mt-2 text-xs text-neutral-600">
            → Waiting for high-quality setup
          </div>
        </div>

        {/* What System is Looking For */}
        <div className="rounded-xl border border-neutral-200 p-4 bg-blue-50">
          <div className="text-xs font-semibold text-blue-700 mb-2">Looking For</div>
          
          <div className="space-y-1 text-xs text-blue-900">
            <div>• Volatility expansion</div>
            <div>• Clear directional edge</div>
            <div>• Liquidity imbalance</div>
          </div>
        </div>
      </div>
    );
  }

  // Scenario 2: ACTIVE DECISION - Show Trade Context
  const strategy = decision.strategy || "unknown";
  const side = decision.side;
  const stop = Number(decision.stop || 0);

  const whyThisTrade = useMemo(() => {
    if (strategy.includes("meanrev")) {
      return ["Range rejection", "Price deviation from mean", "Low volatility setup"];
    }
    if (strategy.includes("trend")) {
      return ["Trend continuation", "Momentum alignment", "Breakout confirmation"];
    }
    return ["Strategy signal", "Risk/reward favorable"];
  }, [strategy]);

  const whyNotOpposite = useMemo(() => {
    if (side === "SHORT") {
      return "No breakout confirmation and overhead resistance";
    }
    return "No breakdown confirmation and support holding";
  }, [side]);

  const whatFlips = useMemo(() => {
    if (side === "SHORT") {
      return `Break above ${stop.toFixed(0)} with volume`;
    }
    return `Break below ${stop.toFixed(0)} with volume`;
  }, [side, stop]);

  return (
    <div className="w-[320px] h-full flex flex-col gap-3 p-3 border-l border-neutral-200 bg-white overflow-y-auto">
      {/* Trade Context */}
      <div className="rounded-xl border border-neutral-200 p-4 bg-white shadow-sm">
        <div className="text-xs font-semibold text-neutral-500 mb-3">📊 TRADE CONTEXT</div>

        <div>
          <div className="text-xs font-semibold text-neutral-700 mb-2">Why this trade:</div>
          <div className="space-y-1 text-xs text-neutral-600">
            {whyThisTrade.map((reason, i) => (
              <div key={i}>• {reason}</div>
            ))}
          </div>
        </div>

        <div className="mt-4">
          <div className="text-xs font-semibold text-neutral-700 mb-1">Why not opposite:</div>
          <div className="text-xs text-neutral-600">
            {whyNotOpposite}
          </div>
        </div>

        <div className="mt-4">
          <div className="text-xs font-semibold text-neutral-700 mb-1">What flips bias:</div>
          <div className="text-xs text-neutral-600">
            → {whatFlips}
          </div>
        </div>
      </div>

      {/* Portfolio Fit */}
      <div className="rounded-xl border border-orange-200 p-4 bg-orange-50">
        <div className="text-xs font-semibold text-orange-700 mb-2">Portfolio Fit</div>

        <div className="text-sm">
          Risk Heat: <span className="font-semibold">{Math.round((portfolio?.risk_heat || 0) * 100)}%</span>
        </div>

        <div className="mt-2 text-xs text-orange-700">
          → {(portfolio?.risk_heat || 0) > 0.6 
            ? "Elevated heat increases drawdown sensitivity"
            : "Portfolio within safe risk range"}
        </div>
      </div>

      {/* Execution Context */}
      <div className="rounded-xl border border-neutral-200 p-4 bg-neutral-50">
        <div className="text-xs font-semibold text-neutral-500 mb-2">Execution Context</div>

        <div className="space-y-1 text-xs text-neutral-600">
          <div className="flex justify-between">
            <span>Ask Wall:</span>
            <span>{heatmap?.summary?.top_ask_wall?.toFixed(0) || "—"}</span>
          </div>
          <div className="flex justify-between">
            <span>Bid Support:</span>
            <span>{heatmap?.summary?.top_bid_wall?.toFixed(0) || "—"}</span>
          </div>
        </div>

        <div className="mt-2 text-xs text-neutral-600">
          → Liquidity context {side === "SHORT" ? "resistance nearby" : "support below"}
        </div>
      </div>
    </div>
  );
}
