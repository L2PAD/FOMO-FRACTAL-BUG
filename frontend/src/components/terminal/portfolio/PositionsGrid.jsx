import { useTerminal } from "../../../store/terminalStore";

export default function PositionsGrid() {
  const { state, dispatch } = useTerminal();

  const positions = state.positions || [];

  return (
    <div className="border border-neutral-200 rounded-lg p-4 flex-1 overflow-auto">
      <div className="mb-3 font-semibold text-neutral-900">Positions</div>

      {positions.length === 0 && (
        <div className="text-neutral-400 text-sm">No open positions</div>
      )}

      {positions.length > 0 && (
        <table className="w-full text-xs">
          <thead>
            <tr className="text-neutral-500 border-b border-neutral-200">
              <th align="left" className="pb-2">Symbol</th>
              <th align="left" className="pb-2">Side</th>
              <th align="right" className="pb-2">Size</th>
              <th align="right" className="pb-2">Entry</th>
              <th align="right" className="pb-2">PnL</th>
            </tr>
          </thead>

          <tbody>
            {positions.map((p) => (
              <tr
                key={p.symbol}
                className="cursor-pointer hover:bg-neutral-50 border-b border-neutral-100"
                onClick={() =>
                  dispatch({
                    type: "SET_SYMBOL",
                    payload: p.symbol,
                  })
                }
              >
                <td className="py-2 font-medium">{p.symbol}</td>
                <td className="py-2">{p.side}</td>
                <td align="right" className="py-2 font-mono">{p.size}</td>
                <td align="right" className="py-2 font-mono">${Number(p.entry_price || 0).toFixed(2)}</td>
                <td align="right" className="py-2 font-mono">${Number(p.unrealized_pnl || 0).toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
