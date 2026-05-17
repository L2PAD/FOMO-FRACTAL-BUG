import { useFills } from "../../../hooks/zap/useFills";
import { formatTs } from "./zapUtils";

export default function FillsPanel() {
  const { data, error } = useFills();

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4" style={{ fontFamily: 'Gilroy, sans-serif' }}>
      <div className="mb-3">
        <div className="text-sm font-medium text-gray-900">Fills</div>
        <div className="text-xs text-gray-500">Real execution results</div>
      </div>

      {error && <div className="text-sm text-red-600 mb-2">{error}</div>}

      <div className="space-y-2 max-h-[260px] overflow-y-auto pr-1">
        {data.length === 0 ? (
          <div className="text-sm text-gray-500">No fills</div>
        ) : (
          data.map((fill) => (
            <div
              key={fill.fill_id || `${fill.symbol}-${fill.timestamp}`}
              className="border border-gray-100 rounded-lg p-3"
            >
              <div className="flex items-center justify-between">
                <div className="font-medium text-sm text-gray-900">
                  {fill.symbol}
                </div>
                <div className="text-xs text-gray-500">{formatTs(fill.timestamp)}</div>
              </div>

              <div className="mt-1 text-sm text-gray-700">
                Qty {fill.quantity ?? fill.qty} @ {fill.price ?? fill.avg_price}
              </div>

              <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-gray-500">
                <div>Fee: {fill.fee ?? "—"}</div>
                <div>Side: {fill.side ?? "—"}</div>
                <div>Maker: {String(fill.is_maker ?? "—")}</div>
                <div>Order: {(fill.order_id ?? "—").slice(0, 12)}</div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
