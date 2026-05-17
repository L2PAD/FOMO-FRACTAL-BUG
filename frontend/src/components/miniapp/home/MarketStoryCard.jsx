import { motion } from 'framer-motion';

const REGIME_COLORS = {
  TRENDING: '#4ade80',
  UNCERTAIN: '#facc15',
  TRANSITIONING: '#a1a1aa',
};

export function MarketStoryCard({ marketStory }) {
  if (!marketStory) return null;
  const regimeColor = REGIME_COLORS[marketStory.regime] || '#a1a1aa';

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: 0.2 }}
      data-testid="market-story-card"
      style={{
        margin: '10px 16px 0',
        padding: '14px 16px',
        background: 'var(--ma-surface)',
        borderRadius: '16px',
        border: '1px solid var(--ma-border)',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
        <span style={{
          fontSize: '10px', fontWeight: 700, letterSpacing: '0.15em',
          color: 'var(--ma-muted)', textTransform: 'uppercase', fontFamily: "'Manrope', sans-serif",
        }}>
          Market Story
        </span>
        <span
          data-testid="story-regime"
          style={{
            fontSize: '9px', fontWeight: 700, letterSpacing: '0.1em',
            color: regimeColor, textTransform: 'uppercase', fontFamily: "'JetBrains Mono', monospace",
            background: `${regimeColor}15`, padding: '2px 8px', borderRadius: '20px',
          }}
        >
          {marketStory.regime}
        </span>
      </div>
      <div data-testid="story-text" style={{
        fontSize: '14px', color: 'var(--ma-secondary)',
        fontFamily: "'Manrope', sans-serif", fontWeight: 500, lineHeight: 1.55,
      }}>
        {marketStory.text}
      </div>
    </motion.div>
  );
}
