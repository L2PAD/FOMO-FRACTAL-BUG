/**
 * CaseCommandHeaderUltraCompact — strip above the chart.
 *
 * Visual cleanup 2026-04-30:
 *   • Empty state now answers the user’s 5-question test instead of
 *     a one-line dev hint. No coloured left bar when nothing is
 *     selected (was a misleading green/red border).
 *   • Selected state keeps the directional tone bar but drops the
 *     dev-y "4H · N exec" trail — timeframe lives on chart
 *     controls now, exec count moves to the Activity feed.
 */
export default function CaseCommandHeaderUltraCompact({ caseData }) {
  if (!caseData) {
    // Empty state — keep it minimal so it doesn't repeat the chart
    // header right below it. Acts as a one-line breadcrumb only.
    return (
      <div
        className="bg-white px-4 py-2"
        data-testid="case-command-header-empty"
      >
        <p className="text-xs text-gray-500">
          Watching the market — no open position.
        </p>
      </div>
    );
  }

  const isLong = caseData.direction === 'LONG';
  const isActive = caseData.status === 'ACTIVE';
  const pnlNum = Number(caseData.pnl || 0);
  const pnlPct = Number(caseData.pnl_pct || 0);
  const pnlPositive = pnlNum >= 0;
  const pnlTone = pnlPositive ? 'text-emerald-600' : 'text-red-600';

  // Status word — calmer, no caps spam.
  const statusWord =
    caseData.status === 'ACTIVE'       ? 'Active'
  : caseData.status === 'CLOSED_WIN'   ? 'Closed · win'
  : caseData.status === 'CLOSED_LOSS'  ? 'Closed · loss'
  : caseData.status === 'WATCHING'     ? 'Watching'
  : (caseData.status || '').toLowerCase();

  return (
    <div
      className="bg-white px-4 py-3"
      data-testid="case-command-header-ultra-compact"
      style={{
        fontVariantNumeric: 'tabular-nums',
        // Single thin tone bar for the active direction — not a debug border.
        boxShadow: `inset 3px 0 0 ${isLong ? '#10b981' : '#ef4444'}`,
      }}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-sm font-semibold text-gray-900">
            {caseData.symbol?.replace('USDT', '')}/USDT
          </h2>
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
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" aria-hidden />
          )}
        </div>

        <div className="flex items-center gap-4 text-xs">
          <span className={`font-semibold ${pnlTone}`}>
            {pnlPositive ? '+' : ''}{pnlPct.toFixed(2)}%
          </span>
          <span className={`font-semibold ${pnlTone}`}>
            {pnlPositive ? '+' : ''}${Math.abs(pnlNum).toFixed(2)}
          </span>
          <span className="text-gray-500">
            <span className="text-gray-400">Entry </span>
            ${caseData.entry_price?.toFixed(2) || '—'}
          </span>
          <span className="text-gray-500">
            <span className="text-gray-400">Mark </span>
            ${caseData.current_price?.toFixed(2) || '—'}
          </span>
        </div>
      </div>

      {(caseData.thesis || caseData.strategy) && (
        <div className="mt-1 flex items-center gap-4 text-xs text-gray-500">
          {caseData.thesis && (
            <span>
              <span className="text-gray-400">Thesis </span>
              <span className="text-gray-700">{caseData.thesis}</span>
            </span>
          )}
          {caseData.strategy && (
            <span>
              <span className="text-gray-400">Strategy </span>
              <span className="text-gray-700">{caseData.strategy}</span>
            </span>
          )}
        </div>
      )}
    </div>
  );
}
