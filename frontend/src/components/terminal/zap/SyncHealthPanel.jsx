import { useSyncHealth } from "../../../hooks/zap/useSyncHealth";
import { statusTone } from "./zapUtils";

export default function SyncHealthPanel() {
  const { data, error } = useSyncHealth();

  const syncState =
    !data ? "UNKNOWN" : data.error_rate > 0 ? "WARNING" : "OK";

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4" style={{ fontFamily: 'Gilroy, sans-serif' }}>
      <div className="mb-3">
        <div className="text-sm font-medium text-gray-900">Sync Health</div>
        <div className="text-xs text-gray-500">Exchange truth layer</div>
      </div>

      {error && <div className="text-sm text-red-600 mb-2">{error}</div>}

      {!data ? (
        <div className="text-sm text-gray-500">No sync data</div>
      ) : (
        <div className="space-y-3">
          <div className={`text-sm font-semibold ${statusTone(syncState)}`}>
            {syncState}
          </div>

          <div className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <div className="text-gray-500">Latency</div>
              <div className="font-medium">{data.latency_ms ?? "—"} ms</div>
            </div>

            <div>
              <div className="text-gray-500">Last Sync</div>
              <div className="font-medium">
                {data.last_sync_seconds ?? "—"}s ago
              </div>
            </div>

            <div>
              <div className="text-gray-500">Error Rate</div>
              <div className="font-medium">{data.error_rate ?? 0}</div>
            </div>

            <div>
              <div className="text-gray-500">Positions</div>
              <div className="font-medium">
                {data.positions_status ?? "OK"}
              </div>
            </div>
          </div>

          {data.last_error && (
            <div className="text-xs text-red-600 break-words">
              {data.last_error}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
