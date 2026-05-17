import { useTerminal } from '../../../store/terminalStore';
import { useMemo } from 'react';
import { MOCK_CASES } from '../../../data/mockCases';

export default function CaseRail() {
  const { state, dispatch } = useTerminal();
  const selectedCaseId = state.selectedCase?.id;

  // Sort: ACTIVE → CLOSED_WIN → CLOSED_LOSS → WATCHING
  const sortedCases = useMemo(() => {
    const statusOrder = {
      ACTIVE: 0,
      CLOSED_WIN: 1,
      CLOSED_LOSS: 2,
      WATCHING: 3
    };

    return [...MOCK_CASES].sort((a, b) => {
      return statusOrder[a.status] - statusOrder[b.status];
    });
  }, []);

  const handleCaseSelect = (caseData) => {
    dispatch({
      type: 'SET_SELECTED_CASE',
      payload: caseData
    });
  };

  return (
    <div className="flex flex-col h-full bg-white border-r border-neutral-200" data-testid="case-rail">
      {/* Header */}
      <div className="px-3 py-3 border-b border-neutral-200 bg-neutral-50">
        <h3 className="text-xs font-bold text-neutral-700 uppercase tracking-wider">
          Trade Cases
        </h3>
      </div>

      {/* Cases List */}
      <div className="flex-1 overflow-y-auto">
        {sortedCases.map((caseItem) => {
          const isSelected = selectedCaseId === caseItem.id;
          const isActive = caseItem.status === 'ACTIVE';
          const isClosedWin = caseItem.status === 'CLOSED_WIN';
          const isClosedLoss = caseItem.status === 'CLOSED_LOSS';
          const isWatching = caseItem.status === 'WATCHING';

          // Background colors
          let bgClass = 'bg-white hover:bg-neutral-50';
          let borderClass = 'border-l-4 border-l-transparent';
          
          if (isSelected) {
            if (caseItem.direction === 'LONG') {
              bgClass = 'bg-green-50 hover:bg-green-100';
              borderClass = 'border-l-4 border-l-green-500';
            } else {
              bgClass = 'bg-red-50 hover:bg-red-100';
              borderClass = 'border-l-4 border-l-red-500';
            }
          }

          return (
            <div
              key={caseItem.id}
              onClick={() => handleCaseSelect(caseItem)}
              className={`px-3 py-3 border-b border-neutral-100 cursor-pointer transition-all duration-150 ${bgClass} ${borderClass}`}
              data-testid={`case-item-${caseItem.id}`}
            >
              {/* Symbol + Direction */}
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-sm font-bold text-neutral-900">
                  {caseItem.symbol.replace('USDT', '')}
                </span>
                <span
                  className={`text-xs font-semibold px-1.5 py-0.5 rounded ${
                    caseItem.direction === 'LONG'
                      ? 'bg-green-100 text-green-700'
                      : 'bg-red-100 text-red-700'
                  }`}
                >
                  {caseItem.direction}
                </span>
              </div>

              {/* Status + TF */}
              <div className="flex items-center gap-1.5 mb-1.5">
                {/* Live indicator for ACTIVE */}
                {isActive && (
                  <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
                )}
                <span className="text-xs text-neutral-600 font-medium">
                  {isActive && 'ACTIVE'}
                  {isClosedWin && 'CLOSED +'}
                  {isClosedLoss && 'CLOSED −'}
                  {isWatching && 'WATCHING'}
                </span>
                <span className="text-xs text-neutral-500">·</span>
                <span className="text-xs text-neutral-600">{caseItem.trading_tf}</span>
              </div>

              {/* Duration + Trade Count */}
              <div className="flex items-center gap-1.5 mb-1.5 text-xs text-neutral-500">
                <span>{caseItem.duration}</span>
                {caseItem.trade_count > 0 && (
                  <>
                    <span>·</span>
                    <span>{caseItem.trade_count} exec</span>
                  </>
                )}
              </div>

              {/* PnL */}
              {caseItem.trade_count > 0 && (
                <div
                  className={`text-sm font-bold ${
                    caseItem.pnl >= 0 ? 'text-green-700' : 'text-red-700'
                  }`}
                >
                  {caseItem.pnl >= 0 ? '+' : ''}{caseItem.pnl_pct.toFixed(1)}%
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
