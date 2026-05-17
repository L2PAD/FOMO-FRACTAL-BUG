import { useMemo } from "react";
import { useTerminal } from "../../../store/terminalStore";

export default function StrategyContribution() {
  const { state } = useTerminal();

  const contribution = useMemo(() => {
    const positions = state.positions || [];
    const stats = {};
    let totalPnl = 0;

    // Aggregate by strategy
    positions.forEach(p => {
      const strategy = p.strategy || "unknown";
      const pnl = Number(p.unrealized_pnl || 0);
      
      if (!stats[strategy]) {
        stats[strategy] = 0;
      }
      
      stats[strategy] += pnl;
      totalPnl += pnl;
    });

    // Calculate contribution %
    const list = Object.entries(stats).map(([name, pnl]) => ({
      name: name.replace("_v2", "").replace("_", " ").toUpperCase(),
      pnl,
      contribution: totalPnl !== 0 ? (pnl / totalPnl) * 100 : 0
    }));

    // Sort by contribution descending
    list.sort((a, b) => b.contribution - a.contribution);

    return { list, totalPnl };
  }, [state.positions]);

  if (contribution.list.length === 0) {
    return (
      <div className="bg-neutral-50 rounded-xl p-4 border border-[#E5E7EB]" data-testid="strategy-contribution">
        <div className="text-xs font-semibold text-neutral-500 mb-3 tracking-wide">
          PNL CONTRIBUTION
        </div>

        <div className="text-sm text-neutral-400 text-center py-3">
          No contribution data
        </div>
      </div>
    );
  }

  const topContributor = contribution.list[0];
  const insight = topContributor.contribution > 60
    ? `→ Majority of profit driven by ${topContributor.name.toLowerCase()}`
    : "→ Profits distributed across multiple strategies";

  return (
    <div className="bg-blue-50 rounded-xl p-4 border border-blue-200" data-testid="strategy-contribution">
      <div className="text-xs font-semibold text-blue-700 mb-3 tracking-wide">
        📊 PNL CONTRIBUTION
      </div>

      <div className="space-y-2 text-sm mb-3">
        {contribution.list.map((s, i) => {
          const contributionColor = s.contribution >= 0 ? "text-green-600" : "text-red-600";
          const contributionSign = s.contribution >= 0 ? "+" : "";

          return (
            <div key={i} className="flex justify-between items-center" data-testid={`contribution-${i}`}>
              <span className="text-neutral-700">{s.name}</span>
              <span className={`font-mono tabular-nums font-semibold ${contributionColor}`}>
                {contributionSign}{s.contribution.toFixed(0)}%
              </span>
            </div>
          );
        })}
      </div>

      {/* Insight */}
      <div className="pt-3 border-t border-blue-300">
        <div className="text-xs text-blue-900">
          {insight}
        </div>
      </div>
    </div>
  );
}
