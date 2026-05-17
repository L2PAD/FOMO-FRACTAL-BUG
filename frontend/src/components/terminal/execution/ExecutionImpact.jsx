import { useMemo } from "react";
import { useTerminal } from "../../../store/terminalStore";

export default function ExecutionImpact() {
  const { state } = useTerminal();

  const impact = useMemo(() => {
    const positions = state.positions || [];
    const lastPosition = positions.filter(p => p.status === "OPEN")[0];

    if (!lastPosition) {
      return null;
    }

    const expectedEntry = Number(lastPosition.expected_entry || lastPosition.entry_price || 0);
    const actualEntry = Number(lastPosition.entry_price || 0);
    const target = Number(lastPosition.take_profit || 0);
    const size = Number(lastPosition.size || 0);
    const side = lastPosition.side;

    if (!expectedEntry || !target || !size) {
      return null;
    }

    // Calculate expected PnL
    const expectedPnl = side === "LONG" 
      ? (target - expectedEntry) * size 
      : (expectedEntry - target) * size;

    // Calculate actual PnL
    const actualPnl = side === "LONG"
      ? (target - actualEntry) * size
      : (actualEntry - target) * size;

    // Impact
    const impactUsd = actualPnl - expectedPnl;
    const impactPct = expectedPnl > 0 ? (impactUsd / expectedPnl) * 100 : 0;

    return {
      expectedPnl,
      actualPnl,
      impactUsd,
      impactPct: impactPct.toFixed(1),
      isNegative: impactUsd < 0
    };
  }, [state.positions]);

  if (!impact) {
    return (
      <div className="bg-neutral-50 rounded-xl p-4 border border-[#E5E7EB]" data-testid="execution-impact">
        <div className="text-xs font-semibold text-neutral-500 mb-3 tracking-wide">
          PNL IMPACT
        </div>

        <div className="text-sm text-neutral-400 text-center py-3">
          No impact data available
        </div>
      </div>
    );
  }

  const impactColor = impact.isNegative ? "text-red-600" : "text-green-600";
  const impactSign = impact.isNegative ? "" : "+";

  return (
    <div className="bg-orange-50 rounded-xl p-4 border border-orange-200" data-testid="execution-impact">
      <div className="text-xs font-semibold text-orange-700 mb-3 tracking-wide">
        💰 PNL IMPACT
      </div>

      <div className="space-y-2 text-sm">
        <div className="flex justify-between items-center">
          <span className="text-neutral-700">Expected PnL</span>
          <span className="font-mono tabular-nums font-semibold text-neutral-900">
            ${impact.expectedPnl.toFixed(0)}
          </span>
        </div>

        <div className="flex justify-between items-center">
          <span className="text-neutral-700">Actual PnL</span>
          <span className="font-mono tabular-nums font-semibold text-neutral-900">
            ${impact.actualPnl.toFixed(0)}
          </span>
        </div>

        <div className="pt-2 border-t border-orange-300">
          <div className="flex justify-between items-center">
            <span className="text-neutral-800 font-medium">Execution Impact</span>
            <span className={`font-mono tabular-nums font-bold ${impactColor}`}>
              {impactSign}${Math.abs(impact.impactUsd).toFixed(0)}
            </span>
          </div>
        </div>
      </div>

      {/* Message */}
      <div className="mt-3 pt-3 border-t border-orange-300">
        <div className="text-xs text-orange-900">
          {impact.isNegative 
            ? `→ Execution reduced profit by ${Math.abs(Number(impact.impactPct)).toFixed(1)}%` 
            : `→ Execution improved profit by ${impact.impactPct}%`}
        </div>
      </div>
    </div>
  );
}
