import { motion } from 'framer-motion';

const PILL_COLORS = {
  bullish: { bg: 'rgba(34, 197, 94, 0.15)', text: '#4ade80' },
  bearish: { bg: 'rgba(239, 68, 68, 0.15)', text: '#f87171' },
  neutral: { bg: 'rgba(161, 161, 170, 0.15)', text: '#a1a1aa' },
};

const ALIGNMENT_LABELS = {
  ALIGNED: 'All Aligned',
  SHORT_DIVERGENCE: 'Short-Term Divergence',
  LONG_DIVERGENCE: 'Long-Term Divergence',
  DIVERGENCE: 'Mixed Signals',
};

const ALIGNMENT_COLORS = {
  ALIGNED: '#4ade80',
  SHORT_DIVERGENCE: '#f87171',
  LONG_DIVERGENCE: '#facc15',
  DIVERGENCE: '#f87171',
};

export function StructureSnapshot({ structure }) {
  if (!structure) return null;

  const alignment = structure.alignment;
  const insight = structure.insight;
  const horizons = [
    { key: 'h24', label: '24H', ...structure.h24 },
    { key: 'd7', label: '7D', ...structure.d7 },
    { key: 'd30', label: '30D', ...structure.d30 },
  ];

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: 0.3 }}
      data-testid="structure-snapshot"
      style={{
        margin: '10px 16px 0',
        padding: '14px 16px',
        background: 'var(--ma-surface)',
        borderRadius: '16px',
        border: '1px solid var(--ma-border)',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
        <span style={{
          fontSize: '10px', fontWeight: 700, letterSpacing: '0.15em',
          color: 'var(--ma-muted)', textTransform: 'uppercase', fontFamily: "'Manrope', sans-serif",
        }}>
          Structure
        </span>
        <span data-testid="structure-alignment" style={{
          fontSize: '9px', fontWeight: 700,
          color: ALIGNMENT_COLORS[alignment] || '#a1a1aa',
          fontFamily: "'JetBrains Mono', monospace", letterSpacing: '0.05em',
          background: `${ALIGNMENT_COLORS[alignment] || '#a1a1aa'}15`,
          padding: '2px 8px', borderRadius: '20px',
        }}>
          {ALIGNMENT_LABELS[alignment] || alignment}
        </span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px', marginBottom: insight ? '12px' : 0 }}>
        {horizons.map((h, i) => {
          const pill = PILL_COLORS[h.direction] || PILL_COLORS.neutral;
          return (
            <motion.div
              key={h.key}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.35 + i * 0.08 }}
              data-testid={`structure-${h.key}`}
              style={{
                display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '4px',
                padding: '10px 8px', background: pill.bg, borderRadius: '12px',
              }}
            >
              <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--ma-secondary)', fontFamily: "'JetBrains Mono', monospace" }}>
                {h.label}
              </span>
              <span style={{ fontSize: '12px', fontWeight: 700, color: pill.text, fontFamily: "'Manrope', sans-serif", textTransform: 'capitalize' }}>
                {h.direction}
              </span>
              <span style={{ fontSize: '10px', color: 'var(--ma-muted)', fontFamily: "'JetBrains Mono', monospace" }}>
                {Math.round(h.confidence * 100)}%
              </span>
            </motion.div>
          );
        })}
      </div>

      {insight && (
        <div data-testid="structure-insight" style={{
          fontSize: '12px', color: 'var(--ma-muted)',
          fontFamily: "'Manrope', sans-serif", fontStyle: 'italic', lineHeight: 1.4,
          paddingTop: '10px', borderTop: '1px solid var(--ma-divider, var(--ma-border))',
        }}>
          {insight}
        </div>
      )}
    </motion.div>
  );
}
