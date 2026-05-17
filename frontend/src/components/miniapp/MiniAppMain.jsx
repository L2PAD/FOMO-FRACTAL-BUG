import { motion } from 'framer-motion';
import { Activity, ChevronRight } from 'lucide-react';

const DECISION_COLORS = {
  BUY: '#00FF66',
  SELL: '#FF3333',
  WAIT: '#FFCC00',
  AVOID: '#FF3333',
};

const DECISION_BG = {
  BUY: 'rgba(0, 255, 102, 0.06)',
  SELL: 'rgba(255, 51, 51, 0.06)',
  WAIT: 'rgba(255, 204, 0, 0.06)',
  AVOID: 'rgba(255, 51, 51, 0.06)',
};

export function MiniAppMain({ data, onWhy, onEdge, onSignals }) {
  const { decision, market, signals } = data;
  const color = DECISION_COLORS[decision.action] || '#888';
  const bgGlow = DECISION_BG[decision.action] || 'transparent';

  return (
    <div
      data-testid="miniapp-main-screen"
      style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        padding: '0 20px 16px',
      }}
    >
      {/* Decision area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', position: 'relative' }}>
        {/* Glow effect */}
        <div
          style={{
            position: 'absolute',
            width: '300px',
            height: '300px',
            borderRadius: '50%',
            background: `radial-gradient(circle, ${bgGlow} 0%, transparent 70%)`,
            filter: 'blur(40px)',
            pointerEvents: 'none',
          }}
        />

        {/* Strength label */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          data-testid="decision-strength"
          style={{
            fontSize: '11px',
            letterSpacing: '0.2em',
            color: color,
            opacity: 0.7,
            fontWeight: 600,
            textTransform: 'uppercase',
            marginBottom: '8px',
            fontFamily: "'Manrope', sans-serif",
          }}
        >
          {decision.strength.replace('_', ' ')}
        </motion.div>

        {/* Main decision word */}
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ type: 'spring', stiffness: 300, damping: 25 }}
          data-testid="decision-action"
          style={{
            fontSize: 'min(25vw, 96px)',
            fontFamily: "'Oswald', sans-serif",
            fontWeight: 700,
            color: color,
            lineHeight: 1,
            letterSpacing: '-0.02em',
            textTransform: 'uppercase',
            textAlign: 'center',
          }}
        >
          {decision.action}
        </motion.div>

        {/* Confidence bar */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2 }}
          style={{ width: '100%', maxWidth: '200px', marginTop: '16px' }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
            <span style={{ fontSize: '11px', color: '#555', letterSpacing: '0.15em', fontWeight: 500, textTransform: 'uppercase' }}>
              Confidence
            </span>
            <span
              data-testid="decision-confidence"
              style={{ fontSize: '13px', color: color, fontFamily: "'JetBrains Mono', monospace", fontWeight: 700 }}
            >
              {decision.confidence}%
            </span>
          </div>
          <div style={{ width: '100%', height: '3px', background: 'rgba(255,255,255,0.06)', borderRadius: '2px', overflow: 'hidden' }}>
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${decision.confidence}%` }}
              transition={{ duration: 0.8, ease: 'easeOut', delay: 0.3 }}
              style={{ height: '100%', background: color, borderRadius: '2px' }}
            />
          </div>
        </motion.div>

        {/* Price */}
        {market.current_price > 0 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.35 }}
            data-testid="current-price"
            style={{
              marginTop: '20px',
              fontSize: '22px',
              fontFamily: "'JetBrains Mono', monospace",
              fontWeight: 700,
              color: '#fff',
              letterSpacing: '-0.01em',
            }}
          >
            ${market.current_price.toLocaleString()}
          </motion.div>
        )}

        {/* Story */}
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.4 }}
          data-testid="market-story"
          style={{
            marginTop: '12px',
            fontSize: '14px',
            color: '#888',
            textAlign: 'center',
            lineHeight: 1.5,
            maxWidth: '320px',
            fontFamily: "'Manrope', sans-serif",
          }}
        >
          {market.story}
        </motion.p>

        {/* Range */}
        {market.scenario.range_low > 0 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.5 }}
            data-testid="price-range"
            style={{
              marginTop: '10px',
              fontSize: '12px',
              fontFamily: "'JetBrains Mono', monospace",
              color: '#555',
            }}
          >
            {market.horizon} Range: ${market.scenario.range_low.toLocaleString()} — ${market.scenario.range_high.toLocaleString()}
          </motion.div>
        )}
      </div>

      {/* Quick signals strip */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.55 }}
        style={{
          display: 'flex',
          gap: '8px',
          marginBottom: '12px',
          overflowX: 'auto',
          paddingBottom: '4px',
        }}
        data-testid="quick-signals"
      >
        <SignalChip label="Exchange" value={signals.exchange.direction} />
        <SignalChip label="Sentiment" value={signals.sentiment.trend} />
        <SignalChip label="Risk" value={signals.ml_risk.level} />
      </motion.div>

      {/* Action buttons */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.6 }}
        style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}
      >
        <ActionButton label="WHY" testId="btn-why" onClick={onWhy} />
        <ActionButton label="EDGE" testId="btn-edge" onClick={onEdge} />
      </motion.div>

      {/* Signals feed link */}
      <motion.button
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.7 }}
        onClick={onSignals}
        data-testid="btn-signals"
        whileTap={{ scale: 0.97 }}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '8px',
          marginTop: '8px',
          padding: '12px',
          background: 'transparent',
          border: '1px solid rgba(255,255,255,0.06)',
          borderRadius: '10px',
          color: '#888',
          cursor: 'pointer',
          fontFamily: "'Manrope', sans-serif",
          fontSize: '13px',
          fontWeight: 500,
          letterSpacing: '0.08em',
          textTransform: 'uppercase',
        }}
      >
        <Activity size={14} />
        Latest Signals
        <ChevronRight size={14} />
      </motion.button>
    </div>
  );
}


function SignalChip({ label, value }) {
  const isPositive = ['bullish', 'positive', 'low', 'outflow'].includes(value);
  const isNegative = ['bearish', 'negative', 'high', 'inflow'].includes(value);
  const chipColor = isPositive ? '#00FF66' : isNegative ? '#FF3333' : '#FFCC00';

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        padding: '6px 10px',
        borderRadius: '6px',
        background: 'rgba(255,255,255,0.04)',
        whiteSpace: 'nowrap',
        flexShrink: 0,
      }}
    >
      <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: chipColor }} />
      <span style={{ fontSize: '11px', color: '#888', fontFamily: "'Manrope', sans-serif" }}>{label}</span>
      <span style={{ fontSize: '11px', color: chipColor, fontWeight: 600, fontFamily: "'JetBrains Mono', monospace", textTransform: 'uppercase' }}>
        {value}
      </span>
    </div>
  );
}


function ActionButton({ label, testId, onClick }) {
  return (
    <motion.button
      whileTap={{ scale: 0.95, opacity: 0.8 }}
      onClick={onClick}
      data-testid={testId}
      style={{
        padding: '18px 0',
        background: 'rgba(255,255,255,0.06)',
        border: '1px solid rgba(255,255,255,0.08)',
        borderRadius: '12px',
        color: '#fff',
        fontFamily: "'Oswald', sans-serif",
        fontSize: '18px',
        fontWeight: 600,
        letterSpacing: '0.2em',
        textTransform: 'uppercase',
        cursor: 'pointer',
      }}
    >
      {label}
    </motion.button>
  );
}
