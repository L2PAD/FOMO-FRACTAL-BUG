import { useMemo } from "react";

export default function OutcomeSummary({ decisions, positions }) {
  const stats = useMemo(() => {
    if (!positions || positions.length === 0) {
      return { wins: 0, losses: 0, total: 0, winRate: 0, avgPnl: 0 };
    }

    const closedPositions = positions.filter(p => p.status === "CLOSED");
    
    const wins = closedPositions.filter(p => {
      const pnl = Number(p.pnl_usd || p.unrealized_pnl || 0);
      return pnl > 0;
    }).length;

    const losses = closedPositions.filter(p => {
      const pnl = Number(p.pnl_usd || p.unrealized_pnl || 0);
      return pnl < 0;
    }).length;

    const total = wins + losses || 1;
    const winRate = (wins / total) * 100;

    const totalPnl = closedPositions.reduce((sum, p) => {
      return sum + Number(p.pnl_usd || p.unrealized_pnl || 0);
    }, 0);

    const avgPnl = closedPositions.length > 0 ? totalPnl / closedPositions.length : 0;

    return { wins, losses, total, winRate, avgPnl };
  }, [positions]);

  // If no closed positions, show active stats
  const activeCount = positions?.filter(p => p.status === "OPEN").length || 0;

  return (
    <div className="rounded-xl border border-neutral-200 p-3 bg-white">
      <div className="text-xs text-gray-500 mb-2">Performance Summary</div>

      {stats.total > 0 ? (
        <>
          <div className="text-sm font-medium text-gray-800">
            Win Rate: {Math.round(stats.winRate)}%
          </div>

          <div className="text-xs text-gray-600 mt-1.5 space-y-0.5">
            <div>Wins: {stats.wins} • Losses: {stats.losses}</div>
            <div>Avg PnL: {stats.avgPnl >= 0 ? "+" : ""}{stats.avgPnl.toFixed(2)} USD</div>
          </div>

          <div className="text-[11px] text-gray-500 mt-2 leading-relaxed">
            → {stats.winRate >= 60 ? "Strong" : stats.winRate >= 50 ? "Moderate" : "Below target"} performance
          </div>
        </>
      ) : (
        <>
          <div className="text-sm font-medium text-gray-800">
            Active Positions: {activeCount}
          </div>

          <div className="text-xs text-gray-600 mt-1.5">
            No closed positions yet
          </div>

          <div className="text-[11px] text-gray-500 mt-2 leading-relaxed">
            → Building track record in BOOTSTRAP mode
          </div>
        </>
      )}
    </div>
  );
}
