import { motion } from 'framer-motion';

const SIGNAL_META = {
  exchange: { label: 'Exchange', icon: 'E' },
  onchain: { label: 'OnChain', icon: 'O' },
  sentiment: { label: 'Sentiment', icon: 'S' },
  twitter: { label: 'Twitter', icon: 'T' },
  ml_risk: { label: 'ML Risk', icon: 'R' },
};

export function MiniAppWhy({ data }) {
  const { decision, signals, market } = data;

  const rows = buildSignalRows(signals);
  const totalScore = rows.reduce((sum, r) => sum + r.numericValue, 0);

  const decisionColor =
    decision.action === 'BUY' ? '#00FF66' :
    decision.action === 'SELL' ? '#FF3333' : '#FFCC00';

  return (
    <div data-testid="miniapp-why-screen" style={{ paddingTop: '4px' }}>
      {/* Header */}
      <div style={{ marginBottom: '24px' }}>
        <h2
          style={{
            fontSize: '13px',
            letterSpacing: '0.2em',
            color: '#555',
            fontWeight: 600,
            textTransform: 'uppercase',
            marginBottom: '4px',
            fontFamily: "'Manrope', sans-serif",
          }}
        >
          Decision Breakdown
        </h2>
        <div
          style={{
            fontSize: '11px',
            color: '#444',
            fontFamily: "'JetBrains Mono', monospace",
          }}
        >
          {market.horizon} horizon
        </div>
      </div>

      {/* Signal rows */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
        {rows.map((row, i) => (
          <motion.div
            key={row.key}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.08 }}
          >
            <SignalRow label={row.label} displayValue={row.displayValue} numericValue={row.numericValue} icon={row.icon} />
          </motion.div>
        ))}
      </div>

      {/* Divider */}
      <div style={{ height: '1px', background: 'rgba(255,255,255,0.06)', margin: '20px 0' }} />

      {/* Total */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.5 }}
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'baseline',
        }}
        data-testid="total-score"
      >
        <span
          style={{
            fontSize: '13px',
            letterSpacing: '0.15em',
            color: '#888',
            fontWeight: 600,
            textTransform: 'uppercase',
            fontFamily: "'Manrope', sans-serif",
          }}
        >
          Total Score
        </span>
        <span
          style={{
            fontSize: '28px',
            fontFamily: "'JetBrains Mono', monospace",
            fontWeight: 700,
            color: totalScore > 0 ? '#00FF66' : totalScore < 0 ? '#FF3333' : '#FFCC00',
          }}
        >
          {totalScore > 0 ? '+' : ''}{totalScore.toFixed(1)}
        </span>
      </motion.div>

      {/* Verdict */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.6 }}
        data-testid="verdict"
        style={{
          marginTop: '16px',
          padding: '16px',
          borderRadius: '12px',
          background: decision.action === 'BUY' ? 'rgba(0,255,102,0.06)' :
                      decision.action === 'SELL' ? 'rgba(255,51,51,0.06)' : 'rgba(255,204,0,0.06)',
          border: `1px solid ${decisionColor}22`,
          textAlign: 'center',
        }}
      >
        <span
          style={{
            fontSize: '22px',
            fontFamily: "'Oswald', sans-serif",
            fontWeight: 700,
            color: decisionColor,
            letterSpacing: '0.1em',
            textTransform: 'uppercase',
          }}
        >
          {decision.strength === 'EXTREME' ? 'EXTREME ' : decision.strength === 'HIGH_CONVICTION' ? 'HIGH CONVICTION ' : ''}
          {decision.action}
        </span>
      </motion.div>
    </div>
  );
}


function SignalRow({ label, displayValue, numericValue, icon }) {
  const isPositive = numericValue > 0.05;
  const isNegative = numericValue < -0.05;
  const color = isPositive ? '#00FF66' : isNegative ? '#FF3333' : '#888';

  const barWidth = Math.min(Math.abs(numericValue) * 15, 100);

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        padding: '14px 0',
        borderBottom: '1px solid rgba(255,255,255,0.04)',
      }}
    >
      {/* Icon */}
      <div
        style={{
          width: '28px',
          height: '28px',
          borderRadius: '6px',
          background: 'rgba(255,255,255,0.05)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: '12px',
          fontFamily: "'JetBrains Mono', monospace",
          fontWeight: 700,
          color: '#555',
          flexShrink: 0,
        }}
      >
        {icon}
      </div>

      {/* Label + value row */}
      <div style={{ flex: 1, marginLeft: '12px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
          <span style={{ fontSize: '14px', color: '#ccc', fontFamily: "'Manrope', sans-serif", fontWeight: 500 }}>
            {label}
          </span>
          <span style={{ fontSize: '13px', fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, color }}>
            {displayValue}
          </span>
        </div>
        {/* Bar */}
        <div style={{ marginTop: '6px', height: '2px', background: 'rgba(255,255,255,0.04)', borderRadius: '1px', overflow: 'hidden' }}>
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${barWidth}%` }}
            transition={{ duration: 0.5, ease: 'easeOut' }}
            style={{ height: '100%', background: color, borderRadius: '1px' }}
          />
        </div>
      </div>
    </div>
  );
}


function buildSignalRows(signals) {
  const rows = [];

  // Exchange
  const ex = signals.exchange;
  const exScore = ex.direction === 'bullish' ? ex.strength : ex.direction === 'bearish' ? -ex.strength : 0;
  rows.push({
    key: 'exchange',
    label: 'Exchange',
    icon: 'E',
    displayValue: `${ex.direction} (${exScore >= 0 ? '+' : ''}${(exScore * 10).toFixed(1)})`,
    numericValue: exScore * 10,
  });

  // OnChain
  const oc = signals.onchain;
  const ocScore = oc.whale_flow === 'outflow' ? oc.strength : oc.whale_flow === 'inflow' ? -oc.strength : 0;
  rows.push({
    key: 'onchain',
    label: 'OnChain',
    icon: 'O',
    displayValue: `${oc.whale_flow} (${ocScore >= 0 ? '+' : ''}${(ocScore * 10).toFixed(1)})`,
    numericValue: ocScore * 10,
  });

  // Sentiment
  const se = signals.sentiment;
  const seScore = se.delta * 10;
  rows.push({
    key: 'sentiment',
    label: 'Sentiment',
    icon: 'S',
    displayValue: `${se.trend} (${seScore >= 0 ? '+' : ''}${seScore.toFixed(1)})`,
    numericValue: seScore,
  });

  // Twitter
  const tw = signals.twitter;
  rows.push({
    key: 'twitter',
    label: 'Twitter',
    icon: 'T',
    displayValue: tw.narrative,
    numericValue: 0,
  });

  // ML Risk
  const ml = signals.ml_risk;
  const mlDisplay = ml.level.toUpperCase();
  rows.push({
    key: 'ml_risk',
    label: 'ML Risk',
    icon: 'R',
    displayValue: mlDisplay,
    numericValue: ml.level === 'high' ? -3 : ml.level === 'medium' ? -1 : 0,
  });

  return rows;
}
