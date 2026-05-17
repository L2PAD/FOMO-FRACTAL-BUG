import { useMemo } from "react";
import { useTerminal } from "../../../store/terminalStore";

export default function ExecutionHero() {
  const { state } = useTerminal();

  // Get most recent fill or position
  const recentExecution = useMemo(() => {
    const positions = state.positions || [];
    const lastPosition = positions.filter(p => p.status === "OPEN")[0];

    if (!lastPosition) {
      return null;
    }

    const expectedPrice = Number(lastPosition.expected_entry || lastPosition.entry_price || 0);
    const filledPrice = Number(lastPosition.entry_price || 0);
    const slippageBps = expectedPrice > 0 ? Math.abs((filledPrice - expectedPrice) / expectedPrice) * 10000 : 0;

    return {
      symbol: lastPosition.symbol,
      side: lastPosition.side,
      status: "FILLED",
      slippageBps: slippageBps.toFixed(1),
      quality: slippageBps < 5 ? "EXCELLENT" : slippageBps < 10 ? "GOOD" : slippageBps < 20 ? "ACCEPTABLE" : "POOR"
    };
  }, [state.positions]);

  if (!recentExecution) {
    return (
      <div className="bg-white rounded-xl p-6 border border-[#E5E7EB]" data-testid="execution-hero">
        <div className="text-xs font-semibold text-neutral-500 mb-3 tracking-wide">
          EXECUTION STATUS
        </div>

        <div className="text-center py-4">
          <div className="text-lg font-semibold text-neutral-400 mb-2">
            NO RECENT EXECUTIONS
          </div>
          <div className="text-sm text-neutral-500">
            → Waiting for order fills
          </div>
        </div>
      </div>
    );
  }

  const qualityColor = 
    recentExecution.quality === "EXCELLENT" ? "text-green-600" :
    recentExecution.quality === "GOOD" ? "text-blue-600" :
    recentExecution.quality === "ACCEPTABLE" ? "text-orange-600" :
    "text-red-600";

  const statusMessage = 
    recentExecution.quality === "EXCELLENT" ? "→ Execution better than expected" :
    recentExecution.quality === "GOOD" ? "→ Execution within acceptable range" :
    recentExecution.quality === "ACCEPTABLE" ? "→ Moderate slippage detected" :
    "→ High slippage — review execution quality";

  return (
    <div className="bg-white rounded-xl p-6 border border-[#E5E7EB] shadow-sm" data-testid="execution-hero">
      <div className="text-xs font-semibold text-neutral-500 mb-3 tracking-wide">
        EXECUTION STATUS
      </div>

      <div className="flex justify-between items-end mb-4">
        {/* Status */}
        <div>
          <div className="text-2xl font-bold text-neutral-900 mb-1">
            {recentExecution.status}
          </div>
          <div className="text-sm text-neutral-600">
            {recentExecution.symbol.replace("USDT", "")} · {recentExecution.side}
          </div>
        </div>

        {/* Quality */}
        <div className="text-right">
          <div className="text-sm font-semibold text-neutral-700 mb-1">
            Slippage: <span className={qualityColor}>{recentExecution.slippageBps} bps</span>
          </div>
          <div className={`text-xs font-medium ${qualityColor}`}>
            Quality: {recentExecution.quality}
          </div>
        </div>
      </div>

      {/* Message */}
      <div className="pt-3 border-t border-[#E5E7EB]">
        <div className="text-sm text-neutral-700">
          {statusMessage}
        </div>
      </div>
    </div>
  );
}
