import { motion } from 'framer-motion';
import { AlertTriangle, TrendingDown, TrendingUp, Activity } from 'lucide-react';

const IMPACT_COLORS = {
  bullish: '#00FF66',
  bearish: '#FF3333',
  neutral: '#FFCC00',
};

const TYPE_ICONS = {
  whale: 'W',
  sentiment: 'S',
  exchange: 'E',
  risk: 'R',
  system: 'A',
  other: '?',
};

export function MiniAppSignals({ data }) {
  const { alerts } = data;
  const hasAlerts = alerts && alerts.length > 0;

  return (
    <div data-testid="miniapp-signals-screen" style={{ paddingTop: '4px' }}>
      {/* Header */}
      <div style={{ marginBottom: '20px' }}>
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
          Latest Signals
        </h2>
      </div>

      {hasAlerts ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          {alerts.map((alert, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, x: -15 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.06 }}
            >
              <AlertRow alert={alert} />
            </motion.div>
          ))}

          {/* Impact summary */}
          <ImpactSummary alerts={alerts} />
        </div>
      ) : (
        <EmptySignals />
      )}
    </div>
  );
}


function AlertRow({ alert }) {
  const impactColor = IMPACT_COLORS[alert.impact] || '#888';
  const iconLetter = TYPE_ICONS[alert.type] || '?';
  const ts = formatTimestamp(alert.timestamp);

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: '12px',
        padding: '14px 0',
        borderBottom: '1px solid rgba(255,255,255,0.04)',
      }}
    >
      {/* Type icon */}
      <div
        style={{
          width: '32px',
          height: '32px',
          borderRadius: '8px',
          background: `${impactColor}10`,
          border: `1px solid ${impactColor}20`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: '13px',
          fontFamily: "'JetBrains Mono', monospace",
          fontWeight: 700,
          color: impactColor,
          flexShrink: 0,
        }}
      >
        {iconLetter}
      </div>

      {/* Content */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontSize: '14px',
            color: '#ccc',
            fontFamily: "'Manrope', sans-serif",
            fontWeight: 500,
            lineHeight: 1.4,
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
        >
          {alert.message}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '4px' }}>
          <span
            style={{
              fontSize: '11px',
              color: impactColor,
              fontFamily: "'JetBrains Mono', monospace",
              fontWeight: 600,
              textTransform: 'uppercase',
            }}
          >
            {alert.impact}
          </span>
          <span style={{ fontSize: '11px', color: '#444', fontFamily: "'JetBrains Mono', monospace" }}>
            {ts}
          </span>
        </div>
      </div>
    </div>
  );
}


function ImpactSummary({ alerts }) {
  const bullish = alerts.filter(a => a.impact === 'bullish').length;
  const bearish = alerts.filter(a => a.impact === 'bearish').length;
  const dominant = bullish > bearish ? 'bullish' : bearish > bullish ? 'bearish' : 'mixed';
  const dominantColor = dominant === 'bullish' ? '#00FF66' : dominant === 'bearish' ? '#FF3333' : '#FFCC00';

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: 0.5 }}
      data-testid="impact-summary"
      style={{
        marginTop: '16px',
        padding: '16px',
        borderRadius: '12px',
        background: `${dominantColor}08`,
        border: `1px solid ${dominantColor}15`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '8px',
      }}
    >
      {dominant === 'bullish' ? <TrendingUp size={16} color={dominantColor} /> :
       dominant === 'bearish' ? <TrendingDown size={16} color={dominantColor} /> :
       <Activity size={16} color={dominantColor} />}
      <span style={{ fontSize: '13px', color: dominantColor, fontWeight: 600, fontFamily: "'Manrope', sans-serif", textTransform: 'uppercase', letterSpacing: '0.1em' }}>
        {dominant} pressure
      </span>
    </motion.div>
  );
}


function EmptySignals() {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      data-testid="signals-empty"
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '48px 24px',
        textAlign: 'center',
      }}
    >
      <AlertTriangle size={24} color="#444" style={{ marginBottom: '12px' }} />
      <span style={{ fontSize: '14px', color: '#888', fontFamily: "'Manrope', sans-serif" }}>
        No recent signals
      </span>
      <span style={{ fontSize: '12px', color: '#555', fontFamily: "'Manrope', sans-serif", marginTop: '4px' }}>
        Alerts will appear here when triggered
      </span>
    </motion.div>
  );
}


function formatTimestamp(ts) {
  if (!ts) return '';
  try {
    const date = new Date(ts);
    const now = new Date();
    const diffMs = now - date;
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 1) return 'now';
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffH = Math.floor(diffMin / 60);
    if (diffH < 24) return `${diffH}h ago`;
    const diffD = Math.floor(diffH / 24);
    return `${diffD}d ago`;
  } catch {
    return '';
  }
}
