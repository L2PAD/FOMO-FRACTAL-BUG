function EventDot({ type }) {
  let cls = "bg-gray-500";
  const typeStr = String(type).toUpperCase();
  
  if (typeStr.includes("FILLED")) cls = "bg-green-500";
  else if (typeStr.includes("FAILED") || typeStr.includes("BLOCKED")) cls = "bg-red-500";
  else if (typeStr.includes("QUEUED") || typeStr.includes("SUBMITTED")) cls = "bg-yellow-500";
  else if (typeStr.includes("APPROVED")) cls = "bg-blue-500";

  return <span className={`w-2 h-2 rounded-full inline-block ${cls}`} />;
}

export default function EventTape({ events = [], isConnected }) {
  return (
    <div className="bg-gray-900/60 border border-gray-800 rounded-lg p-4" data-testid="event-tape">
      <div className="flex justify-between items-center mb-3">
        <div className="text-white font-semibold">Execution Tape</div>

        <div
          className={
            isConnected
              ? "text-green-400 text-xs font-semibold"
              : "text-yellow-400 text-xs font-semibold"
          }
        >
          {isConnected ? "🟢 LIVE" : "🟡 RECONNECTING"}
        </div>
      </div>

      {!events.length ? (
        <div className="text-gray-500 text-center py-6">Events will appear here in real-time</div>
      ) : (
        <div className="space-y-2 max-h-[420px] overflow-y-auto custom-scrollbar">
          {events.map((e, idx) => (
            <div
              key={idx}
              className="flex justify-between items-center border-b border-gray-800/50 pb-2 text-sm hover:bg-gray-800/30 px-2 py-1 rounded transition-colors"
              data-testid={`event-${idx}`}
            >
              <div className="flex gap-3 items-center">
                <EventDot type={e.event} />

                <span className="text-white font-medium">
                  {e.event}
                </span>

                {e.data?.symbol && (
                  <span className="text-gray-400">
                    {e.data.symbol}
                  </span>
                )}

                {e.data?.reason && (
                  <span className="text-red-400 text-xs">
                    ({e.data.reason})
                  </span>
                )}
              </div>

              <div className="text-xs text-gray-500">
                {new Date(e.ts).toLocaleTimeString()}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
