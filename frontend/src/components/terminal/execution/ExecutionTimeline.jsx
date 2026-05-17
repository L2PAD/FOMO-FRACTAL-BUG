import { useMemo } from "react";
import { useTerminal } from "../../../store/terminalStore";

export default function ExecutionTimeline() {
  const { state } = useTerminal();

  const steps = useMemo(() => {
    const positions = state.positions || [];
    const hasPosition = positions.some(p => p.status === "OPEN");

    return [
      { label: "Signal", completed: true },
      { label: "Order Submitted", completed: true },
      { label: "Partial Fill", completed: hasPosition },
      { label: "Full Fill", completed: hasPosition },
      { label: "Position Open", completed: hasPosition }
    ];
  }, [state.positions]);

  return (
    <div className="bg-white rounded-xl p-5 border border-[#E5E7EB]" data-testid="execution-timeline">
      <div className="text-xs font-semibold text-neutral-500 mb-4 tracking-wide">
        EXECUTION FLOW
      </div>

      <div className="flex items-center justify-between relative">
        {/* Connection line */}
        <div className="absolute top-2 left-0 right-0 h-0.5 bg-neutral-200" style={{ zIndex: 0 }} />

        {steps.map((step, i) => (
          <div key={i} className="flex flex-col items-center text-xs relative" style={{ zIndex: 1 }}>
            {/* Dot */}
            <div 
              className={`w-4 h-4 rounded-full mb-2 border-2 ${
                step.completed 
                  ? "bg-green-500 border-green-500" 
                  : "bg-white border-neutral-300"
              }`}
            />

            {/* Label */}
            <div className={`text-center max-w-[80px] ${
              step.completed ? "text-neutral-800 font-medium" : "text-neutral-400"
            }`}>
              {step.label}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
