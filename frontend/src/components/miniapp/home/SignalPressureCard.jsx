import { motion } from 'framer-motion';

const DIR_COLORS = { BULLISH: '#4ade80', BEARISH: '#f87171', NEUTRAL: '#a1a1aa', MIXED: '#facc15' };
const RISK_COLORS = { LOW: '#4ade80', MEDIUM: '#facc15', HIGH: '#f87171', UNKNOWN: '#a1a1aa' };

export function SignalPressureCard({ pressure }) {
  if (!pressure) return null;
  const net = pressure.net;
  const netColor = DIR_COLORS[net.direction] || '#a1a1aa';

  const rows = [
    { key: 'exchange', label: 'Exchange', dir: pressure.exchange.direction, score: pressure.exchange.score },
    { key: 'onchain', label: 'OnChain', dir: pressure.onchain.direction, score: pressure.onchain.score },
    { key: 'sentiment', label: 'Sentiment', dir: pressure.sentiment.direction, score: pressure.sentiment.score },
    { key: 'twitter', label: 'Twitter', text: pressure.twitter.label },
    { key: 'mlRisk', label: 'ML Risk', risk: pressure.mlRisk.level },
  ];

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: 0.4 }}
      data-testid="signal-pressure-card"
      style={{
        margin: '10px 16px 0',
        padding: '14px 16px',
        background: 'var(--ma-surface)',
        borderRadius: '16px',
        border: '1px solid var(--ma-border)',
      }}
    >
      <div
        data-testid="net-pressure"
        style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '10px 12px', marginBottom: '10px',
          background: `${netColor}10`, borderRadius: '12px', border: `1px solid ${netColor}20`,
        }}
      >
        <div>
          <div style={{ fontSize: '10px', fontWeight: 700, letterSpacing: '0.15em', color: 'var(--ma-muted)', textTransform: 'uppercase', fontFamily: "'Manrope', sans-serif", marginBottom: '2px' }}>
            Net Pressure
          </div>
          <div style={{ fontSize: '11px', color: 'var(--ma-muted)', fontFamily: "'Manrope', sans-serif" }}>
            {net.summary}
          </div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: '16px', fontWeight: 700, color: netColor, fontFamily: "'Oswald', sans-serif", letterSpacing: '0.05em' }}>
            {net.direction}
          </div>
          <div style={{ fontSize: '10px', fontWeight: 600, color: 'var(--ma-muted)', fontFamily: "'JetBrains Mono', monospace" }}>
            {net.confidence}
          </div>
        </div>
      </div>

      <div style={{ fontSize: '10px', fontWeight: 700, letterSpacing: '0.15em', color: 'var(--ma-muted)', textTransform: 'uppercase', fontFamily: "'Manrope', sans-serif", marginBottom: '6px' }}>
        Breakdown
      </div>
      {rows.map((r, i) => (
        <motion.div
          key={r.key}
          initial={{ opacity: 0, x: -8 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.45 + i * 0.05 }}
          style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '9px 0', borderBottom: i < rows.length - 1 ? '1px solid var(--ma-divider, var(--ma-border))' : 'none',
          }}
        >
          <span style={{ fontSize: '13px', fontWeight: 500, color: 'var(--ma-secondary)', fontFamily: "'Manrope', sans-serif" }}>
            {r.label}
          </span>
          {r.risk ? (
            <span data-testid={`signal-${r.key}`} style={{
              fontSize: '11px', fontWeight: 700,
              color: RISK_COLORS[r.risk] || '#a1a1aa',
              fontFamily: "'JetBrains Mono', monospace", textTransform: 'uppercase',
              padding: '2px 10px', background: `${RISK_COLORS[r.risk] || '#a1a1aa'}18`, borderRadius: '20px',
            }}>
              {r.risk}
            </span>
          ) : r.text ? (
            <span style={{ fontSize: '11px', color: 'var(--ma-muted)', fontFamily: "'Manrope', sans-serif", maxWidth: '180px', textAlign: 'right', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {r.text}
            </span>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ fontSize: '12px', fontWeight: 700, fontFamily: "'JetBrains Mono', monospace", color: DIR_COLORS[r.dir] || '#a1a1aa' }}>
                {r.score > 0 ? '+' : ''}{r.score}
              </span>
              <span style={{ fontSize: '10px', width: '8px', textAlign: 'center', color: DIR_COLORS[r.dir] || '#a1a1aa' }}>
                {r.dir === 'BULLISH' ? '\u2191' : r.dir === 'BEARISH' ? '\u2193' : '\u2194'}
              </span>
            </div>
          )}
        </motion.div>
      ))}
    </motion.div>
  );
}
