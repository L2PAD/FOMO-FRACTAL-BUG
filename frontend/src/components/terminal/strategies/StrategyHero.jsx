import { useMemo } from "react";
import { useTerminal } from "../../../store/terminalStore";

export default function StrategyHero() {
  const { state } = useTerminal();

  // Calculate strategy stats from positions
  const strategyStats = useMemo(() => {
    const positions = state.positions || [];
    const decisions = state.allocator?.decisions || [];

    // Aggregate by strategy
    const stats = {};
    
    positions.forEach(p => {
      const strategy = p.strategy || "unknown";
      if (!stats[strategy]) {
        stats[strategy] = { pnl: 0, wins: 0, losses: 0, trades: 0 };
      }
      
      const pnl = Number(p.unrealized_pnl || 0);
      stats[strategy].pnl += pnl;
      stats[strategy].trades += 1;
      
      if (pnl > 0) stats[strategy].wins += 1;
      if (pnl < 0) stats[strategy].losses += 1;
    });

    // Add active decisions (potential)
    decisions.forEach(d => {
      const strategy = d.strategy || "unknown";
      if (!stats[strategy]) {
        stats[strategy] = { pnl: 0, wins: 0, losses: 0, trades: 0 };
      }
    });

    // Convert to array and calculate win rate
    const list = Object.entries(stats).map(([name, data]) => ({
      name: name.replace("_v2", "").replace("_", " ").toUpperCase(),
      pnl: data.pnl,
      winRate: data.trades > 0 ? (data.wins / data.trades) * 100 : 0,
      trades: data.trades
    }));

    // Sort by PnL
    list.sort((a, b) => b.pnl - a.pnl);

    return list[0] || null;
  }, [state.positions, state.allocator]);

  const regime = state.allocator?.regime || "CHOP";

  if (!strategyStats) {
    return (
      <div className="bg-white rounded-xl p-6 border border-[#E5E7EB]" data-testid="strategy-hero">
        <div className="text-xs font-semibold text-neutral-500 mb-3 tracking-wide">
          STRATEGY PERFORMANCE
        </div>

        <div className="text-center py-4">
          <div className="text-lg font-semibold text-neutral-400 mb-2">
            NO ACTIVE STRATEGIES
          </div>
          <div className="text-sm text-neutral-500">
            → Waiting for signals
          </div>
        </div>
      </div>
    );
  }

  const pnlColor = strategyStats.pnl >= 0 ? "text-green-600" : "text-red-600";
  const pnlSign = strategyStats.pnl >= 0 ? "+" : "";

  return (
    <div className="bg-white rounded-xl p-6 border border-[#E5E7EB] shadow-sm" data-testid="strategy-hero">
      <div className="text-xs font-semibold text-neutral-500 mb-3 tracking-wide">
        STRATEGY PERFORMANCE
      </div>

      <div className="flex justify-between items-end mb-4">
        {/* Best Strategy */}
        <div>
          <div className="text-2xl font-bold text-neutral-900 mb-1">
            {strategyStats.name}
          </div>
          <div className="text-sm text-neutral-600">
            Best performing in {regime} regime
          </div>
        </div>

        {/* PnL */}
        <div className="text-right">
          <div className={`text-xl font-bold ${pnlColor} font-mono tabular-nums`}>
            {pnlSign}${Math.abs(strategyStats.pnl).toFixed(0)}
          </div>
          <div className="text-xs text-neutral-500 mt-1">
            Win rate: {strategyStats.winRate.toFixed(0)}%
          </div>
        </div>
      </div>

      {/* Message */}
      <div className="pt-3 border-t border-[#E5E7EB]">
        <div className="text-sm text-neutral-700">
          → Currently strongest edge in current market
        </div>
      </div>
    </div>
  );
}
