import { useMemo } from "react";
import { useTerminal } from "../../../store/terminalStore";

export default function StrategyInsightsPanel() {
  const { state } = useTerminal();

  const insights = useMemo(() => {
    const positions = state.positions || [];
    const regime = state.allocator?.regime || "CHOP";
    const stats = {};

    // Aggregate by strategy
    positions.forEach(p => {
      const strategy = p.strategy || "unknown";
      const pnl = Number(p.unrealized_pnl || 0);
      
      if (!stats[strategy]) {
        stats[strategy] = { pnl: 0, trades: 0 };
      }
      
      stats[strategy].pnl += pnl;
      stats[strategy].trades += 1;
    });

    // Find best and worst
    const list = Object.entries(stats).map(([name, data]) => ({
      name: name.replace("_v2", "").replace("_", " ").toLowerCase(),
      pnl: data.pnl,
      trades: data.trades
    }));

    list.sort((a, b) => b.pnl - a.pnl);

    const best = list[0];
    const worst = list[list.length - 1];

    const result = [];

    // Best regime fit
    if (best) {
      result.push({
        title: "Best Regime Fit",
        text: `${best.name} performs strongest in ${regime} regime`
      });
    }

    // Underperforming
    if (worst && worst.pnl < 0) {
      result.push({
        title: "Underperforming",
        text: `${worst.name} failing in low volatility environment`
      });
    }

    // Recommendation
    if (worst && worst.pnl < 0) {
      result.push({
        title: "Recommendation",
        text: `Reduce ${worst.name} exposure until volatility expands`
      });
    } else if (best) {
      result.push({
        title: "Recommendation",
        text: `Increase allocation to ${best.name} in current regime`
      });
    }

    return result;
  }, [state.positions, state.allocator]);

  if (insights.length === 0) {
    return (
      <div className="bg-white rounded-xl p-4 border border-[#E5E7EB]" data-testid="strategy-insights-panel">
        <div className="text-xs font-semibold text-neutral-500 mb-3 tracking-wide">
          STRATEGY INSIGHTS
        </div>

        <div className="text-sm text-neutral-400 text-center py-4">
          Waiting for data to generate insights
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl p-4 border border-[#E5E7EB]" data-testid="strategy-insights-panel">
      <div className="text-xs font-semibold text-neutral-500 mb-4 tracking-wide">
        STRATEGY INSIGHTS
      </div>

      <div className="space-y-4 text-sm">
        {insights.map((insight, i) => (
          <div key={i} data-testid={`insight-${i}`}>
            <div className="font-semibold text-neutral-900 mb-1">
              {insight.title}
            </div>
            <div className="text-neutral-700">
              {insight.text}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
