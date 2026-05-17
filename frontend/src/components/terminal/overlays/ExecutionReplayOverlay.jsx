import { useMemo } from "react";

export default function ExecutionReplayOverlay({ fills, chart }) {
  // Hooks must be called unconditionally
  const points = useMemo(() => {
    if (!fills || !chart) return [];
    
    const priceToY = (price) => {
      try {
        const priceScale = chart.priceScale('right');
        return priceScale.priceToCoordinate(price);
      } catch (e) {
        return 0;
      }
    };

    const timeToX = (time) => {
      try {
        return chart.timeScale().timeToCoordinate(time);
      } catch (e) {
        return 0;
      }
    };
    
    return fills.map(fill => ({
      x: timeToX(fill.time),
      y: priceToY(fill.price),
      fill
    }));
  }, [fills, chart]);

  // Early return after hooks
  if (!fills?.length || !chart || points.length === 0) return null;

  return (
    <div className="absolute inset-0 pointer-events-none" style={{ zIndex: 50 }}>
      {/* Fill dots */}
      {points.map((p, i) => {
        const slippage = p.fill.slippage_bps || 0;
        const color = slippage < 5 ? '#00C853' : slippage < 15 ? '#FFA726' : '#FF4D4F';

        return (
          <div
            key={i}
            style={{
              position: 'absolute',
              left: `${p.x - 4}px`,
              top: `${p.y - 4}px`,
              width: 8,
              height: 8,
              borderRadius: '50%',
              background: color,
              border: '2px solid white',
              boxShadow: '0 2px 4px rgba(0,0,0,0.2)',
            }}
            title={`${p.fill.side} ${p.fill.price} • Slippage: ${slippage}bps • Latency: ${p.fill.latency_ms || 0}ms`}
          />
        );
      })}

      {/* Connection line between fills (if multiple) */}
      {points.length > 1 && (
        <svg className="absolute inset-0" style={{ pointerEvents: 'none' }}>
          <polyline
            points={points.map(p => `${p.x},${p.y}`).join(" ")}
            fill="none"
            stroke="#999"
            strokeWidth="1.5"
            strokeDasharray="4 4"
            opacity="0.6"
          />
        </svg>
      )}
    </div>
  );
}
