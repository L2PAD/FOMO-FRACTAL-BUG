/**
 * Momentum Sparkline (M-3 UI)
 * Simple SVG sparkline for momentum history
 */
export default function MomentumSparkline({ points, metric = 'momentumScore' }) {
  const xs = (points || [])
    .map(p => (typeof p[metric] === 'number' ? p[metric] : null))
    .filter(v => v !== null);

  if (xs.length < 2) return <div className="text-gray-400 text-sm">Not enough data</div>;

  const w = 280;
  const h = 60;

  const min = Math.min(...xs);
  const max = Math.max(...xs);
  const span = Math.max(0.1, max - min);

  const step = w / (xs.length - 1);

  const path = xs
    .map((v, i) => {
      const x = i * step;
      const y = h - 4 - ((v - min) / span) * (h - 8);
      return `${i === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(' ');

  // Determine trend color
  const lastVal = xs[xs.length - 1];
  const firstVal = xs[0];
  const trending = lastVal > firstVal ? 'up' : lastVal < firstVal ? 'down' : 'flat';
  const strokeColor = trending === 'up' ? '#10b981' : trending === 'down' ? '#ef4444' : '#6b7280';

  return (
    <div data-testid="momentum-sparkline">
      <svg width={w} height={h} className="block">
        <path
          d={path}
          fill="none"
          stroke={strokeColor}
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <div className="flex justify-between text-xs text-gray-500 mt-1">
        <span>{xs[0]?.toFixed(1)}</span>
        <span>{xs[xs.length - 1]?.toFixed(1)}</span>
      </div>
    </div>
  );
}
