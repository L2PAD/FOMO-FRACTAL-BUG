import { useEffect, useRef } from "react";
import { useExecutionFeed } from "../../../hooks/zap/useExecutionFeed";
import { eventTone, formatTs } from "./zapUtils";

export default function ExecutionFeedPanel() {
  const { data, error } = useExecutionFeed();
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [data]);

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4" style={{ fontFamily: 'Gilroy, sans-serif' }}>
      <div className="flex items-center justify-between mb-3">
        <div>
          <div className="text-sm font-medium text-gray-900">Execution Feed</div>
          <div className="text-xs text-gray-500">Live pipeline events</div>
        </div>
        <div className="text-xs text-gray-500">{data.length} events</div>
      </div>

      {error && (
        <div className="text-sm text-red-600 mb-2">{error}</div>
      )}

      <div className="h-[260px] overflow-y-auto space-y-2 pr-1">
        {data.length === 0 ? (
          <div className="text-sm text-gray-500">No execution events yet</div>
        ) : (
          data.map((event) => (
            <div
              key={event.event_id || event.id || `${event.type}-${event.timestamp}`}
              className="grid grid-cols-[90px_100px_120px_1fr] gap-3 text-sm border-b border-gray-100 pb-2"
            >
              <div className="text-gray-500">{formatTs(event.timestamp || event.timestamp_dt)}</div>
              <div className="font-medium text-gray-900">{event.symbol || "SYSTEM"}</div>
              <div className={eventTone(event.type)}>{event.type || "EVENT"}</div>
              <div className="text-gray-700 truncate">
                {event.message ||
                  event.reason ||
                  event.error ||
                  event.status ||
                  "—"}
              </div>
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
