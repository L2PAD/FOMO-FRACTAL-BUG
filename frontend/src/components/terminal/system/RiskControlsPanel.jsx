export default function RiskControlsPanel() {
  return (
    <div className="border border-neutral-200 rounded-lg p-4 overflow-auto">
      <div className="mb-4 font-semibold text-neutral-900">Risk Controls</div>

      <div className="space-y-3 text-sm">
        <div className="flex justify-between">
          <span className="text-neutral-600">Kill Switch:</span>
          <span className="text-green-600 font-semibold">OFF</span>
        </div>

        <div className="flex justify-between">
          <span className="text-neutral-600">Max Drawdown:</span>
          <span className="font-mono">10%</span>
        </div>

        <div className="flex justify-between">
          <span className="text-neutral-600">Daily Loss Limit:</span>
          <span className="font-mono">5%</span>
        </div>

        <div className="flex justify-between">
          <span className="text-neutral-600">Max Heat:</span>
          <span className="font-mono">70%</span>
        </div>

        <div className="flex justify-between">
          <span className="text-neutral-600">Max Positions:</span>
          <span className="font-mono">10</span>
        </div>

        <div className="flex justify-between">
          <span className="text-neutral-600">Max Symbol Concentration:</span>
          <span className="font-mono">30%</span>
        </div>

        <div className="flex justify-between">
          <span className="text-neutral-600">Execution Threshold:</span>
          <span className="font-mono">60</span>
        </div>
      </div>
    </div>
  );
}
