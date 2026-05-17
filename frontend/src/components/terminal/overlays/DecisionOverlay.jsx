export default function DecisionOverlay({ decision, chart }) {
  if (!decision || !chart) return null;

  const { entry, stop, target, side, strategy, confidence, reason, meta } = decision;

  // Calculate Y coordinate for entry price
  const priceToY = (price) => {
    try {
      const priceScale = chart.priceScale('right');
      return priceScale.priceToCoordinate(price);
    } catch (e) {
      return 100; // fallback
    }
  };

  const y = priceToY(entry);
  const rr = ((target - entry) / Math.abs(entry - stop)).toFixed(2);

  return (
    <div
      style={{
        position: 'absolute',
        top: `${y - 100}px`,
        left: '65%',
        background: '#111',
        color: '#fff',
        padding: '12px 14px',
        borderRadius: 8,
        fontSize: 12,
        width: 220,
        pointerEvents: 'auto',
        cursor: 'pointer',
        boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
        zIndex: 100,
      }}
    >
      {/* Header */}
      <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 6, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ color: side === 'LONG' || side === 'BUY' ? '#00C853' : '#FF4D4F' }}>
          {side || 'LONG'}
        </span>
        <span style={{ fontSize: 11, opacity: 0.7 }}>{strategy || 'breakout_v1'}</span>
      </div>

      {/* Reason */}
      <div style={{ opacity: 0.8, marginBottom: 8, fontSize: 11, color: '#ccc' }}>
        {reason || 'Breakout confirmed above resistance'}
      </div>

      {/* Levels */}
      <div style={{ marginBottom: 8, fontSize: 11, lineHeight: 1.6 }}>
        <div>Entry: <span style={{ fontFamily: 'monospace', color: '#2962FF' }}>{entry.toFixed(2)}</span></div>
        <div>Stop: <span style={{ fontFamily: 'monospace', color: '#FF4D4F' }}>{stop.toFixed(2)}</span></div>
        <div>Target: <span style={{ fontFamily: 'monospace', color: '#00C853' }}>{target.toFixed(2)}</span></div>
      </div>

      {/* Metrics */}
      <div style={{ marginBottom: 8, fontSize: 11, lineHeight: 1.6, borderTop: '1px solid rgba(255,255,255,0.15)', paddingTop: 6 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span>RR:</span>
          <span style={{ fontFamily: 'monospace', color: '#00C853', fontWeight: 600 }}>{rr}</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span>Conf:</span>
          <span style={{ fontFamily: 'monospace', color: confidence > 0.7 ? '#00C853' : '#FFA726' }}>
            {((confidence || 0.68) * 100).toFixed(0)}%
          </span>
        </div>
      </div>

      {/* Signals Breakdown (if available) */}
      {meta?.signals && (
        <div style={{ fontSize: 10, opacity: 0.7, borderTop: '1px solid rgba(255,255,255,0.15)', paddingTop: 6 }}>
          {meta.signals.slice(0, 3).map((s, i) => (
            <div key={i} style={{ marginBottom: 2 }}>
              • {s}
            </div>
          ))}
        </div>
      )}

      {/* Arrow pointer to entry line */}
      <div
        style={{
          position: 'absolute',
          bottom: -6,
          left: 20,
          width: 0,
          height: 0,
          borderLeft: '6px solid transparent',
          borderRight: '6px solid transparent',
          borderTop: '6px solid #111',
        }}
      />
    </div>
  );
}
