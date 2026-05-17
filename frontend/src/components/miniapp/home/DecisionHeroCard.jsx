import { motion } from 'framer-motion';

const STATE_COLORS = {
  BUY: { color: '#10b981', text: '#34d399', bg: 'rgba(16, 185, 129, 0.08)', border: 'rgba(16, 185, 129, 0.25)' },
  SELL: { color: '#ef4444', text: '#f87171', bg: 'rgba(239, 68, 68, 0.08)', border: 'rgba(239, 68, 68, 0.25)' },
  WAIT: { color: '#eab308', text: '#facc15', bg: 'rgba(234, 179, 8, 0.08)', border: 'rgba(234, 179, 8, 0.25)' },
  AVOID: { color: '#7f1d1d', text: '#fca5a5', bg: 'rgba(127, 29, 29, 0.15)', border: 'rgba(127, 29, 29, 0.4)' },
};

export function DecisionHeroCard({ data }) {
  if (!data) return null;
  const { decision, price, asset } = data;
  const s = STATE_COLORS[decision.action] || STATE_COLORS.WAIT;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      data-testid="decision-hero-card"
      style={{
        margin: '8px 16px 0',
        padding: '24px 20px',
        borderRadius: '20px',
        background: `radial-gradient(ellipse at top left, ${s.bg}, var(--ma-surface) 70%)`,
        border: `1px solid ${s.border}`,
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
        <span style={{
          fontSize: '11px', fontWeight: 700, letterSpacing: '0.2em',
          color: 'var(--ma-secondary)', textTransform: 'uppercase', fontFamily: "'Manrope', sans-serif",
        }}>
          {asset}
        </span>
        <span style={{
          fontSize: '9px', fontWeight: 700, letterSpacing: '0.12em',
          color: decision.mode === 'AGGRESSIVE' ? '#f87171' : decision.mode === 'DEFENSIVE' ? '#facc15' : 'var(--ma-secondary)',
          textTransform: 'uppercase', fontFamily: "'JetBrains Mono', monospace",
          background: decision.mode === 'AGGRESSIVE' ? 'rgba(239,68,68,0.12)' : decision.mode === 'DEFENSIVE' ? 'rgba(234,179,8,0.12)' : 'var(--ma-stat-bg)',
          padding: '3px 8px', borderRadius: '20px',
        }}
          data-testid="decision-mode"
        >
          {decision.mode}
        </span>
      </div>

      <div style={{ display: 'flex', alignItems: 'baseline', gap: '12px', marginBottom: '2px' }}>
        <span data-testid="hero-action" style={{
          fontSize: 'clamp(36px, 12vw, 56px)', fontFamily: "'Oswald', sans-serif",
          fontWeight: 700, color: s.text, lineHeight: 1, letterSpacing: '-0.02em',
        }}>
          {decision.action}
        </span>
      </div>

      <div style={{ display: 'flex', gap: '8px', marginBottom: '14px' }}>
        <span data-testid="hero-strength" style={{
          fontSize: '10px', fontWeight: 700, letterSpacing: '0.1em',
          color: s.text, opacity: 0.7, textTransform: 'uppercase', fontFamily: "'JetBrains Mono', monospace",
        }}>
          {decision.strength.replace('_', ' ')}
        </span>
        <span style={{ fontSize: '10px', color: 'var(--ma-muted)' }}>·</span>
        <span style={{
          fontSize: '10px', fontWeight: 600, color: 'var(--ma-muted)',
          textTransform: 'uppercase', fontFamily: "'JetBrains Mono', monospace",
          letterSpacing: '0.08em',
        }}>
          Risk: {decision.riskLevel}
        </span>
      </div>

      <div style={{ marginBottom: '16px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
          <span style={{ fontSize: '10px', color: 'var(--ma-muted)', fontWeight: 700, letterSpacing: '0.15em', textTransform: 'uppercase', fontFamily: "'Manrope', sans-serif" }}>
            Confidence
          </span>
          <span data-testid="hero-confidence" style={{ fontSize: '13px', color: s.text, fontWeight: 700, fontFamily: "'JetBrains Mono', monospace" }}>
            {Math.round(decision.confidence * 100)}%
          </span>
        </div>
        <div style={{ height: '3px', background: 'var(--ma-bar-bg, var(--ma-hover))', borderRadius: '2px', overflow: 'hidden' }}>
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${decision.confidence * 100}%` }}
            transition={{ duration: 0.8, ease: 'easeOut', delay: 0.2 }}
            style={{ height: '100%', background: s.color, borderRadius: '2px' }}
          />
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
        <DataPoint label="Price" value={`$${price.toLocaleString()}`} testId="hero-price" />
        <DataPoint
          label="Expected Move"
          value={`${decision.expectedMovePct >= 0 ? '+' : ''}${decision.expectedMovePct}%`}
          color={decision.expectedMovePct >= 0 ? '#34d399' : '#f87171'}
          testId="hero-move"
        />
        <DataPoint
          label="30D Range"
          value={`$${_fmtK(decision.range30d.min)} — $${_fmtK(decision.range30d.max)}`}
          testId="hero-range"
          span
        />
      </div>
    </motion.div>
  );
}

function _fmtK(v) {
  if (!v) return '?';
  if (v >= 1000) return `${(v / 1000).toFixed(1)}k`;
  return v.toFixed(0);
}

function DataPoint({ label, value, color, testId, span }) {
  return (
    <div style={{ gridColumn: span ? '1 / -1' : undefined }} data-testid={testId}>
      <div style={{ fontSize: '10px', fontWeight: 600, color: 'var(--ma-muted)', letterSpacing: '0.12em', textTransform: 'uppercase', fontFamily: "'Manrope', sans-serif", marginBottom: '2px' }}>
        {label}
      </div>
      <div style={{ fontSize: '14px', fontWeight: 700, color: color || 'var(--ma-text)', fontFamily: "'JetBrains Mono', monospace" }}>
        {value}
      </div>
    </div>
  );
}
