import React from 'react';

const CTX_COLORS = { bullish: '#22c55e', bearish: '#E5484D', neutral: '#94a3b8', uncertain: '#64748b' };
const CTX_ICONS = { bullish: '\u25B2', bearish: '\u25BC', neutral: '\u25C6', uncertain: '?' };

const MarketContextBlock = React.memo(({ marketContext }) => {
  if (!marketContext) return null;
  const ctxColor = CTX_COLORS[marketContext.type] || '#94a3b8';
  return (
    <div data-testid="market-context-panel" style={{
      padding: '10px 12px', borderRadius: '8px', marginBottom: '10px',
      background: `linear-gradient(135deg, ${ctxColor}12, ${ctxColor}06)`,
      border: `1px solid ${ctxColor}33`,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ fontSize: '14px', color: ctxColor }}>{CTX_ICONS[marketContext.type]}</span>
          <span data-testid="market-context-type" style={{ fontWeight: 700, fontSize: '12px', color: ctxColor, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            {marketContext.type}
          </span>
        </div>
        <span data-testid="market-context-confidence" style={{
          fontSize: '10px', fontWeight: 700, color: ctxColor,
          backgroundColor: `${ctxColor}1A`, padding: '2px 7px', borderRadius: '4px',
        }}>
          {Math.round(marketContext.confidence * 100)}%
        </span>
      </div>
      <div data-testid="market-context-summary" style={{ fontSize: '11px', color: '#e2e8f0', fontWeight: 500, marginBottom: '8px', lineHeight: 1.4 }}>
        {marketContext.summary}
      </div>
      {/* Score bar */}
      <div style={{ marginBottom: '8px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '9px', color: '#64748b', marginBottom: '3px' }}>
          <span>Bull: {marketContext.bullish_score}</span>
          <span>Bear: {marketContext.bearish_score}</span>
        </div>
        <div style={{ display: 'flex', height: '4px', borderRadius: '2px', overflow: 'hidden', backgroundColor: 'rgba(100,116,139,0.15)' }}>
          {(marketContext.bullish_score + marketContext.bearish_score) > 0 && (
            <>
              <div style={{ width: `${(marketContext.bullish_score / (marketContext.bullish_score + marketContext.bearish_score)) * 100}%`, backgroundColor: '#22c55e', transition: 'width 0.3s' }} />
              <div style={{ width: `${(marketContext.bearish_score / (marketContext.bullish_score + marketContext.bearish_score)) * 100}%`, backgroundColor: '#E5484D', transition: 'width 0.3s' }} />
            </>
          )}
        </div>
      </div>
      {/* Drivers */}
      {marketContext.drivers && marketContext.drivers.length > 0 && (
        <div data-testid="market-context-drivers" style={{ marginBottom: '6px' }}>
          <div style={{ fontSize: '9px', color: '#64748b', fontWeight: 600, textTransform: 'uppercase', marginBottom: '3px', letterSpacing: '0.05em' }}>Drivers</div>
          {marketContext.drivers.map((d, di) => (
            <div key={di} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', padding: '2px 0' }}>
              <span style={{ color: '#22c55e' }}>{d.type.replace(/_/g, ' ')}</span>
              <span style={{ color: '#94a3b8' }}>+{d.contribution}</span>
            </div>
          ))}
        </div>
      )}
      {/* Risks */}
      {marketContext.risks && marketContext.risks.length > 0 && (
        <div data-testid="market-context-risks">
          <div style={{ fontSize: '9px', color: '#64748b', fontWeight: 600, textTransform: 'uppercase', marginBottom: '3px', letterSpacing: '0.05em' }}>Risks</div>
          {marketContext.risks.map((r, ri) => (
            <div key={ri} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', padding: '2px 0' }}>
              <span style={{ color: '#E5484D' }}>{r.type.replace(/_/g, ' ')}</span>
              <span style={{ color: '#94a3b8' }}>-{r.contribution}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
});

MarketContextBlock.displayName = 'MarketContextBlock';

export default MarketContextBlock;
