import { useMemo } from "react";

function Metric({ label, value, color }) {
  return (
    <div className="flex justify-between text-xs text-gray-600">
      <span>{label}</span>
      <span className={`font-medium ${color || ""}`}>{value}</span>
    </div>
  );
}

function DecisionDetails({ decision }) {
  const isLong = decision ? decision.side === "LONG" : false;
  
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
  const kelly = decision ? (decision.kelly || 0) : 0;

  if (!decision) return null;

  return (
    <div className="rounded-xl border border-neutral-200 p-3 bg-white">
      <div className="text-xs text-gray-500 mb-2">Decision</div>

      <div className={`text-sm font-semibold ${isLong ? "text-green-600" : "text-red-600"}`}>
        {decision.side} • {decision.strategy}
      </div>

      <div className="mt-2 text-xs space-y-1 text-gray-700">
        <div>Entry: {Number(decision.entry).toFixed(2)}</div>
        <div>Stop: {Number(decision.stop).toFixed(2)}</div>
        <div>Target: {Number(decision.target).toFixed(2)}</div>
      </div>

      <div className="mt-3 text-xs space-y-1.5">
        <Metric label="Confidence" value={`${confidence}%`} />
        <Metric label="RR" value={rr || "N/A"} />
        <Metric label="Kelly" value={kelly.toFixed(3)} />
      </div>

      <div className="mt-3 text-[11px] text-gray-500 leading-relaxed">
        → {confidence > 65 ? "Strong" : "Moderate"} conviction setup with controlled risk
      </div>
    </div>
  );
}

function PortfolioFit({ decision, portfolio }) {
  const heat = portfolio ? (portfolio.risk_heat || 0) : 0;
  const positionsCount = portfolio ? (portfolio.positions_count || 0) : 0;
  const equity = portfolio ? (portfolio.equity || 0) : 0;

  const heatLabel =
    heat > 0.7 ? "HIGH" :
    heat > 0.5 ? "ELEVATED" :
    "NORMAL";

  const heatColor =
    heat > 0.7 ? "text-red-600" :
    heat > 0.5 ? "text-yellow-600" :
    "text-green-600";

  if (!decision || !portfolio) return null;

  return (
    <div className="rounded-xl border border-neutral-200 p-3 bg-white">
      <div className="text-xs text-gray-500 mb-2">Portfolio Fit</div>

      <div className="text-sm font-medium">
        Risk Heat: {Math.round(heat * 100)}% 
        <span className={`ml-1.5 text-xs font-semibold ${heatColor}`}>({heatLabel})</span>
      </div>

      <div className="mt-2 text-xs text-gray-700 space-y-1">
        <div>Positions: {positionsCount}</div>
        <div>Equity: ${equity.toFixed(0)}</div>
      </div>

      <div className="mt-3 text-[11px] text-gray-500 leading-relaxed">
        → Adding this trade {heat > 0.6 ? "increases drawdown sensitivity" : "keeps portfolio balanced"}
      </div>
    </div>
  );
}

function ExecutionContext({ decision, heatmap }) {
  const askWall = heatmap?.summary?.top_ask_wall;
  const bidWall = heatmap?.summary?.top_bid_wall;
  const entry = decision ? Number(decision.entry || 0) : 0;
  const side = decision ? decision.side : "";

  const nearbyResistance = side === "SHORT" && askWall && askWall > entry;
  const nearbySupport = side === "LONG" && bidWall && bidWall < entry;

  if (!decision) return null;

  return (
    <div className="rounded-xl border border-neutral-200 p-3 bg-white">
      <div className="text-xs text-gray-500 mb-2">Execution Context</div>

      <div className="text-xs space-y-1.5 text-gray-700">
        <div className="flex justify-between">
          <span>Ask Wall:</span>
          <span className="font-medium">{askWall ? askWall.toFixed(0) : "—"}</span>
        </div>
        <div className="flex justify-between">
          <span>Bid Support:</span>
          <span className="font-medium">{bidWall ? bidWall.toFixed(0) : "—"}</span>
        </div>
      </div>

      <div className="mt-3 text-[11px] text-gray-500 leading-relaxed">
        → {nearbyResistance && "Nearby liquidity may act as resistance"}
        {nearbySupport && "Support zone provides downside protection"}
        {!nearbyResistance && !nearbySupport && "Liquidity context neutral"}
      </div>
    </div>
  );
}

function AlternativeScenarios({ decision, explainability }) {
  const side = decision ? decision.side : "";
  const strategy = decision ? (decision.strategy || "") : "";
  const stop = decision ? Number(decision.stop || 0) : 0;

  const whyNotOpposite = useMemo(() => {
    if (!decision) return "";
    if (side === "SHORT") {
      if (strategy.includes("meanrev")) {
        return "No breakout confirmation and price in reversion zone";
      }
      return "Weak momentum and overhead resistance";
    } else {
      if (strategy.includes("meanrev")) {
        return "No breakdown confirmation and price in bounce zone";
      }
      return "Weak downside momentum and support holding";
    }
  }, [decision, side, strategy]);

  const whatFlips = useMemo(() => {
    if (!decision) return "";
    if (side === "SHORT") {
      return `Reclaim above ${stop.toFixed(0)} with volume`;
    }
    return `Break below ${stop.toFixed(0)} with volume`;
  }, [decision, side, stop]);

  if (!decision) return null;

  return (
    <div className="rounded-xl border border-neutral-200 p-3 bg-white">
      <div className="text-xs text-gray-500 mb-2">Alternative View</div>

      <div className="text-xs text-gray-700 space-y-3">
        <div>
          <div className="font-medium text-gray-800 mb-1">Why NOT opposite:</div>
          <div className="text-gray-600 text-[11px] leading-relaxed">
            {whyNotOpposite}
          </div>
        </div>

        <div>
          <div className="font-medium text-gray-800 mb-1">What flips bias:</div>
          <div className="text-gray-600 text-[11px] leading-relaxed">
            {whatFlips}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function RightIntelligencePanel({
  decision,
  explainability,
  portfolio,
  heatmap
}) {
  if (!decision) {
    return (
      <div className="w-[320px] h-full flex items-center justify-center p-4 border-l border-neutral-200 bg-white">
        <div className="text-center text-sm text-gray-500">
          Select a symbol to view intelligence
        </div>
      </div>
    );
  }

  return (
    <div className="w-[320px] h-full flex flex-col gap-3 p-3 border-l border-neutral-200 bg-neutral-50 overflow-y-auto">
      <DecisionDetails decision={decision} />
      <PortfolioFit decision={decision} portfolio={portfolio} />
      <ExecutionContext decision={decision} heatmap={heatmap} />
      <AlternativeScenarios decision={decision} explainability={explainability} />
    </div>
  );
}
