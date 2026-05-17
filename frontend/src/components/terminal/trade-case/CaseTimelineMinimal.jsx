export default function CaseTimelineMinimal({ caseData }) {
  if (!caseData || !caseData.timeline) {
    return null;
  }

  return (
    <div
      className="h-10 px-4 py-1.5 bg-neutral-50 border-t border-neutral-200 flex items-center overflow-x-auto"
      data-testid="case-timeline-minimal"
      style={{ marginLeft: '220px' }}
    >
      <div className="flex items-center gap-1 min-w-max">
        {caseData.timeline.map((item, index) => {
          const isLast = index === caseData.timeline.length - 1;

          return (
            <div key={index} className="flex items-center">
              {/* Event */}
              <div className="flex items-center gap-1">
                <div className={`w-1.5 h-1.5 rounded-full ${
                  isLast ? 'bg-green-500 animate-pulse' : 'bg-neutral-400'
                }`} />
                <span className="text-xs text-neutral-700 font-medium whitespace-nowrap">
                  {item.label}
                </span>
              </div>

              {/* Arrow */}
              {index < caseData.timeline.length - 1 && (
                <span className="text-neutral-400 mx-2 text-xs">→</span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
