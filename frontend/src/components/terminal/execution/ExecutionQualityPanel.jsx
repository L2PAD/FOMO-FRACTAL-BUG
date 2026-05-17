import { useMemo } from "react";
import { useTerminal } from "../../../store/terminalStore";

export default function ExecutionQualityPanel() {
  const { state } = useTerminal();

  const quality = useMemo(() => {
    const positions = state.positions || [];
    const lastPosition = positions.filter(p => p.status === "OPEN")[0];

    if (!lastPosition) {
      return null;
    }

    const expectedPrice = Number(lastPosition.expected_entry || lastPosition.entry_price || 0);
    const filledPrice = Number(lastPosition.entry_price || 0);
    const slippagePct = expectedPrice > 0 ? ((filledPrice - expectedPrice) / expectedPrice) * 100 : 0;

    return {
      expected: expectedPrice,
      filled: filledPrice,
      slippagePct: slippagePct.toFixed(3),
      isBetter: slippagePct < 0
    };
  }, [state.positions]);

  if (!quality) {
    return (
      <div className="bg-white rounded-xl p-4 border border-[#E5E7EB]" data-testid="execution-quality-panel">
        <div className="text-xs font-semibold text-neutral-500 mb-3 tracking-wide">
          EXECUTION QUALITY
        </div>

        <div className="text-sm text-neutral-400 text-center py-4">
          No execution data
        </div>
      </div>
    );
  }

  const slippageColor = quality.isBetter ? "text-green-600" : "text-orange-600";
  const message = quality.isBetter 
    ? "→ Better than expected" 
    : Math.abs(Number(quality.slippagePct)) < 0.1 
      ? "→ Filled at expected price" 
      : "→ Slightly worse than expected";

  return (
    <div className="bg-white rounded-xl p-4 border border-[#E5E7EB]" data-testid="execution-quality-panel">
      <div className="text-xs font-semibold text-neutral-500 mb-4 tracking-wide">
        EXECUTION QUALITY
      </div>

      <div className="space-y-3 text-sm">
        <div className="flex justify-between items-center">
          <span className="text-neutral-600">Expected</span>
          <span className="font-mono tabular-nums font-semibold text-neutral-900">
            ${quality.expected.toFixed(2)}
          </span>
        </div>

        <div className="flex justify-between items-center">
          <span className="text-neutral-600">Filled</span>
          <span className="font-mono tabular-nums font-semibold text-neutral-900">
            ${quality.filled.toFixed(2)}
          </span>
        </div>

        <div className="pt-2 border-t border-[#E5E7EB]">
          <div className="flex justify-between items-center">
            <span className="text-neutral-700 font-medium">Slippage</span>
            <span className={`font-mono tabular-nums font-bold ${slippageColor}`}>
              {Number(quality.slippagePct) >= 0 ? "+" : ""}{quality.slippagePct}%
            </span>
          </div>
        </div>
      </div>

      {/* Message */}
      <div className="mt-4 pt-3 border-t border-[#E5E7EB]">
        <div className="text-xs text-neutral-600">
          {message}
        </div>
      </div>
    </div>
  );
}
