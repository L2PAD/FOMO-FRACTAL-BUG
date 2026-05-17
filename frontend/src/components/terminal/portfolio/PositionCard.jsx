import { useMemo } from "react";
import { useTerminal } from "../../../store/terminalStore";

export default function PositionCard({ position }) {
  const { dispatch } = useTerminal();

  const symbol = position.symbol;
  const side = position.side;
  const entryPrice = Number(position.entry_price || 0);
  const currentPrice = Number(position.current_price || entryPrice);
  const unrealizedPnl = Number(position.unrealized_pnl || 0);
  const unrealizedPnlPct = entryPrice > 0 ? ((currentPrice - entryPrice) / entryPrice) * 100 * (side === "LONG" ? 1 : -1) : 0;

  const target = Number(position.take_profit || 0);
  const stop = Number(position.stop_loss || 0);

  // Status
  const status = useMemo(() => {
    if (!target || !stop) return "Active";

    const distanceToTarget = Math.abs(currentPrice - target);
    const distanceToStop = Math.abs(currentPrice - stop);
    const distanceToEntry = Math.abs(currentPrice - entryPrice);

    if (distanceToTarget < distanceToEntry / 2) return "Near target";
    if (distanceToStop < distanceToEntry / 2) return "Near stop";
    if (unrealizedPnlPct > 1) return "In profit";
    if (unrealizedPnlPct < -1) return "In loss";
    return "Active";
  }, [currentPrice, target, stop, entryPrice, unrealizedPnlPct]);

  const pnlColor = unrealizedPnl >= 0 ? "text-green-600" : "text-red-600";
  const pnlSign = unrealizedPnl >= 0 ? "+" : "";
  const sideColor = side === "LONG" ? "text-green-700" : "text-red-700";

  const handleClick = () => {
    dispatch({ type: "SET_SYMBOL", payload: symbol });
    dispatch({ type: "SET_VIEW", payload: "trade" });
  };

  return (
    <div 
      className="bg-white rounded-xl p-4 border border-neutral-200 hover:border-neutral-300 transition-colors cursor-pointer"
      onClick={handleClick}
      data-testid={`position-card-${symbol.toLowerCase()}`}
    >
      {/* Header */}
      <div className="flex justify-between items-start mb-3">
        <div>
          <div className="font-bold text-base text-neutral-900">
            {symbol.replace("USDT", "")} <span className={`${sideColor} font-semibold`}>· {side}</span>
          </div>
          <div className="text-xs text-neutral-500 mt-1 font-mono tabular-nums">
            Entry: ${entryPrice.toFixed(2)}
          </div>
        </div>

        {/* PnL */}
        <div className="text-right">
          <div className={`${pnlColor} font-bold text-base font-mono tabular-nums`} data-testid={`position-pnl-${symbol.toLowerCase()}`}>
            {pnlSign}${Math.abs(unrealizedPnl).toFixed(0)}
          </div>
          <div className={`text-xs ${pnlColor} font-mono tabular-nums`}>
            {pnlSign}{unrealizedPnlPct.toFixed(2)}%
          </div>
        </div>
      </div>

      {/* Status */}
      <div className="text-xs text-neutral-600 pt-2 border-t border-neutral-200">
        → {status}
      </div>
    </div>
  );
}
