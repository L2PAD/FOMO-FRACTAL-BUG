import React from "react";
import {
  useAutoSafetyConfig,
  useAutoSafetyState,
  useAutoSafetyActions,
} from "@/hooks/auto_safety/useAutoSafety";
import useWsSnapshot from "@/ws/useWsSnapshot";

export default function AutoSafetyPanel() {
  const { config, loading, refetch } = useAutoSafetyConfig();
  
  // WS-2: safety.state via WebSocket (primary)
  const { data: wsState, isConnected } = useWsSnapshot("safety.state", null);
  
  // Polling fallback
  const { state: polledState } = useAutoSafetyState();
  
  // WS primary, polling fallback (with race condition fix built-in)
  const state = wsState ?? polledState;
  
  const { updateConfig, updating } = useAutoSafetyActions(refetch);

  if (!config || !state) {
    return <div className="p-4 text-gray-400">Loading Auto Safety...</div>;
  }

  const isAuto = config.auto_mode_enabled;

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-4" data-testid="auto-safety-panel">

      {/* HEADER */}
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-3">
          <div className="text-lg font-semibold text-white">AUTO SAFETY</div>
          <div
            className={
              isConnected
                ? "text-green-400 text-xs font-semibold"
                : "text-yellow-400 text-xs font-semibold"
            }
          >
            {isConnected ? "🟢 LIVE" : "🟡 POLLING"}
          </div>
        </div>

        <button
          onClick={() =>
            updateConfig({ auto_mode_enabled: !config.auto_mode_enabled })
          }
          disabled={updating}
          data-testid="auto-safety-toggle"
          className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
            isAuto ? "bg-green-600 hover:bg-green-700" : "bg-gray-700 hover:bg-gray-600"
          }`}
        >
          {isAuto ? "AUTO ON" : "AUTO OFF"}
        </button>
      </div>

      {/* GRID */}
      <div className="grid grid-cols-2 gap-4">

        {/* CONFIG */}
        <div className="bg-gray-800 rounded p-3 space-y-2" data-testid="auto-safety-config">
          <div className="text-gray-400 text-xs font-semibold">CONFIG</div>

          <Row label="Max trades/hour" value={config.max_trades_per_hour} />
          <Row label="Max concurrent" value={config.max_concurrent_positions} />
          <Row label="Max capital %" value={`${(config.max_capital_deployed_pct * 100).toFixed(0)}%`} />
          <Row label="Max trade %" value={`${(config.max_single_trade_notional_pct * 100).toFixed(0)}%`} />
          <Row label="Daily loss limit" value={`$${config.daily_loss_limit_usd}`} />
          <Row label="Max losses" value={config.max_consecutive_losses} />

          <Row
            label="Symbols"
            value={(config.allowed_symbols || []).join(", ") || "None"}
          />
        </div>

        {/* STATE */}
        <div className="bg-gray-800 rounded p-3 space-y-2" data-testid="auto-safety-state">
          <div className="text-gray-400 text-xs font-semibold">STATE</div>

          <Row label="Trades (1h)" value={state.trades_last_hour} />
          <Row label="Open positions" value={state.concurrent_positions} />
          <Row label="Capital used %" value={`${(state.capital_deployed_pct * 100).toFixed(1)}%`} />
          <Row label="Daily PnL" value={`$${state.daily_pnl_usd.toFixed(2)}`} />
          <Row label="Loss streak" value={state.consecutive_losses} />
        </div>
      </div>

      {/* WARNINGS */}
      <div className="bg-gray-800 rounded p-3 space-y-2" data-testid="auto-safety-status">
        <div className="text-gray-400 text-xs font-semibold">STATUS</div>

        {!isAuto && (
          <div className="text-yellow-400 text-sm font-medium">
            ⚠ AUTO MODE DISABLED
          </div>
        )}

        {state.last_block_reason && (
          <div className="text-red-400 text-sm font-medium" data-testid="auto-safety-block-reason">
            🚫 BLOCKED: {state.last_block_reason}
          </div>
        )}

        {isAuto && !state.last_block_reason && (
          <div className="text-green-400 text-sm font-medium">
            ✓ AUTO ACTIVE — WITHIN LIMITS
          </div>
        )}
      </div>
    </div>
  );
}

/* small reusable row */
function Row({ label, value }) {
  return (
    <div className="flex justify-between text-sm">
      <span className="text-gray-400">{label}</span>
      <span className="text-white">{value ?? "-"}</span>
    </div>
  );
}
