/**
 * Cosmic Radar — Alpha Detection Engine
 * 
 * Layout:
 * [ Insight Banner ]
 * [ CosmicRadar SVG  |  Ranked Actor List ]
 * [ Filters: min quality / min velocity ]
 */
import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { RefreshCw, ExternalLink, Zap, TrendingUp, AlertTriangle, ArrowRight } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';

const ZONE_COLORS = {
  alpha: { bg: 'rgba(34,197,94,0.06)', label: 'ALPHA', text: '#16a34a' },
  opportunity: { bg: 'rgba(234,179,8,0.06)', label: 'OPPORTUNITY', text: '#ca8a04' },
  stable: { bg: 'rgba(59,130,246,0.06)', label: 'STABLE', text: '#2563eb' },
  noise: { bg: 'rgba(107,114,128,0.06)', label: 'NOISE', text: '#6b7280' },
};
const SIGNAL_COLORS = {
  breakout: '#22c55e',
  early: '#eab308',
  stable: '#3b82f6',
  noise: '#6b7280',
};

// ─── INSIGHT BANNER ────────────────────────────────
const InsightBanner = ({ insights }) => {
  if (!insights || insights.length === 0) return null;
  const icons = { alpha_cluster: Zap, momentum_surge: TrendingUp, early_trend: AlertTriangle };
  return (
    <div className="flex items-center gap-4 mb-3 px-4 py-2.5 bg-gray-900 text-white rounded-lg" data-testid="insight-banner">
      {insights.map((ins, i) => {
        const Icon = icons[ins.type] || Zap;
        return (
          <div key={i} className="flex items-center gap-2 text-sm">
            <Icon className="w-4 h-4 text-yellow-400 flex-shrink-0" />
            <span className="font-medium">{ins.text}</span>
          </div>
        );
      })}
    </div>
  );
};

// ─── RADAR TOOLTIP ────────────────────────────────
const RadarTooltip = ({ actor, coords }) => {
  if (!actor || !coords) return null;
  const zone = actor.zone?.toUpperCase() || 'NOISE';
  const zoneColor = ZONE_COLORS[actor.zone]?.text || '#6b7280';
  return createPortal(
    <div
      className="fixed z-[99999] pointer-events-none bg-gray-900 text-white rounded-lg px-3 py-2.5 text-xs shadow-2xl"
      style={{ top: coords.y - 10, left: coords.x + 15, maxWidth: 220 }}
      data-testid="radar-tooltip"
    >
      <div className="font-bold text-sm mb-1">@{actor.username}</div>
      <div className="space-y-0.5 text-gray-300">
        <div className="flex justify-between gap-4"><span>Velocity</span><span className={`font-medium ${actor.velocity_norm > 0 ? 'text-green-400' : 'text-red-400'}`}>{actor.velocity_norm > 0 ? '+' : ''}{(actor.velocity_norm * 100).toFixed(0)}%</span></div>
        <div className="flex justify-between gap-4"><span>Quality</span><span className="font-medium text-white">{actor.quality.toFixed(2)}</span></div>
        <div className="flex justify-between gap-4"><span>Winrate</span><span className="font-medium text-white">{(actor.winrate * 100).toFixed(0)}%</span></div>
        <div className="flex justify-between gap-4"><span>Score</span><span className="font-medium text-white">{actor.radar_score.toFixed(2)}</span></div>
      </div>
      <div className="mt-1.5 pt-1.5 border-t border-gray-700">
        <span className="font-semibold" style={{ color: zoneColor }}>{zone}</span>
        {actor.history_confidence === 'none' && <span className="text-gray-500 ml-2">· no history</span>}
      </div>
    </div>,
    document.body
  );
};

// ─── COSMIC RADAR SVG ─────────────────────────────
const CosmicRadarChart = ({ actors, selectedId, onSelect, onHover, hoveredId }) => {
  const svgRef = useRef(null);
  const W = 700, H = 460, P = 50;
  const plotW = W - 2 * P, plotH = H - 2 * P;

  const velThreshold = 0.3;
  const qualThreshold = 0.6;

  const toX = (vel) => P + ((vel + 1) / 2) * plotW;
  const toY = (qual) => P + (1 - qual) * plotH;

  // Deterministic jitter based on username hash (stable across renders)
  const jitter = (handle, axis) => {
    let h = 0;
    for (let i = 0; i < handle.length; i++) h = ((h << 5) - h + handle.charCodeAt(i) + (axis === 'y' ? 7 : 0)) | 0;
    return ((h % 1000) / 1000 - 0.5) * 0.06;
  };

  const zoneX = toX(velThreshold);
  const zoneY = toY(qualThreshold);

  return (
    <svg
      ref={svgRef}
      viewBox={`0 0 ${W} ${H}`}
      className="w-full h-full"
      data-testid="cosmic-radar-svg"
    >
      <defs>
        <filter id="glow">
          <feGaussianBlur stdDeviation="4" result="coloredBlur" />
          <feMerge><feMergeNode in="coloredBlur" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
        <linearGradient id="trailFade" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="white" stopOpacity="0.1" />
          <stop offset="100%" stopColor="white" stopOpacity="0.6" />
        </linearGradient>
      </defs>

      {/* Background */}
      <rect x={0} y={0} width={W} height={H} fill="#fafafa" rx={8} />

      {/* Zone backgrounds */}
      <rect x={zoneX} y={P} width={W - P - zoneX} height={zoneY - P} fill={ZONE_COLORS.alpha.bg} />
      <rect x={zoneX} y={zoneY} width={W - P - zoneX} height={H - P - zoneY} fill={ZONE_COLORS.opportunity.bg} />
      <rect x={P} y={P} width={zoneX - P} height={zoneY - P} fill={ZONE_COLORS.stable.bg} />
      <rect x={P} y={zoneY} width={zoneX - P} height={H - P - zoneY} fill={ZONE_COLORS.noise.bg} />

      {/* Zone labels */}
      <text x={W - P - 8} y={P + 18} textAnchor="end" fill={ZONE_COLORS.alpha.text} fontSize={10} fontWeight={700} opacity={0.6}>ALPHA</text>
      <text x={W - P - 8} y={H - P - 8} textAnchor="end" fill={ZONE_COLORS.opportunity.text} fontSize={10} fontWeight={700} opacity={0.6}>OPPORTUNITY</text>
      <text x={P + 8} y={P + 18} fill={ZONE_COLORS.stable.text} fontSize={10} fontWeight={700} opacity={0.6}>STABLE</text>
      <text x={P + 8} y={H - P - 8} fill={ZONE_COLORS.noise.text} fontSize={10} fontWeight={700} opacity={0.6}>NOISE</text>

      {/* Grid lines */}
      <line x1={zoneX} y1={P} x2={zoneX} y2={H - P} stroke="#e5e7eb" strokeWidth={1} strokeDasharray="4,4" />
      <line x1={P} y1={zoneY} x2={W - P} y2={zoneY} stroke="#e5e7eb" strokeWidth={1} strokeDasharray="4,4" />
      <line x1={toX(0)} y1={P} x2={toX(0)} y2={H - P} stroke="#d1d5db" strokeWidth={0.5} strokeDasharray="2,4" />

      {/* Axis labels */}
      <text x={W / 2} y={H - 8} textAnchor="middle" fill="#9ca3af" fontSize={11} fontWeight={500}>
        ← Weak · Velocity · Strong →
      </text>
      <text x={12} y={H / 2} textAnchor="middle" fill="#9ca3af" fontSize={11} fontWeight={500} transform={`rotate(-90, 12, ${H / 2})`}>
        Signal Quality
      </text>

      {/* Trails */}
      {actors.map(a => {
        if (!a.trail || a.trail.length < 2) return null;
        const points = a.trail.map(t => `${toX(t.x)},${toY(t.y)}`).join(' ');
        const c = SIGNAL_COLORS[a.signal_type] || '#6b7280';
        return (
          <polyline
            key={`trail-${a.author_id}`}
            points={points}
            fill="none"
            stroke={c}
            strokeWidth={1.5}
            opacity={0.3}
            strokeLinecap="round"
          />
        );
      })}

      {/* Actor dots */}
      {actors.map(a => {
        const jx = jitter(a.username, 'x');
        const jy = jitter(a.username, 'y');
        const cx = toX(a.velocity_norm + jx);
        const cy = toY(a.quality + jy);
        const r = Math.max(3, Math.min(a.size_norm / 2, 6));
        const c = SIGNAL_COLORS[a.signal_type] || '#6b7280';
        const isSelected = a.author_id === selectedId;
        const isHovered = a.author_id === hoveredId;

        return (
          <g
            key={a.author_id}
            onClick={() => onSelect(a.author_id)}
            onMouseEnter={(e) => onHover(a.author_id, { x: e.clientX, y: e.clientY })}
            onMouseMove={(e) => onHover(a.author_id, { x: e.clientX, y: e.clientY })}
            onMouseLeave={() => onHover(null, null)}
            className="cursor-pointer"
            data-testid={`radar-dot-${a.username}`}
          >
            {isSelected && (
              <>
                <circle cx={cx} cy={cy} r={r + 6} fill="none" stroke={c} strokeWidth={1.5} opacity={0.3}>
                  <animate attributeName="r" values={`${r + 4};${r + 9};${r + 4}`} dur="2s" repeatCount="indefinite" />
                  <animate attributeName="opacity" values="0.3;0.1;0.3" dur="2s" repeatCount="indefinite" />
                </circle>
                <circle cx={cx} cy={cy} r={r + 2} fill={c} opacity={0.12} filter="url(#glow)" />
              </>
            )}
            <circle
              cx={cx} cy={cy} r={isHovered ? r + 1.5 : r}
              fill={c}
              opacity={isSelected ? 1 : isHovered ? 0.85 : 0.6}
              stroke={isSelected ? '#fff' : 'none'}
              strokeWidth={isSelected ? 2 : 0}
            />
            {(isSelected || isHovered) && (
              <text x={cx} y={cy - r - 4} textAnchor="middle" fill="#374151" fontSize={9} fontWeight={700}>
                @{a.username.length > 14 ? a.username.slice(0, 12) + '..' : a.username}
              </text>
            )}
          </g>
        );
      })}

      {/* Border */}
      <rect x={P} y={P} width={plotW} height={plotH} fill="none" stroke="#e5e7eb" strokeWidth={1} rx={4} />
    </svg>
  );
};

// ─── ACTOR LIST ────────────────────────────────────
const ActorList = ({ actors, selectedId, onSelect, onViewProfile }) => {
  return (
    <div className="flex flex-col h-full" data-testid="actor-list">
      <div className="px-3 py-2 flex items-center justify-between text-xs text-gray-400 uppercase tracking-wider">
        <span>Actor</span>
        <span>Zone / Score</span>
      </div>
      <div className="flex-1 overflow-y-auto divide-y divide-gray-100">
        {actors.length === 0 ? (
          <div className="p-6 text-center text-gray-400 text-sm">No actors match filters</div>
        ) : actors.map(a => {
          const isSelected = a.author_id === selectedId;
          const zoneConf = ZONE_COLORS[a.zone] || ZONE_COLORS.noise;
          return (
            <div
              key={a.author_id}
              onClick={() => onSelect(a.author_id)}
              data-testid={`actor-row-${a.username}`}
              className={`flex items-center gap-2 px-3 py-2 cursor-pointer transition-all text-sm ${
                isSelected ? 'bg-gray-900 text-white' : 'hover:bg-gray-50'
              }`}
            >
              <img
                src={a.avatar}
                alt=""
                className="w-7 h-7 rounded-full flex-shrink-0"
                onError={e => { e.target.src = `https://ui-avatars.com/api/?name=${a.username}&size=28&background=random`; }}
              />
              <div className="flex-1 min-w-0">
                <div className={`font-medium truncate ${isSelected ? 'text-white' : 'text-gray-900'}`}>@{a.username}</div>
                <div className={`text-[10px] ${isSelected ? 'text-gray-300' : 'text-gray-400'}`}>
                  {a.velocity_norm > 0 ? '+' : ''}{(a.velocity_norm * 100).toFixed(0)}% vel
                </div>
              </div>
              <div className="text-right flex-shrink-0">
                <div className="text-[10px] font-semibold" style={{ color: isSelected ? '#fff' : zoneConf.text }}>
                  {a.zone.toUpperCase()}
                </div>
                <div className={`text-xs ${isSelected ? 'text-gray-300' : 'text-gray-500'}`}>
                  {a.radar_score.toFixed(2)}
                </div>
              </div>
              <button
                onClick={(e) => { e.stopPropagation(); onViewProfile(a.username); }}
                className={`p-1 rounded transition-colors flex-shrink-0 ${isSelected ? 'text-gray-300 hover:text-white' : 'text-gray-300 hover:text-blue-500'}`}
                title="View Profile"
              >
                <ExternalLink className="w-3.5 h-3.5" />
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
};

// ─── FILTER BAR ────────────────────────────────────
const FilterBar = ({ filters, onChange, zoneCounts }) => {
  return (
    <div className="flex items-center gap-5 text-xs" data-testid="radar-filters">
      <div className="flex items-center gap-2 flex-1">
        <span className="text-gray-400 w-20">Min Quality</span>
        <input
          type="range"
          min={0} max={100} step={5}
          value={Math.round(filters.minQuality * 100)}
          onChange={e => onChange({ ...filters, minQuality: parseInt(e.target.value) / 100 })}
          className="flex-1 h-1 appearance-none bg-gray-200 rounded-full accent-blue-500"
          data-testid="filter-min-quality"
        />
        <span className="text-gray-600 w-8 text-right">{(filters.minQuality * 100).toFixed(0)}%</span>
      </div>
      <div className="flex items-center gap-2 flex-1">
        <span className="text-gray-400 w-20">Min Velocity</span>
        <input
          type="range"
          min={-100} max={100} step={5}
          value={Math.round(filters.minVelocity * 100)}
          onChange={e => onChange({ ...filters, minVelocity: parseInt(e.target.value) / 100 })}
          className="flex-1 h-1 appearance-none bg-gray-200 rounded-full accent-green-500"
          data-testid="filter-min-velocity"
        />
        <span className="text-gray-600 w-8 text-right">{filters.minVelocity > 0 ? '+' : ''}{(filters.minVelocity * 100).toFixed(0)}%</span>
      </div>
      <div className="flex items-center gap-3 text-[10px] text-gray-400">
        {Object.entries(zoneCounts).map(([z, c]) => (
          <span key={z} className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: ZONE_COLORS[z]?.text || '#6b7280' }} />
            {z} {c}
          </span>
        ))}
      </div>
    </div>
  );
};

// ─── MAIN PAGE ─────────────────────────────────────
export default function ConnectionsEarlySignalPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [rawData, setRawData] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [hoveredId, setHoveredId] = useState(null);
  const [tooltipCoords, setTooltipCoords] = useState(null);
  const [filters, setFilters] = useState({ minQuality: 0, minVelocity: -1 });

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/connections/radar/cosmic?limit=100`);
      if (!res.ok) throw new Error('Failed');
      const data = await res.json();
      if (data.ok) setRawData(data.data);
    } catch (err) {
      console.error('Cosmic radar fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const filteredActors = useMemo(() => {
    if (!rawData?.accounts) return [];
    return rawData.accounts.filter(a =>
      a.quality >= filters.minQuality && a.velocity_norm >= filters.minVelocity
    );
  }, [rawData, filters]);

  const zoneCounts = useMemo(() => {
    const counts = { alpha: 0, opportunity: 0, stable: 0, noise: 0 };
    filteredActors.forEach(a => { counts[a.zone] = (counts[a.zone] || 0) + 1; });
    return counts;
  }, [filteredActors]);

  const selectedActor = useMemo(() => {
    return filteredActors.find(a => a.author_id === selectedId);
  }, [filteredActors, selectedId]);

  const hoveredActor = useMemo(() => {
    return filteredActors.find(a => a.author_id === hoveredId);
  }, [filteredActors, hoveredId]);

  const handleHover = useCallback((id, coords) => {
    setHoveredId(id);
    setTooltipCoords(coords);
  }, []);

  const handleViewProfile = useCallback((username) => {
    navigate(`/connections/influencers/${username}`);
  }, [navigate]);

  useEffect(() => {
    if (filteredActors.length > 0 && !selectedId) {
      setSelectedId(filteredActors[0].author_id);
    }
  }, [filteredActors, selectedId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-6 h-6 text-gray-400 animate-spin" />
      </div>
    );
  }

  return (
    <div className="p-4" data-testid="cosmic-radar-page">
      {/* Insight Banner */}
      <InsightBanner insights={rawData?.insights} />

      {/* Main: Radar + Actor List */}
      <div className="flex gap-4 mb-3" style={{ height: 480 }}>
        {/* Radar SVG */}
        <div className="flex-1 min-w-0 bg-white rounded-lg overflow-hidden" data-testid="radar-container">
          <div className="flex items-center justify-between px-3 py-2">
            <span className="text-xs text-gray-400 uppercase tracking-wider font-semibold">Cosmic Radar</span>
            <button onClick={fetchData} disabled={loading} className="p-1 text-gray-400 hover:text-gray-600" data-testid="refresh-radar">
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
          <CosmicRadarChart
            actors={filteredActors}
            selectedId={selectedId}
            hoveredId={hoveredId}
            onSelect={setSelectedId}
            onHover={handleHover}
          />
        </div>

        {/* Actor List */}
        <div className="w-[300px] flex-shrink-0 bg-white rounded-lg overflow-hidden" data-testid="actor-list-container">
          <ActorList
            actors={filteredActors}
            selectedId={selectedId}
            onSelect={setSelectedId}
            onViewProfile={handleViewProfile}
          />
        </div>
      </div>

      {/* Filters */}
      <FilterBar filters={filters} onChange={setFilters} zoneCounts={zoneCounts} />

      {/* Tooltip */}
      <RadarTooltip actor={hoveredActor} coords={tooltipCoords} />
    </div>
  );
}
