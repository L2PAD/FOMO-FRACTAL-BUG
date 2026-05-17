import { useMemo } from "react";

export default function ScenarioRailV2({ decision, explainability }) {
  const scenarios = useMemo(() => {
    if (!decision) {
      return [
        {
          title: "BASE",
          description: "Range continues",
          probability: 55,
          color: "bg-neutral-50 border-neutral-300 text-neutral-800 hover:border-neutral-400 hover:bg-neutral-100"
        },
        {
          title: "BREAKOUT",
          description: "Above 69,900",
          probability: 25,
          color: "bg-green-50 border-green-300 text-green-900 hover:border-green-400 hover:bg-green-100"
        },
        {
          title: "REVERSAL",
          description: "False move",
          probability: 20,
          color: "bg-red-50 border-red-300 text-red-900 hover:border-red-400 hover:bg-red-100"
        }
      ];
    }

    const side = decision.side;
    const target = Number(decision.target || 0);

    return [
      {
        title: "BASE",
        description: side === "SHORT" ? "Down to target" : "Up to target",
        probability: 60,
        color: "bg-neutral-50 border-neutral-300 text-neutral-800 hover:border-neutral-400 hover:bg-neutral-100"
      },
      {
        title: side === "SHORT" ? "BREAKDOWN" : "BREAKOUT",
        description: `${side === "SHORT" ? "Below" : "Above"} ${target.toFixed(0)}`,
        probability: 25,
        color: "bg-green-50 border-green-300 text-green-900 hover:border-green-400 hover:bg-green-100"
      },
      {
        title: "REVERSAL",
        description: "Stop hit",
        probability: 15,
        color: "bg-red-50 border-red-300 text-red-900 hover:border-red-400 hover:bg-red-100"
      }
    ];
  }, [decision]);

  return (
    <div className="grid grid-cols-3 gap-4" data-testid="scenario-rail-v2">
      {scenarios.map((scenario, i) => (
        <div 
          key={i}
          className={`rounded-xl p-4 border cursor-pointer transition-all duration-150 ease-out ${scenario.color}`}
          data-testid={`scenario-${i}`}
        >
          {/* Title */}
          <div className="text-xs font-bold mb-2 uppercase tracking-wider">
            {scenario.title}
          </div>

          {/* Description */}
          <div className="text-sm font-medium mb-2">
            {scenario.description}
          </div>

          {/* Probability */}
          <div className="text-xs opacity-70">
            {scenario.probability}%
          </div>
        </div>
      ))}
    </div>
  );
}
