import { useEffect } from "react";
import { useTerminal } from "../../../store/terminalStore";

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

export default function PortfolioKpiBar() {
  const { state, dispatch } = useTerminal();

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(`${API_URL}/api/trading/portfolio`);
        const data = await res.json();

        if (data.ok) {
          dispatch({
            type: "SET_PORTFOLIO",
            payload: data.portfolio,
          });
          
          dispatch({
            type: "SET_POSITIONS",
            payload: data.portfolio?.positions || [],
          });
        }
      } catch (e) {
        console.error('Portfolio fetch error:', e);
      }
    }

    load();
    const i = setInterval(load, 5000);
    return () => clearInterval(i);
  }, [dispatch]);

  const p = state.portfolio || {};

  return (
    <div className="grid grid-cols-4 gap-4 text-sm">
      <div className="border border-neutral-200 rounded-lg p-3">
        <div className="text-xs text-neutral-500 mb-1">Equity</div>
        <div className="font-semibold font-mono">${Number(p.equity || 0).toFixed(2)}</div>
      </div>

      <div className="border border-neutral-200 rounded-lg p-3">
        <div className="text-xs text-neutral-500 mb-1">Balance</div>
        <div className="font-mono">${Number(p.balance || 0).toFixed(2)}</div>
      </div>

      <div className="border border-neutral-200 rounded-lg p-3">
        <div className="text-xs text-neutral-500 mb-1">PnL</div>
        <div className="font-mono">${Number(p.total_pnl || 0).toFixed(2)}</div>
      </div>

      <div className="border border-neutral-200 rounded-lg p-3">
        <div className="text-xs text-neutral-500 mb-1">Risk Heat</div>
        <div className="font-mono">{Number((p.risk_heat || 0) * 100).toFixed(0)}%</div>
      </div>
    </div>
  );
}
