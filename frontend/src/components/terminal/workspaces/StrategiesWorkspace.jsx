import StrategySummaryBar from "../strategy/StrategySummaryBar";
import LiveSignalStream from "../strategy/LiveSignalStream";
import DecisionDetailsPanel from "../strategy/DecisionDetailsPanel";

export default function StrategyWorkspace() {
  return (
    <div className="max-w-[1400px] mx-auto px-6 py-6 space-y-6">
      <div className="mb-4">
        <h2 className="text-xl font-semibold text-gray-100 mb-1">Strategy Visibility</h2>
        <p className="text-sm text-gray-400">
          Live TA signals, runtime decisions, and execution context
        </p>
      </div>

      <StrategySummaryBar />

      <div className="grid grid-cols-12 gap-6">
        <div className="col-span-7">
          <LiveSignalStream />
        </div>

        <div className="col-span-5">
          <DecisionDetailsPanel />
        </div>
      </div>
    </div>
  );
}
