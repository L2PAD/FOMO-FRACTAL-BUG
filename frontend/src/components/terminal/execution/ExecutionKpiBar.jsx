import { useEffect } from "react";
import { useTerminal } from "../../../store/terminalStore";

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

export default function ExecutionKpiBar() {
  const { state, dispatch } = useTerminal();

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(`${API_URL}/api/trading/execution-quality`);
        const data = await res.json();

        if (data.ok) {
          dispatch({
            type: "SET_EXECUTION",
            payload: data,
          });
        }
      } catch (e) {
        console.error('Execution quality fetch error:', e);
      }
    }

    load();
    const i = setInterval(load, 5000);
    return () => clearInterval(i);
  }, [dispatch]);

  const x = state.execution || {};

  return (
    <div className="grid grid-cols-6 gap-4 text-sm">
      <div className="border border-[#E5E7EB] rounded-lg p-3">
        <div className="text-xs text-neutral-500 mb-1">Avg Quality</div>
        <div className="font-semibold font-mono">
          {Number(x.avg_quality || 0).toFixed(1)}
        </div>
      </div>

      <div className="border border-[#E5E7EB] rounded-lg p-3">
        <div className="text-xs text-neutral-500 mb-1">Avg Slippage</div>
        <div className="font-mono">{Number(x.avg_slippage || 0).toFixed(2)} bps</div>
      </div>

      <div className="border border-[#E5E7EB] rounded-lg p-3">
        <div className="text-xs text-neutral-500 mb-1">Avg Latency</div>
        <div className="font-mono">{Number(x.avg_latency || 0).toFixed(0)} ms</div>
      </div>

      <div className="border border-[#E5E7EB] rounded-lg p-3">
        <div className="text-xs text-neutral-500 mb-1">Filled</div>
        <div className="font-mono">{x.filled || 0}</div>
      </div>

      <div className="border border-[#E5E7EB] rounded-lg p-3">
        <div className="text-xs text-neutral-500 mb-1">Rejected</div>
        <div className="font-mono">{x.rejected || 0}</div>
      </div>

      <div className="border border-[#E5E7EB] rounded-lg p-3">
        <div className="text-xs text-neutral-500 mb-1">Fees</div>
        <div className="font-mono">${Number(x.total_fees || 0).toFixed(2)}</div>
      </div>
    </div>
  );
}
