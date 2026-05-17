import { useTerminal } from "../../../store/terminalStore";
import { useEffect, useState } from "react";

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

export default function MarketNavPanel() {
  const { state, dispatch } = useTerminal();
  const [portfolio, setPortfolio] = useState(null);

  useEffect(() => {
    const fetchPortfolio = async () => {
      try {
        const res = await fetch(`${API_URL}/api/trading/portfolio`);
        const data = await res.json();
        if (data.ok && data.portfolio) {
          setPortfolio(data.portfolio);
          dispatch({ type: "SET_PORTFOLIO", payload: data.portfolio });
        }
      } catch (e) {
        console.error("Portfolio fetch error:", e);
      }
    };

    fetchPortfolio();
    const interval = setInterval(fetchPortfolio, 3000);
    return () => clearInterval(interval);
  }, [dispatch]);

  const fallbackSymbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"];
  
  // P0 FIX: Dynamic portfolio symbols from positions
  const positions = portfolio?.positions || [];
  const activeSymbols = positions.length > 0
    ? [...new Set(positions.map(p => p.symbol))]
    : fallbackSymbols;

  return (
    <div className="border-r border-neutral-200 p-3 overflow-y-auto bg-white">
      <div className="text-xs text-neutral-500 uppercase tracking-wide mb-3 font-semibold">ASSETS</div>

      <div className="space-y-1">
        {activeSymbols.map((symbol) => (
          <button
            key={symbol}
            onClick={() => dispatch({ type: "SET_SYMBOL", payload: symbol })}
            className={`
              w-full text-left px-3 py-2 rounded text-sm transition-colors
              ${
                state.selectedSymbol === symbol
                  ? "bg-neutral-900 text-white font-semibold"
                  : "bg-white text-neutral-700 hover:bg-neutral-50"
              }
            `}
            data-testid={`asset-chip-${symbol}`}
          >
            {symbol}
          </button>
        ))}
      </div>
    </div>
  );
}
