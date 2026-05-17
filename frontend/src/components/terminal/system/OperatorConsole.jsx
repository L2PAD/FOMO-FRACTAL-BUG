import { useState } from "react";
import { useTerminal } from "../../../store/terminalStore";

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

export default function OperatorConsole() {
  const { state, dispatch } = useTerminal();
  const [loading, setLoading] = useState(false);

  const toggleAutotrading = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/trading/autotrading/toggle`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: !state.autotradingEnabled })
      });
      const data = await res.json();
      if (data.ok) {
        dispatch({ type: "SET_AUTOTRADING", payload: data.autotrading?.enabled || false });
      }
    } catch (e) {
      console.error('Toggle autotrading error:', e);
    } finally {
      setLoading(false);
    }
  };

  const forceSyncFills = async () => {
    setLoading(true);
    try {
      await fetch(`${API_URL}/api/exchange/sync-fills`, { method: 'POST' });
    } catch (e) {
      console.error('Sync fills error:', e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="border border-neutral-200 rounded-lg p-4 overflow-auto">
      <div className="mb-4 font-semibold text-neutral-900">Operator Console</div>

      <div className="space-y-2">
        <button
          onClick={toggleAutotrading}
          disabled={loading}
          className="w-full px-4 py-2 text-sm bg-neutral-900 text-white rounded hover:bg-neutral-800 disabled:opacity-50"
          data-testid="toggle-autotrading-btn"
        >
          {state.autotradingEnabled ? "Disable Autotrading" : "Enable Autotrading"}
        </button>

        <button
          onClick={() => dispatch({ type: "SET_EXCHANGE_MODE", payload: state.exchangeMode === "PAPER" ? "TESTNET" : "PAPER" })}
          disabled={loading}
          className="w-full px-4 py-2 text-sm bg-neutral-100 text-neutral-900 rounded hover:bg-neutral-200 disabled:opacity-50"
        >
          Switch to {state.exchangeMode === "PAPER" ? "TESTNET" : "PAPER"}
        </button>

        <button
          onClick={forceSyncFills}
          disabled={loading}
          className="w-full px-4 py-2 text-sm bg-neutral-100 text-neutral-900 rounded hover:bg-neutral-200 disabled:opacity-50"
        >
          Force Sync Fills
        </button>

        <button
          disabled={loading}
          className="w-full px-4 py-2 text-sm bg-red-50 text-red-600 rounded hover:bg-red-100 disabled:opacity-50"
        >
          Emergency Flatten All
        </button>

        <button
          disabled={loading}
          className="w-full px-4 py-2 text-sm bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50"
        >
          KILL SWITCH
        </button>
      </div>

      <div className="mt-4 pt-4 border-t border-neutral-200">
        <div className="text-xs text-neutral-500 mb-2">Recent Actions</div>
        <div className="text-xs text-neutral-400">No recent operator actions</div>
      </div>
    </div>
  );
}
