import { useStrategyRecentDecisions } from "@/hooks/strategy/useStrategyRecentDecisions";

export default function DecisionDetailsPanel() {
  const { data, error } = useStrategyRecentDecisions();

  if (error) {
    return (
      <div className="bg-neutral-900 rounded-xl p-6 border border-red-600/20">
        <div className="text-red-500 text-sm">Decisions error: {error}</div>
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="bg-neutral-900 rounded-xl p-6 text-center text-gray-400 border border-neutral-800">
        <div className="text-base font-medium mb-2">No runtime decisions yet</div>
        <div className="text-xs">Run the engine or wait for a valid setup</div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="text-sm font-medium text-gray-300 mb-3">
        Recent Decisions ({data.slice(0, 20).length})
      </div>
      {data.slice(0, 20).map((d, i) => (
        <DecisionRow key={i} d={d} />
      ))}
    </div>
  );
}

function DecisionRow({ d }) {
  const statusColor =
    d.status === "APPROVED"
      ? "text-green-400"
      : d.status === "REJECTED"
      ? "text-red-400"
      : "text-yellow-400";

  return (
    <div
      className="bg-neutral-900 rounded-lg p-3 border border-neutral-800 hover:border-neutral-700 transition-colors"
      data-testid={`decision-row-${d.symbol}`}
    >
      <div className="flex justify-between text-sm">
        <span className="text-gray-100 font-medium">{d.symbol}</span>
        <span className={statusColor}>{d.status}</span>
      </div>

      <div className="text-xs text-gray-400 mt-1">
        {d.direction} · {d.strategy}
      </div>

      {d.confidence && (
        <div className="text-xs text-gray-500 mt-1">
          Confidence: {(d.confidence * 100).toFixed(1)}%
        </div>
      )}

      {d.risk_reason && (
        <div className="text-xs text-red-400 mt-1 bg-red-600/10 px-2 py-1 rounded border border-red-600/20">
          {d.risk_reason}
        </div>
      )}

      <div className="text-[10px] text-gray-500 mt-2 flex justify-between">
        <span>{d.runtime_mode}</span>
        <span>{new Date(d.created_at).toLocaleTimeString()}</span>
      </div>
    </div>
  );
}
