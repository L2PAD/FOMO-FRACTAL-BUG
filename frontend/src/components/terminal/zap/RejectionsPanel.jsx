import { useRejections } from "../../../hooks/zap/useRejections";
import { formatTs } from "./zapUtils";

export default function RejectionsPanel() {
  const { data, error } = useRejections();

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4" style={{ fontFamily: 'Gilroy, sans-serif' }}>
      <div className="mb-3">
        <div className="text-sm font-medium text-gray-900">Rejected Signals</div>
        <div className="text-xs text-gray-500">Why risk blocked trades</div>
      </div>

      {error && <div className="text-sm text-red-600 mb-2">{error}</div>}

      <div className="space-y-2 max-h-[260px] overflow-y-auto pr-1">
        {data.length === 0 ? (
          <div className="text-sm text-gray-500">No recent rejections</div>
        ) : (
          data.map((row, idx) => (
            <div
              key={row.id || `${row.symbol}-${row.timestamp}-${idx}`}
              className="border border-gray-100 rounded-lg p-3"
            >
              <div className="flex items-center justify-between">
                <div className="font-medium text-sm text-gray-900">{row.symbol}</div>
                <div className="text-xs text-gray-500">{formatTs(row.timestamp)}</div>
              </div>

              <div className="mt-1 text-sm text-red-600 font-medium">
                {row.reason}
              </div>

              <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-gray-500">
                <div>Strategy: {row.strategy ?? "—"}</div>
                <div>Confidence: {row.confidence ?? "—"}</div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
