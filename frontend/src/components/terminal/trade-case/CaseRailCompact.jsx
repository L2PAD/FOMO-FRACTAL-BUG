import { useTerminal } from '../../../store/terminalStore';
import { useMemo } from 'react';
import { useTradingCases } from '../../../hooks/useTradingCases';

/**
 * CaseRailCompact — left rail "Opportunities".
 *
 * Phase closing-loop.MARK (2026-04-23) — store/data hooks UNCHANGED.
 * Visual cleanup 2026-04-30:
 *   • "CASES (N)" → "Opportunities" + secondary count line
 *   • Empty state → explanatory copy, not a one-liner
 *   • Per-row dev codes (LONG/ACTIVE/4H/Mark/Entry) replaced with
 *     a calmer hierarchy: symbol + direction tag + status word.
 */
export default function CaseRailCompact() {
  const { state, dispatch } = useTerminal();
  const selectedCaseId = state.selectedCase?.id;
  const { cases: realCases, loading, error } = useTradingCases();

  const sortedCases = useMemo(() => {
    if (!realCases || realCases.length === 0) return [];
    const statusOrder = { ACTIVE: 0, CLOSED_WIN: 1, CLOSED_LOSS: 2, WATCHING: 3 };
    return [...realCases].sort(
      (a, b) => (statusOrder[a.status] || 9) - (statusOrder[b.status] || 9)
    );
  }, [realCases]);

  const { totalPnl, activeCount } = useMemo(() => {
    let total = 0;
    let n = 0;
    for (const c of sortedCases) {
      if (c.status === 'ACTIVE') {
        total += Number(c.pnl || 0);
        n += 1;
      }
    }
    return { totalPnl: total, activeCount: n };
  }, [sortedCases]);

  const handleCaseSelect = (caseData) => {
    dispatch({ type: 'SET_SELECTED_CASE', payload: caseData });
  };

  const pnlTone =
    totalPnl > 0 ? 'text-emerald-600' : totalPnl < 0 ? 'text-red-600' : 'text-gray-500';

  return (
    <div className="flex flex-col h-full bg-white" data-testid="case-rail-compact">
      {/* Header — product framing, not dev count */}
      <div className="px-4 py-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-900">Opportunities</h3>
          {activeCount > 0 && (
            <span
              className={`text-sm font-semibold tabular-nums ${pnlTone}`}
              data-testid="total-pnl"
            >
              {totalPnl >= 0 ? '+' : ''}${totalPnl.toFixed(2)}
            </span>
          )}
        </div>
        <p className="text-xs text-gray-500 mt-0.5">
          {sortedCases.length === 0
            ? 'No setups yet'
            : activeCount > 0
              ? `${activeCount} active · unrealized PnL`
              : `${sortedCases.length} closed · history`}
        </p>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto">
        {loading && sortedCases.length === 0 && (
          <div className="flex items-center justify-center h-20">
            <span className="text-xs text-gray-400">Loading…</span>
          </div>
        )}

        {error && (
          <div className="px-4 py-3">
            <p className="text-xs text-red-600">Couldn’t load opportunities.</p>
            <p className="text-[11px] text-gray-400 mt-0.5">{String(error)}</p>
          </div>
        )}

        {!loading && !error && sortedCases.length === 0 && (
          <div className="px-4 py-6">
            <p className="text-sm text-gray-700 font-medium">No active opportunities yet.</p>
            <p className="text-xs text-gray-500 mt-1 leading-relaxed">
              Setups appear here automatically when the system detects a valid
              signal on one of the watched markets.
            </p>
          </div>
        )}

        {sortedCases.map((caseItem) => {
          const isSelected = selectedCaseId === caseItem.id;
          const isLong = caseItem.direction === 'LONG';
          const isActive = caseItem.status === 'ACTIVE';
          const pnlNum = Number(caseItem.pnl || 0);
          const pnlPctNum = Number(caseItem.pnl_pct || 0);
          const showPnl = isActive || (caseItem.trade_count || 0) > 0;
          const pnlToneRow =
            pnlNum > 0
              ? 'text-emerald-600'
              : pnlNum < 0
              ? 'text-red-600'
              : 'text-gray-400';

          // Status word — calmer, non-shouty caps.
          const statusWord = isActive
            ? 'Active'
            : caseItem.status === 'CLOSED_WIN'
              ? 'Closed · win'
              : caseItem.status === 'CLOSED_LOSS'
                ? 'Closed · loss'
                : caseItem.status === 'WATCHING'
                  ? 'Watching'
                  : (caseItem.status || '').toLowerCase();

          return (
            <button
              type="button"
              key={caseItem.id}
              onClick={() => handleCaseSelect(caseItem)}
              className={`w-full text-left px-4 py-3 transition-colors ${
                isSelected
                  ? isLong
                    ? 'bg-emerald-50/80'
                    : 'bg-red-50/80'
                  : 'hover:bg-gray-50'
              }`}
              data-testid={`case-item-${caseItem.id}`}
            >
              {/* Row 1 — symbol + pnl% */}
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold text-gray-900">
                  {caseItem.symbol?.replace('USDT', '')}
                </span>
                {showPnl && (
                  <span
                    className={`text-xs font-semibold tabular-nums ${pnlToneRow}`}
                    data-testid={`case-pnl-${caseItem.id}`}
                  >
                    {pnlNum >= 0 ? '+' : ''}
                    {pnlPctNum.toFixed(2)}%
                  </span>
                )}
              </div>

              {/* Row 2 — direction tag + status (no pipes, no caps spam) */}
              <div className="flex items-center gap-2 mt-1">
                <span
                  className={`text-[11px] font-semibold px-1.5 py-0.5 rounded ${
                    isLong
                      ? 'bg-emerald-50 text-emerald-700'
                      : 'bg-red-50 text-red-700'
                  }`}
                >
                  {isLong ? 'Long' : 'Short'}
                </span>
                <span className="text-xs text-gray-500">{statusWord}</span>
                {isActive && (
                  <span
                    className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"
                    aria-hidden
                  />
                )}
              </div>

              {/* Row 3 — prices + pnl$, smaller */}
              <div className="flex items-center justify-between text-xs text-gray-500 mt-1.5 tabular-nums">
                <span>Entry ${caseItem.entry_price?.toFixed(0) || '—'}</span>
                {isActive && caseItem.current_price != null && (
                  <span>Mark ${caseItem.current_price.toFixed(0)}</span>
                )}
              </div>
              {showPnl && (
                <div className={`text-[11px] font-semibold tabular-nums mt-0.5 ${pnlToneRow}`}>
                  {pnlNum >= 0 ? '+' : ''}${Math.abs(pnlNum).toFixed(2)}
                </div>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
