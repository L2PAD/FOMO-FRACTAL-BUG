import { useTerminal } from "../../../store/terminalStore";

export default function AllocationPanel() {
  const { state } = useTerminal();

  const positions = state.positions || [];

  const total = positions.reduce((sum, p) => sum + (p.size_usd || 0), 0);

  return (
    <div className="border border-neutral-200 rounded-lg p-4 text-sm">
      <div className="mb-4 font-semibold text-neutral-900">Allocation</div>

      {positions.length === 0 && (
        <div className="text-neutral-400 text-xs">No positions</div>
      )}

      <div className="space-y-3">
        {positions.map((p) => {
          const pct = total > 0 ? (p.size_usd / total) * 100 : 0;

          return (
            <div key={p.symbol}>
              <div className="flex justify-between text-xs mb-1">
                <span className="font-medium">{p.symbol}</span>
                <span className="font-mono">{pct.toFixed(1)}%</span>
              </div>

              <div className="h-2 bg-neutral-100 rounded-full overflow-hidden">
                <div
                  className="h-2 bg-neutral-900 rounded-full"
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
