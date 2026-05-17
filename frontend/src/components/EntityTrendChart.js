import React, { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown, Minus, Calendar, Activity } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const EntityTrendChart = ({ entityId, colors }) => {
  const [historyData, setHistoryData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [timeRange, setTimeRange] = useState(30);
  const [hoveredPoint, setHoveredPoint] = useState(null);

  useEffect(() => {
    if (!entityId) return;
    
    const fetchHistory = async () => {
      setLoading(true);
      try {
        const [type, id] = entityId.split(':');
        const res = await fetch(`${API_URL}/api/momentum/entity/${type}/${id}/history?days=${timeRange}`);
        if (res.ok) {
          const data = await res.json();
          setHistoryData(data.history || []);
        }
      } catch (err) {
        console.error('Failed to fetch history:', err);
      } finally {
        setLoading(false);
      }
    };
    
    fetchHistory();
  }, [entityId, timeRange]);

  // Calculate trend
  const calculateTrend = () => {
    if (historyData.length < 2) return { direction: 'neutral', change: 0 };
    const first = historyData[0]?.momentum_score || 0;
    const last = historyData[historyData.length - 1]?.momentum_score || 0;
    const change = last - first;
    const percentChange = first > 0 ? ((change / first) * 100).toFixed(1) : 0;
    
    return {
      direction: change > 0 ? 'up' : change < 0 ? 'down' : 'neutral',
      change: percentChange,
      absolute: change.toFixed(2),
    };
  };

  const trend = calculateTrend();
  
  // Get chart bounds
  const scores = historyData.map(d => d.momentum_score || 0);
  const minScore = Math.min(...scores, 0);
  const maxScore = Math.max(...scores, 100);
  const range = maxScore - minScore || 1;

  // Chart dimensions
  const chartWidth = 280;
  const chartHeight = 80;
  const padding = { top: 10, right: 10, bottom: 20, left: 35 };
  const innerWidth = chartWidth - padding.left - padding.right;
  const innerHeight = chartHeight - padding.top - padding.bottom;

  // Generate path
  const generatePath = () => {
    if (historyData.length < 2) return '';
    
    const points = historyData.map((d, i) => {
      const x = padding.left + (i / (historyData.length - 1)) * innerWidth;
      const y = padding.top + innerHeight - ((d.momentum_score - minScore) / range) * innerHeight;
      return `${x},${y}`;
    });
    
    return `M${points.join(' L')}`;
  };

  // Generate area path (for gradient fill)
  const generateArea = () => {
    if (historyData.length < 2) return '';
    
    const points = historyData.map((d, i) => {
      const x = padding.left + (i / (historyData.length - 1)) * innerWidth;
      const y = padding.top + innerHeight - ((d.momentum_score - minScore) / range) * innerHeight;
      return { x, y };
    });
    
    const startX = points[0].x;
    const endX = points[points.length - 1].x;
    const bottomY = padding.top + innerHeight;
    
    return `M${startX},${bottomY} ${points.map(p => `L${p.x},${p.y}`).join(' ')} L${endX},${bottomY} Z`;
  };

  const TrendIcon = trend.direction === 'up' ? TrendingUp : trend.direction === 'down' ? TrendingDown : Minus;
  const trendColor = trend.direction === 'up' ? '#10b981' : trend.direction === 'down' ? '#ef4444' : '#64748b';

  if (!entityId) {
    return (
      <div className="p-4 text-center text-slate-500 text-sm">
        Select an entity to view trends
      </div>
    );
  }

  return (
    <div className="rounded-xl p-4" style={{ backgroundColor: 'rgba(99, 102, 241, 0.05)', border: '1px solid rgba(99, 102, 241, 0.1)' }}>
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-violet-400" />
          <span className="text-sm font-medium" style={{ color: colors?.text || '#e2e8f0' }}>
            Momentum Trend
          </span>
        </div>
        
        {/* Time range selector */}
        <div className="flex gap-1">
          {[7, 30, 90].map(days => (
            <button
              key={days}
              onClick={() => setTimeRange(days)}
              className="px-2 py-1 text-xs rounded transition-colors"
              style={{
                backgroundColor: timeRange === days ? 'rgba(139, 92, 246, 0.3)' : 'transparent',
                color: timeRange === days ? '#a78bfa' : '#64748b',
                border: timeRange === days ? '1px solid rgba(139, 92, 246, 0.5)' : '1px solid transparent',
              }}
            >
              {days}d
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-6">
          <div className="w-5 h-5 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : historyData.length < 2 ? (
        <div className="flex flex-col items-center justify-center py-6 text-slate-500 text-sm">
          <Calendar className="w-6 h-6 mb-2 opacity-50" />
          <span>Collecting trend data...</span>
        </div>
      ) : (
        <>
          {/* Trend summary */}
          <div className="flex items-center gap-3 mb-3">
            <div className="flex items-center gap-1">
              <TrendIcon className="w-4 h-4" style={{ color: trendColor }} />
              <span className="text-lg font-semibold" style={{ color: trendColor }}>
                {trend.direction === 'up' ? '+' : ''}{trend.change}%
              </span>
            </div>
            <span className="text-xs text-slate-500">
              over {timeRange} days
            </span>
            {historyData.length > 0 && (
              <span className="ml-auto text-sm font-medium" style={{ color: colors?.text || '#e2e8f0' }}>
                {historyData[historyData.length - 1]?.momentum_score?.toFixed(1) || '-'}
              </span>
            )}
          </div>

          {/* Chart */}
          <div className="relative">
            <svg width={chartWidth} height={chartHeight} className="overflow-visible">
              {/* Gradient definition */}
              <defs>
                <linearGradient id="trendGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                  <stop offset="0%" stopColor={trendColor} stopOpacity="0.3" />
                  <stop offset="100%" stopColor={trendColor} stopOpacity="0.05" />
                </linearGradient>
              </defs>
              
              {/* Grid lines */}
              {[0, 0.5, 1].map((ratio, i) => (
                <line
                  key={i}
                  x1={padding.left}
                  y1={padding.top + innerHeight * ratio}
                  x2={chartWidth - padding.right}
                  y2={padding.top + innerHeight * ratio}
                  stroke="rgba(148, 163, 184, 0.1)"
                  strokeDasharray="2,2"
                />
              ))}
              
              {/* Y-axis labels */}
              <text x={padding.left - 5} y={padding.top + 3} fontSize="8" fill="#64748b" textAnchor="end">
                {maxScore.toFixed(0)}
              </text>
              <text x={padding.left - 5} y={padding.top + innerHeight} fontSize="8" fill="#64748b" textAnchor="end">
                {minScore.toFixed(0)}
              </text>
              
              {/* Area fill */}
              <path d={generateArea()} fill="url(#trendGradient)" />
              
              {/* Line */}
              <path
                d={generatePath()}
                fill="none"
                stroke={trendColor}
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              
              {/* Data points */}
              {historyData.map((d, i) => {
                const x = padding.left + (i / (historyData.length - 1)) * innerWidth;
                const y = padding.top + innerHeight - ((d.momentum_score - minScore) / range) * innerHeight;
                const isHovered = hoveredPoint === i;
                
                return (
                  <g key={i}>
                    {/* Invisible larger hit area */}
                    <circle
                      cx={x}
                      cy={y}
                      r={10}
                      fill="transparent"
                      onMouseEnter={() => setHoveredPoint(i)}
                      onMouseLeave={() => setHoveredPoint(null)}
                      style={{ cursor: 'pointer' }}
                    />
                    {/* Visible point */}
                    <circle
                      cx={x}
                      cy={y}
                      r={isHovered ? 4 : 2}
                      fill={isHovered ? '#fff' : trendColor}
                      stroke={trendColor}
                      strokeWidth={isHovered ? 2 : 0}
                    />
                  </g>
                );
              })}
            </svg>
            
            {/* Tooltip */}
            {hoveredPoint !== null && historyData[hoveredPoint] && (
              <div
                className="absolute pointer-events-none"
                style={{
                  left: padding.left + (hoveredPoint / (historyData.length - 1)) * innerWidth,
                  top: -30,
                  transform: 'translateX(-50%)',
                }}
              >
                <div className="bg-slate-800 px-2 py-1 rounded text-xs whitespace-nowrap">
                  <div className="text-white font-medium">
                    {historyData[hoveredPoint].momentum_score?.toFixed(1)}
                  </div>
                  <div className="text-slate-400">
                    {new Date(historyData[hoveredPoint].date).toLocaleDateString()}
                  </div>
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
};

export default EntityTrendChart;

