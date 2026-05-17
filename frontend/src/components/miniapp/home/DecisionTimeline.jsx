import { motion } from 'framer-motion';

const DECISION_COLORS = {
  BUY: '#34d399',
  SELL: '#f87171',
  WAIT: '#facc15',
};

export function DecisionTimeline({ timeline }) {
  if (!timeline || timeline.length < 2) return null;

  const prev = timeline[0];
  const curr = timeline[timeline.length - 1];
  const changed = prev.decision !== curr.decision;

  if (!changed) return null;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: 0.55 }}
      data-testid="decision-timeline"
      style={{
        margin: '10px 16px 0',
        padding: '12px 16px',
        background: 'var(--ma-surface)',
        borderRadius: '16px',
        border: '1px solid var(--ma-border)',
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
      }}
    >
      <span style={{
        fontSize: '10px', fontWeight: 700, letterSpacing: '0.15em',
        color: 'var(--ma-muted)', textTransform: 'uppercase', fontFamily: "'Manrope', sans-serif",
        flexShrink: 0,
      }}>
        Changed
      </span>

      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
        <span style={{
          fontSize: '12px', fontWeight: 700,
          color: DECISION_COLORS[prev.decision] || '#a1a1aa',
          fontFamily: "'JetBrains Mono', monospace",
        }}>
          {prev.decision}
        </span>
        <span style={{ fontSize: '10px', color: 'var(--ma-muted)', fontFamily: "'JetBrains Mono', monospace" }}>
          {prev.time}
        </span>
      </div>

      <span style={{ color: 'var(--ma-muted)', fontSize: '14px' }}>&rarr;</span>

      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
        <span style={{
          fontSize: '12px', fontWeight: 700,
          color: DECISION_COLORS[curr.decision] || '#a1a1aa',
          fontFamily: "'JetBrains Mono', monospace",
        }}>
          {curr.decision}
        </span>
        <span style={{ fontSize: '10px', color: 'var(--ma-muted)', fontFamily: "'JetBrains Mono', monospace" }}>
          {curr.time}
        </span>
      </div>
    </motion.div>
  );
}
