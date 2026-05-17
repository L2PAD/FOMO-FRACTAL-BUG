import { useTerminal } from "../../../store/terminalStore";

export default function ExecutionDiagnostics() {
  const { state } = useTerminal();
  const execution = state.execution || {};

  const quality = Number(execution.avg_quality || 0);
  const slippage = Number(execution.avg_slippage || 0);
  const latency = Number(execution.avg_latency || 0);

  const warnings = [];

  if (quality > 0 && quality < 60) {
    warnings.push("Execution quality is poor");
  }

  if (slippage > 15) {
    warnings.push("High slippage detected");
  }

  if (latency > 400) {
    warnings.push("Latency is elevated");
  }

  if ((execution.rejected || 0) > 0) {
    warnings.push("There are rejected orders");
  }

  return (
    <div className="border border-[#E5E7EB] rounded-lg p-4 overflow-auto">
      <div className="mb-3 font-semibold text-neutral-900">Diagnostics</div>

      <div className="space-y-3 text-sm">
        <div>
          <div className="text-xs text-neutral-500">Execution Quality</div>
          <div className="font-medium font-mono">{quality.toFixed(1)}</div>
        </div>

        <div>
          <div className="text-xs text-neutral-500">Slippage</div>
          <div className="font-medium font-mono">{slippage.toFixed(2)} bps</div>
        </div>

        <div>
          <div className="text-xs text-neutral-500">Latency</div>
          <div className="font-medium font-mono">{latency.toFixed(0)} ms</div>
        </div>

        <div>
          <div className="text-xs text-neutral-500">Reject Rate</div>
          <div className="font-medium font-mono">
            {Number(execution.reject_rate || 0).toFixed(2)}%
          </div>
        </div>

        <div className="pt-3 border-t border-[#E5E7EB]">
          <div className="text-xs text-neutral-500 mb-2">Warnings</div>
          {warnings.length === 0 ? (
            <div className="text-xs text-neutral-400">No active warnings</div>
          ) : (
            <div className="space-y-1">
              {warnings.map((w, i) => (
                <div key={i} className="text-xs text-red-600 bg-red-50 rounded px-2 py-1">
                  {w}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
