import { useMemo, useEffect, useState } from "react";
import { useTerminal } from "../../../store/terminalStore";

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

export default function DecisionPanel() {
  const { state, dispatch } = useTerminal();
  const [allocatorData, setAllocatorData] = useState(null);

  useEffect(() => {
    const fetchAllocator = async () => {
      try {
        const res = await fetch(`${API_URL}/api/strategy/allocator-v3`);
        const data = await res.json();
        if (data.ok) {
          setAllocatorData(data);
          dispatch({ type: "SET_ALLOCATOR", payload: data });
        }
      } catch (e) {
        console.error("Allocator fetch error:", e);
      }
    };

    fetchAllocator();
    const interval = setInterval(fetchAllocator, 5000);
    return () => clearInterval(interval);
  }, [dispatch]);

  const decision = useMemo(() => {
    return (
      allocatorData?.decisions?.find(
        (d) => d.symbol === state.selectedSymbol
      ) || null
    );
  }, [allocatorData, state.selectedSymbol]);

  const position = useMemo(() => {
    return (
      state.positions?.find((p) => p.symbol === state.selectedSymbol) || null
    );
  }, [state.positions, state.selectedSymbol]);

  return (
    <div className="border-l border-neutral-200 p-4 text-sm overflow-y-auto bg-white">
      <div className="mb-5 font-semibold text-neutral-900">Decision & Position</div>

      {!decision && !position && (
        <div className="text-neutral-500 text-sm">No active decision or position for this symbol</div>
      )}

      {decision && (
        <div className="mb-6 space-y-2">
          <div className="text-xs uppercase text-neutral-500 mb-2">DECISION</div>
          <div className="space-y-1.5">
            <div className="flex justify-between">
              <span className="text-neutral-600">Side:</span>
              <span className="font-semibold">{decision.side}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-neutral-600">Size USD:</span>
              <span className="font-semibold font-mono">${Number(decision.size_usd || 0).toFixed(2)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-neutral-600">Rank:</span>
              <span className="font-semibold font-mono">{Number(decision.rank_score || decision.score || 0).toFixed(2)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-neutral-600">Kelly:</span>
              <span className="font-semibold font-mono">{Number(decision.kelly_fraction || 0).toFixed(4)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-neutral-600">Adaptive Risk:</span>
              <span className="font-semibold font-mono">{(Number(decision.adaptive_risk || 0) * 100).toFixed(2)}%</span>
            </div>
            <div className="flex justify-between">
              <span className="text-neutral-600">Vol Mult:</span>
              <span className="font-semibold font-mono">{Number(decision.vol_multiplier || 0).toFixed(2)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-neutral-600">Corr Penalty:</span>
              <span className="font-semibold font-mono">{Number(decision.correlation_penalty || 0).toFixed(2)}</span>
            </div>
          </div>
          <div className="mt-3 pt-3 border-t border-neutral-200">
            <div className="text-xs text-neutral-500 mb-1">Reason</div>
            <div className="text-xs text-neutral-700">
              {decision.rank_reason || "No reasoning provided"}
            </div>
          </div>
        </div>
      )}

      {position && (
        <div className="space-y-2">
          <div className="text-xs uppercase text-neutral-500 mb-2">POSITION</div>
          <div className="space-y-1.5">
            <div className="flex justify-between">
              <span className="text-neutral-600">Side:</span>
              <span className="font-semibold">{position.side}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-neutral-600">Entry:</span>
              <span className="font-semibold font-mono">${Number(position.entry_price || 0).toFixed(2)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-neutral-600">Size:</span>
              <span className="font-semibold font-mono">{position.size}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-neutral-600">UPnL:</span>
              <span className="font-semibold font-mono">${Number(position.unrealized_pnl || 0).toFixed(2)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-neutral-600">Status:</span>
              <span className="font-semibold">{position.status || "OPEN"}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
