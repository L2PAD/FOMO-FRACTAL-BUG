import { useMemo } from "react";
import { useTerminal } from "../../../store/terminalStore";

export default function ExposureMap() {
  const { state } = useTerminal();

  const positions = state.positions || [];
  const equity = state.portfolio?.equity || 10000;

  // Calculate exposure per symbol
  const exposure = useMemo(() => {
    const map = {};
    positions.forEach(p => {
      const sizeUsd = Number(p.size_usd || 0);
      const symbol = p.symbol.replace("USDT", "");
      map[symbol] = (map[symbol] || 0) + sizeUsd;
    });

    // Convert to percentage and sort
    return Object.entries(map)
      .map(([symbol, value]) => ({
        symbol,
        percent: equity > 0 ? (value / equity) * 100 : 0
      }))
      .sort((a, b) => b.percent - a.percent)
      .slice(0, 5);
  }, [positions, equity]);

  // Insight
  const insight = useMemo(() => {
    if (exposure.length === 0) return "→ No exposure";
    const top = exposure[0];
    if (top.percent > 40) return `→ Highly concentrated in ${top.symbol}`;
    if (top.percent > 25) return `→ Concentrated in ${top.symbol}`;
    return "→ Diversified exposure";
  }, [exposure]);

  return (
    <div className="bg-white rounded-xl p-4 border border-neutral-200" data-testid="exposure-map">
      <div className="text-xs font-semibold text-neutral-500 mb-3 tracking-wide">
        EXPOSURE
      </div>

      {exposure.length === 0 && (
        <div className="text-sm text-neutral-400">No positions</div>
      )}

      {exposure.length > 0 && (
        <div className="space-y-2 mb-3">
          {exposure.map((e) => (
            <div key={e.symbol} className="flex justify-between items-center text-sm" data-testid={`exposure-${e.symbol.toLowerCase()}`}>
              <span className="font-medium text-neutral-800">{e.symbol}</span>
              <span className="font-mono tabular-nums text-neutral-700">{e.percent.toFixed(1)}%</span>
            </div>
          ))}
        </div>
      )}

      {/* Insight */}
      <div className="text-xs text-neutral-600 pt-2 border-t border-neutral-200">
        {insight}
      </div>
    </div>
  );
}
