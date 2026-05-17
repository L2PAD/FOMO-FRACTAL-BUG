import { useMemo } from "react";

export default function ScenarioRail({ decision, explainability }) {
  const regime = explainability?.regime || "chop";

  const scenarios = useMemo(() => {
    if (!decision) {
      // NO DECISION: General market scenarios
      return [
        {
          title: "BASE CASE",
          description: "Range continues, no edge",
          probability: 55,
          color: "bg-neutral-50 border-neutral-300 text-neutral-800"
        },
        {
          title: "BULL TRIGGER",
          description: "Break and hold above resistance",
          probability: 25,
          color: "bg-green-50 border-green-300 text-green-900"
        },
        {
          title: "RISK CASE",
          description: "False breakout and sharp reversal",
          probability: 20,
          color: "bg-red-50 border-red-300 text-red-900"
        }
      ];
    }

    // HAS DECISION: Trade-specific scenarios
    const side = decision.side;
    const target = Number(decision.target || 0);
    const stop = Number(decision.stop || 0);

    return [
      {
        title: "BASE CASE",
        description: side === "SHORT" 
          ? "Mean reversion down to target" 
          : "Trend continuation upward",
        probability: 60,
        color: "bg-blue-50 border-blue-300 text-blue-900"
      },
      {
        title: side === "SHORT" ? "BEARISH TRIGGER" : "BULLISH TRIGGER",
        description: side === "SHORT"
          ? `Strong breakdown below ${target.toFixed(0)}`
          : `Breakout above ${target.toFixed(0)}`,
        probability: 25,
        color: "bg-green-50 border-green-300 text-green-900"
      },
      {
        title: "RISK CASE",
        description: `Stop violation ${side === "SHORT" ? "above" : "below"} ${stop.toFixed(0)}`,
        probability: 15,
        color: "bg-red-50 border-red-300 text-red-900"
      }
    ];
  }, [decision, explainability, regime]);

  return (
    <div className="grid grid-cols-3 gap-4" data-testid="scenario-rail">
      {scenarios.map((scenario, i) => (
        <div 
          key={i}
          className={`rounded-xl p-5 border-2 ${scenario.color}`}
          data-testid={`scenario-${i}`}
        >
          {/* Title */}
          <div className="text-xs font-bold mb-2 tracking-wide opacity-80">
            {scenario.title}
          </div>

          {/* Description */}
          <div className="text-sm font-semibold mb-3">
            {scenario.description}
          </div>

          {/* Probability */}
          <div className="text-xs font-medium opacity-70">
            Probability: {scenario.probability}%
          </div>
        </div>
      ))}
    </div>
  );
}
