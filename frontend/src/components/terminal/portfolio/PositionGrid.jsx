import { useTerminal } from "../../../store/terminalStore";
import PositionCard from "./PositionCard";

export default function PositionGrid() {
  const { state } = useTerminal();

  const positions = (state.positions || []).filter(p => p.status === "OPEN");

  if (positions.length === 0) {
    return (
      <div className="bg-white rounded-xl p-8 border border-neutral-200 text-center">
        <div className="text-sm font-semibold text-neutral-500 mb-2">
          No Active Positions
        </div>
        <div className="text-xs text-neutral-400">
          → Waiting for high-quality setups
        </div>
      </div>
    );
  }

  return (
    <div data-testid="position-grid">
      <div className="text-sm font-semibold text-neutral-700 mb-3">
        Active Positions ({positions.length})
      </div>

      <div className="grid grid-cols-2 gap-4">
        {positions.map((position) => (
          <PositionCard key={position.symbol} position={position} />
        ))}
      </div>
    </div>
  );
}
