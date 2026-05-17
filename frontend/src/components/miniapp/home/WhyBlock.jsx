import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown, ChevronUp } from 'lucide-react';

export function WhyBlock({ reasons }) {
  const [expanded, setExpanded] = useState(false);

  if (!reasons || reasons.length === 0) return null;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: 0.5 }}
      data-testid="why-block"
      style={{
        margin: '10px 16px 0',
        borderRadius: '16px',
        background: 'var(--ma-surface, #18181b)',
        border: '1px solid var(--ma-border, #27272a)',
        overflow: 'hidden',
        position: 'relative',
        zIndex: 1,
      }}
    >
      <button
        onClick={() => setExpanded(prev => !prev)}
        data-testid="why-toggle"
        style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          width: '100%', padding: '16px',
          background: 'transparent', border: 'none', cursor: 'pointer',
          WebkitTapHighlightColor: 'transparent',
          touchAction: 'manipulation',
        }}
      >
        <span style={{
          fontSize: '11px', fontWeight: 700, letterSpacing: '0.12em',
          color: expanded ? 'var(--ma-text, #fafafa)' : 'var(--ma-muted, #52525b)',
          textTransform: 'uppercase', fontFamily: "'Manrope', sans-serif",
          transition: 'color 0.15s',
        }}>
          Why This Decision
        </span>
        {expanded
          ? <ChevronUp size={16} color="var(--ma-secondary, #a1a1aa)" />
          : <ChevronDown size={16} color="var(--ma-muted, #52525b)" />
        }
      </button>

      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: 'easeInOut' }}
            style={{ overflow: 'hidden' }}
          >
            <div style={{ padding: '0 16px 16px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {reasons.map((r, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.06 }}
                  style={{ display: 'flex', alignItems: 'flex-start', gap: '10px' }}
                >
                  <div style={{
                    width: '4px', height: '4px', borderRadius: '50%',
                    background: 'var(--ma-accent, #6366f1)', marginTop: '7px', flexShrink: 0,
                  }} />
                  <span style={{
                    fontSize: '13px', color: 'var(--ma-secondary, #a1a1aa)',
                    fontFamily: "'Manrope', sans-serif", lineHeight: 1.5,
                  }}>
                    {r}
                  </span>
                </motion.div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
