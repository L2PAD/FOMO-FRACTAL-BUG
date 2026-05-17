export default function CaseTimeline({ caseData }) {
  if (!caseData || !caseData.timeline) {
    return null;
  }

  return (
    <div
      className="bg-white rounded-xl p-5 border border-neutral-200 shadow-sm transition-all duration-150 hover:shadow-md"
      data-testid="case-timeline"
    >
      <h3 className="text-xs font-bold text-neutral-500 mb-4 uppercase tracking-wider">
        Case Timeline
      </h3>

      <div className="relative">
        {/* Timeline Line */}
        <div className="absolute left-2 top-2 bottom-2 w-0.5 bg-neutral-200" />

        {/* Timeline Items */}
        <div className="space-y-4">
          {caseData.timeline.map((item, index) => {
            const isLast = index === caseData.timeline.length - 1;
            const isFirst = index === 0;

            return (
              <div key={index} className="relative flex items-start gap-4">
                {/* Dot */}
                <div
                  className={`relative z-10 w-4 h-4 rounded-full border-2 flex-shrink-0 ${
                    isLast
                      ? 'bg-green-500 border-green-500 animate-pulse'
                      : isFirst
                      ? 'bg-blue-500 border-blue-500'
                      : 'bg-white border-neutral-400'
                  }`}
                />

                {/* Content */}
                <div className="flex-1 pb-2">
                  <p className="text-sm font-bold text-neutral-900">{item.label}</p>
                  <p className="text-xs text-neutral-500 mt-0.5">{item.time}</p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
