export default function CaseTimelineCompact({ caseData }) {
  if (!caseData || !caseData.timeline) {
    return null;
  }

  return (
    <div
      className="h-20 px-6 py-3 bg-white border-t border-neutral-200 flex items-center overflow-x-auto"
      data-testid="case-timeline-compact"
      style={{ opacity: 0.85 }}
    >
      <div className="flex items-center gap-1 min-w-max">
        {caseData.timeline.map((item, index) => {
          const isLast = index === caseData.timeline.length - 1;
          const isFirst = index === 0;

          return (
            <div key={index} className="flex items-center">
              {/* Event */}
              <div className="flex flex-col items-center">
                <div
                  className={`w-2.5 h-2.5 rounded-full ${
                    isLast
                      ? 'bg-green-500 animate-pulse'
                      : isFirst
                      ? 'bg-blue-500'
                      : 'bg-neutral-400'
                  }`}
                />
                <p className="text-xs font-medium text-neutral-900 mt-1 whitespace-nowrap">
                  {item.label}
                </p>
                <p className="text-xs text-neutral-500 mt-0.5">{item.time}</p>
              </div>

              {/* Arrow */}
              {index < caseData.timeline.length - 1 && (
                <div className="w-8 h-px bg-neutral-300 mx-2" />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
