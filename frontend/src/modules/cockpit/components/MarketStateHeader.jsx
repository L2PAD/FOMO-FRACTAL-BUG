/**
 * MarketStateHeader
 * =================
 *
 * PHASE 5.2 polish (2026-04-30) — 3-line key:value format.
 *
 *   Line 1:  Market: Neutral
 *   Line 2:  Confidence: 53%  ·  Tradeability: Low
 *   Line 3:  Signals are mixed across timeframes
 *
 * Visual hierarchy:
 *   • "Market:" / "Confidence:" / "Tradeability:" — text-gray-500 labels
 *   • Values         — text-gray-900 with semantic color when relevant
 *   • Tradeability  — yellow on Low, red on Off, emerald on High
 *   • Bias          — emerald / red / gray-900
 *
 * Reads same fields as before. No new endpoints, no derivation.
 */
import React from 'react';
import styled from 'styled-components';

const Wrap = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 16px 22px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  margin-bottom: 12px;
  flex-wrap: wrap;
`;

const Asset = styled.div`
  display: flex;
  align-items: baseline;
  gap: 10px;
  flex-shrink: 0;

  .pair {
    font-size: 16px;
    font-weight: 700;
    color: #0f172a;
    letter-spacing: -0.01em;
  }

  .tf {
    font-size: 12px;
    font-weight: 500;
    color: #64748b;
  }
`;

const Lines = styled.div`
  display: flex;
  flex-direction: column;
  gap: 4px;
  text-align: right;
  flex: 1;
  min-width: 280px;
  font-size: 13px;
  line-height: 1.4;
`;

const Row = styled.div`
  display: flex;
  align-items: baseline;
  justify-content: flex-end;
  gap: 6px;
  flex-wrap: wrap;

  .label  { color: #94a3b8; font-weight: 500; }
  .value  { color: #0f172a; font-weight: 600; }
  .sep    { color: #cbd5e1; }
  .muted  { color: #64748b; }
  .up     { color: #059669; font-weight: 600; }
  .down   { color: #dc2626; font-weight: 600; }
  .warn   { color: #d97706; font-weight: 600; }
`;

function titleCase(s) {
  if (!s) return '';
  return String(s).charAt(0).toUpperCase() + String(s).slice(1).toLowerCase();
}

function biasClass(bias) {
  const b = String(bias || '').toLowerCase();
  if (b === 'bullish') return 'up';
  if (b === 'bearish') return 'down';
  return 'value';
}

function tradeabilityClass(t) {
  const v = String(t || '').toLowerCase();
  if (v === 'high')   return 'up';
  if (v === 'low')    return 'warn';
  if (v === 'off' || v === 'blocked') return 'down';
  return 'value';
}

function alignmentPhrase(a) {
  const v = String(a || '').toLowerCase();
  if (v === 'aligned')        return 'aligned across timeframes';
  if (v === 'counter_trend')  return 'counter-trend across timeframes';
  return 'mixed across timeframes';
}

function alignmentClass(a) {
  const v = String(a || '').toLowerCase();
  if (v === 'aligned')        return 'up';
  if (v === 'counter_trend')  return 'down';
  return 'value';
}

const MarketStateHeader = ({ unified, mtfContext }) => {
  if (!unified) return null;

  const {
    symbol,
    timeframe,
    bias,
    confidence,
    tradeability,
    alignment,
  } = unified;

  const macro = mtfContext?.global_bias || mtfContext?.timeframes?.macro?.bias;
  const mid   = mtfContext?.setup_bias  || mtfContext?.timeframes?.mid?.bias;
  const short = mtfContext?.entry_bias  || mtfContext?.timeframes?.short?.bias;

  const confPct = Math.round(((confidence ?? 0) || 0) * 100);
  const trendsKnown = !!(macro || mid || short);

  return (
    <Wrap data-testid="market-state-header">
      <Asset>
        <span className="pair">{symbol || '—'}</span>
        <span className="tf">{timeframe || '—'}</span>
      </Asset>

      <Lines>
        {/* Line 1 — Market state */}
        <Row>
          <span className="label">Market:</span>
          <span className={biasClass(bias)}>{titleCase(bias) || 'Neutral'}</span>
        </Row>

        {/* Line 2 — Strength of the signal */}
        <Row>
          <span className="label">Confidence:</span>
          <span className="value">{confPct}%</span>
          <span className="sep">·</span>
          <span className="label">Tradeability:</span>
          <span className={tradeabilityClass(tradeability)}>
            {titleCase(tradeability) || 'Low'}
          </span>
        </Row>

        {/* Line 3 — Multi-timeframe context (only if known) */}
        {(alignment || trendsKnown) && (
          <Row>
            {alignment && (
              <>
                <span className="muted">Signals are</span>{' '}
                <span className={alignmentClass(alignment)}>
                  {alignmentPhrase(alignment)}
                </span>
              </>
            )}
            {alignment && trendsKnown && <span className="sep">·</span>}
            {trendsKnown && (
              <span className="muted">
                {macro && <>macro {titleCase(macro)}</>}
                {macro && (mid || short) && ', '}
                {mid && <>mid {titleCase(mid)}</>}
                {mid && short && ', '}
                {short && <>short {titleCase(short)}</>}
              </span>
            )}
          </Row>
        )}
      </Lines>
    </Wrap>
  );
};

export default MarketStateHeader;
