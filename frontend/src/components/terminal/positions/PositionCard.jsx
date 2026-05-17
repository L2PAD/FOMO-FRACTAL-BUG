/**
 * PositionCard — single open position tile.
 *
 * PHASE 2 visual cleanup (2026-04-30):
 *   • Header: symbol + side pill (Long/Short, calm case) + pnl%.
 *   • Body: 5 stacked rows (Entry / Mark / PnL / Size / Leverage),
 *     no two-column grid, no qty raw, no 4-decimal noise.
 *   • Actions always visible — Close (primary), Reduce 50%, Reverse.
 *     No toggle, no ASCII chevron.
 *   • Direction tone is rendered via box-shadow inset (consistent with
 *     CaseCommandHeaderUltraCompact), not borderLeft.
 *   • emerald-* palette to match Trade page; green-* removed.
 *   • Inline Gilroy fontFamily dropped — it's now global in index.css.
 *
 * NOT TOUCHED: PnL math — reads p.unrealized_pnl / p.unrealized_pnl_pct
 * straight from the payload; notional = entry_price × qty, identical to
 * the previous implementation.
 */
export default function PositionCard({ position, onClose, onReduce, onReverse }) {
  const p = position;
  const isLong = p.side === "LONG";
  const pnl = p.unrealized_pnl || 0;
  const pnlPct = p.unrealized_pnl_pct || 0;
  const isProfitable = pnl >= 0;
  const notional = (p.entry_price || 0) * (p.qty || 0);

  const toneEmerald = isProfitable ? "text-emerald-600" : "text-red-600";

  return (
    <div
      className="bg-white rounded-lg border border-gray-200 p-4"
      data-testid={`position-card-${p.symbol}`}
      style={{
        fontVariantNumeric: "tabular-nums",
        // Direction tone bar — same pattern as the Trade case header.
        boxShadow: `inset 3px 0 0 ${isLong ? "#10b981" : "#ef4444"}`,
      }}
    >
      {/* ── Header ─────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="font-medium text-gray-900">{p.symbol}</div>
          <span
            className={`text-xs px-2 py-0.5 rounded-full ${
              isLong
                ? "bg-emerald-50 text-emerald-600"
                : "bg-red-50 text-red-600"
            }`}
          >
            {isLong ? "Long" : "Short"}
          </span>
        </div>
        <div className={`text-sm font-medium ${toneEmerald}`}>
          {isProfitable ? "+" : ""}
          {pnlPct.toFixed(2)}%
        </div>
      </div>

      {/* ── Stats ──────────────────────────────────────────────────── */}
      <div className="mt-3 text-sm space-y-1">
        <div className="flex justify-between">
          <span className="text-gray-500">Entry</span>
          <span className="text-gray-900">{(p.entry_price || 0).toFixed(2)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-500">Mark</span>
          <span className="text-gray-900">{(p.mark_price || 0).toFixed(2)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-500">PnL</span>
          <span className={toneEmerald}>
            {isProfitable ? "+" : ""}${pnl.toFixed(2)}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-500">Size</span>
          <span className="text-gray-900">${notional.toFixed(0)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-500">Leverage</span>
          <span className="text-gray-900">{p.leverage || 1}x</span>
        </div>
      </div>

      {/* ── Actions — always visible ────────────────────────────────────── */}
      <div className="flex gap-2 mt-4">
        <button
          type="button"
          onClick={onClose}
          className="px-3 py-1.5 text-sm rounded-md bg-gray-900 text-white hover:bg-gray-800 transition-colors"
          data-testid={`close-position-${p.symbol}`}
        >
          Close
        </button>
        <button
          type="button"
          onClick={() => onReduce(50)}
          className="px-3 py-1.5 text-sm rounded-md border border-gray-200 text-gray-700 hover:bg-gray-50 transition-colors"
          data-testid={`reduce-50-${p.symbol}`}
        >
          Reduce 50%
        </button>
        <button
          type="button"
          onClick={onReverse}
          className="px-3 py-1.5 text-sm rounded-md border border-gray-200 text-gray-700 hover:bg-gray-50 transition-colors"
          data-testid={`reverse-position-${p.symbol}`}
        >
          Reverse
        </button>
      </div>
    </div>
  );
}
