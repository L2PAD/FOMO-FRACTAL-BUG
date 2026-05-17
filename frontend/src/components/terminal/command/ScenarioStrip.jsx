import { useMemo } from "react";

export default function ScenarioStrip({ decision, explainability }) {
  const regime = explainability?.regime || "chop";

  const scenarios = useMemo(() => {
    if (!decision) {
      // PASS 6: NO EMPTY STATE - show intelligent waiting explanation
      return {
        baseCase: `${regime.toUpperCase()} regime detected`,
        bullCase: "Waiting for volatility expansion",
        failCase: "No directional bias until breakout"
      };
    }

    const side = decision.side;
    const strategy = decision.strategy || "unknown";
    const stop = Number(decision.stop || 0);

    // Base case
    let baseCase = "";
    if (strategy.includes("meanrev")) {
      baseCase = side === "SHORT" 
        ? "Mean reversion down to target"
        : "Mean reversion up to target";
    } else if (strategy.includes("trend")) {
      baseCase = side === "SHORT"
        ? "Trend continuation downward"
        : "Trend continuation upward";
    } else {
      baseCase = side === "SHORT" ? "Downside move" : "Upside move";
    }

    // Bull case (price goes up)
    const bullCase = side === "SHORT"
      ? "Breakout reclaim invalidates short"
      : "Strong breakout to upside";

    // Fail case (stop hit)
    const failCase = side === "SHORT"
      ? `Stop violation above ${stop.toFixed(0)}`
      : `Stop violation below ${stop.toFixed(0)}`;

    return { baseCase, bullCase, failCase };
  }, [decision, explainability, regime]);

  if (!scenarios) return null;

  // Color scheme changes based on decision state
  const baseColor = decision ? "bg-blue-50 border-blue-200 text-blue-700" : "bg-neutral-50 border-neutral-200 text-neutral-600";
  const bullColor = decision ? "bg-green-50 border-green-200 text-green-700" : "bg-neutral-50 border-neutral-200 text-neutral-600";
  const failColor = decision ? "bg-red-50 border-red-200 text-red-700" : "bg-neutral-50 border-neutral-200 text-neutral-600";

  const baseTitleColor = decision ? "text-blue-700" : "text-neutral-500";
  const bullTitleColor = decision ? "text-green-700" : "text-neutral-500";
  const failTitleColor = decision ? "text-red-700" : "text-neutral-500";

  const baseTextColor = decision ? "text-blue-900" : "text-neutral-700";
  const bullTextColor = decision ? "text-green-900" : "text-neutral-700";
  const failTextColor = decision ? "text-red-900" : "text-neutral-700";

  return (
    <div className="grid grid-cols-3 gap-3">
      <div className={`p-3 border rounded ${baseColor}`}>
        <div className={`text-xs font-semibold mb-1 ${baseTitleColor}`}>
          {decision ? "BASE CASE" : "MARKET STATE"}
        </div>
        <div className={`text-xs ${baseTextColor}`}>{scenarios.baseCase}</div>
      </div>
      <div className={`p-3 border rounded ${bullColor}`}>
        <div className={`text-xs font-semibold mb-1 ${bullTitleColor}`}>
          {decision ? "BULL CASE" : "LOOKING FOR"}
        </div>
        <div className={`text-xs ${bullTextColor}`}>{scenarios.bullCase}</div>
      </div>
      <div className={`p-3 border rounded ${failColor}`}>
        <div className={`text-xs font-semibold mb-1 ${failTitleColor}`}>
          {decision ? "FAIL CASE" : "AVOID"}
        </div>
        <div className={`text-xs ${failTextColor}`}>{scenarios.failCase}</div>
      </div>
    </div>
  );
}
