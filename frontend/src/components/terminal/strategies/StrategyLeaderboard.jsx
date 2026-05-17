import { useMemo } from "react";
import { useTerminal } from "../../../store/terminalStore";

export default function StrategyLeaderboard() {
  const { state } = useTerminal();

  const strategies = useMemo(() => {
    const positions = state.positions || [];
    const stats = {};

    // Aggregate by strategy
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

    // Convert to array
    const list = Object.entries(stats).map(([name, data]) => ({
      name: name.replace("_v2", "").replace("_", " ").toUpperCase(),
      pnl: data.pnl,
      winRate: data.trades > 0 ? (data.wins / data.trades) * 100 : 0,
      trades: data.trades
    }));

    // Sort by PnL descending
    list.sort((a, b) => b.pnl - a.pnl);

    return list;
  }, [state.positions]);

  if (strategies.length === 0) {
    return (
      <div className="bg-white rounded-xl p-4 border border-[#E5E7EB]" data-testid="strategy-leaderboard">
        <div className="text-xs font-semibold text-neutral-500 mb-3 tracking-wide">
          STRATEGY LEADERBOARD
        </div>

        <div className="text-sm text-neutral-400 text-center py-4">
          No strategy data available
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl p-4 border border-[#E5E7EB]" data-testid="strategy-leaderboard">
      <div className="text-xs font-semibold text-neutral-500 mb-4 tracking-wide">
        STRATEGY LEADERBOARD
      </div>

      <div className="space-y-3">
        {strategies.map((s, i) => {
          const pnlColor = s.pnl >= 0 ? "text-green-600" : "text-red-600";
          const pnlSign = s.pnl >= 0 ? "+" : "";

          return (
            <div key={i} className="flex justify-between items-center text-sm" data-testid={`strategy-item-${i}`}>
              {/* Strategy Name */}
              <div className="flex-1">
                <div className="font-semibold text-neutral-900">
                  {s.name}
                </div>
                <div className="text-xs text-neutral-500">
                  {s.trades} trades
                </div>
              </div>

              {/* PnL + Win Rate */}
              <div className="text-right">
                <div className={`font-bold font-mono tabular-nums ${pnlColor}`}>
                  {pnlSign}${Math.abs(s.pnl).toFixed(0)}
                </div>
                <div className="text-xs text-neutral-500">
                  {s.winRate.toFixed(0)}% win
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
