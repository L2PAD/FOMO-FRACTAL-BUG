import { usePositions } from "@/hooks/positions/usePositions";
import { useTerminal } from "../../../store/terminalStore";
import PositionCard from "../positions/PositionCard";

/**
 * PositionsWorkspace — Open Positions screen.
 *
 * PHASE 2 visual cleanup (2026-04-30):
 *   • Summary bar: Total PnL / Exposure / Risk (no "Connected" dev meta,
 *     no ALL-CAPS, no notional precision noise).
 *   • Empty state synced with Trade page tone ("observing the market").
 *   • Cards grid unchanged — still 1/2/3 columns by viewport.
 *
 * NOT TOUCHED: usePositions polling, API contract, store, PnL math.
 */
export default function PositionsWorkspace() {
  // eslint-disable-next-line no-unused-vars
  const { positions: rawPositions, refresh, isConnected } = usePositions();
  // Defensive: ensure positions is always an array even if hook returns null/undefined/object
  const positions = Array.isArray(rawPositions) ? rawPositions : [];
  // eslint-disable-next-line no-unused-vars
  const { dispatch } = useTerminal();

  const handleClose = async (symbol) => {
    const API_URL = process.env.REACT_APP_BACKEND_URL;
    const result = await fetch(`${API_URL}/api/positions/${symbol}/close`, { method: "POST" }).then(r => r.json());
    if (result.ok) refresh();
    else console.error("Close failed:", result.error);
  };

  const handleReduce = async (symbol, pct) => {
    const API_URL = process.env.REACT_APP_BACKEND_URL;
    const result = await fetch(`${API_URL}/api/positions/${symbol}/reduce`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reduce_pct: pct }),
    }).then(r => r.json());
    if (result.ok) refresh();
    else console.error("Reduce failed:", result.error);
  };

  const handleReverse = async (symbol) => {
    const API_URL = process.env.REACT_APP_BACKEND_URL;
    const result = await fetch(`${API_URL}/api/positions/${symbol}/reverse`, { method: "POST" }).then(r => r.json());
    if (result.ok) refresh();
    else console.error("Reverse failed:", result.error);
  };

  // Derived aggregates — formulas unchanged from previous version.
  const totalPnl = positions.reduce((sum, p) => sum + (p.unrealized_pnl || 0), 0);
  const totalNotional = positions.reduce(
    (sum, p) => sum + ((p.entry_price || 0) * (p.qty || 0)),
    0
  );

  return (
    <div className="p-6" data-testid="positions-workspace">
      {/* ── Summary bar ──────────────────────────────────────────────
          Title + active count on the left, three semantic metrics on
          the right (Total PnL · Exposure · Risk). No "Connected" badge,
          no ALL-CAPS labels, no border boxes — numbers carry their own
          weight via typography. */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Open Positions</h1>
          <p className="text-sm text-gray-500">
            {positions.length === 0
              ? "No active positions"
              : `${positions.length} active`}
          </p>
        </div>
        <div className="flex items-center gap-6 text-sm">
          <div>
            <div className="text-gray-500">Total PnL</div>
            <div
              className={`font-semibold tabular-nums ${
                totalPnl >= 0 ? "text-emerald-600" : "text-red-600"
              }`}
            >
              {totalPnl >= 0 ? "+" : ""}${totalPnl.toFixed(2)}
            </div>
          </div>
          <div>
            <div className="text-gray-500">Exposure</div>
            <div className="font-semibold text-gray-900 tabular-nums">
              ${totalNotional.toFixed(2)}
            </div>
          </div>
          <div>
            <div className="text-gray-500">Risk</div>
            <div className="font-semibold text-gray-700">Normal</div>
          </div>
        </div>
      </div>

      {/* ── Body ────────────────────────────────────────────────────────── */}
      {positions.length === 0 ? (
        <div className="text-center py-16 text-gray-500">
          <div className="text-base font-medium text-gray-700">
            No open positions
          </div>
          <div className="text-sm mt-1">
            The system is currently observing the market.
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
          {positions.map((pos) => (
            <PositionCard
              key={pos.symbol}
              position={pos}
              onClose={() => handleClose(pos.symbol)}
              onReduce={(pct) => handleReduce(pos.symbol, pct)}
              onReverse={() => handleReverse(pos.symbol)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
