import React, { useState, useEffect, useRef, useCallback } from 'react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const SPEEDS = [1, 2, 4, 10];
const TRAIL_DURATION = 2500; // ms — flow trail fade time
const TICK_BASE = 800; // ms per event at 1x speed

// Colors by flow direction
const FLOW_COLORS = {
  deposit: '#10b981',    // green — incoming
  withdraw: '#ef4444',   // red — outgoing
  swap: '#3b82f6',       // blue — internal
  transfer: '#f59e0b',   // amber
  rotation: '#8b5cf6',   // purple
  default: '#06b6d4',    // cyan
};

function getFlowColor(type) {
  return FLOW_COLORS[type] || FLOW_COLORS.default;
}

function formatTimestamp(ts) {
  if (!ts) return '';
  const d = new Date(ts * 1000);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) + ' ' +
    d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
}

export default function GraphPlaybackControl({
  nodeId = '',
  seeds = '',
  onHighlightsChange, // (Map<edgeKey, {intensity, color}> | null) => void
  onActiveChange,     // (boolean) => void
}) {
  const [events, setEvents] = useState([]);
  const [timeRange, setTimeRange] = useState({ start: 0, end: 0 });
  const [loading, setLoading] = useState(false);
  const [resolution, setResolution] = useState('24h');

  // Playback state
  const [playing, setPlaying] = useState(false);
  const [speedIdx, setSpeedIdx] = useState(0);
  const [currentIdx, setCurrentIdx] = useState(-1);
  const [eventGroups, setEventGroups] = useState([]); // grouped by timestamp
  const [currentGroupIdx, setCurrentGroupIdx] = useState(-1);

  // Refs for animation loop
  const timerRef = useRef(null);
  const trailsRef = useRef(new Map()); // edgeKey → { color, addedAt }
  const speedRef = useRef(SPEEDS[0]);

  // Fetch flow events
  const fetchEvents = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ resolution, max_events: '500' });
      if (nodeId) params.set('node_id', nodeId);
      if (seeds) params.set('seeds', seeds);
      const resp = await fetch(`${API_URL}/api/graph-core/playback/events?${params}`);
      if (!resp.ok) throw new Error('fetch failed');
      const data = await resp.json();
      setEvents(data.events || []);
      setTimeRange(data.time_range || { start: 0, end: 0 });

      // Group events by timestamp
      const groups = [];
      let lastTs = null;
      for (const evt of (data.events || [])) {
        if (evt.timestamp !== lastTs) {
          groups.push({ timestamp: evt.timestamp, events: [evt] });
          lastTs = evt.timestamp;
        } else {
          groups[groups.length - 1].events.push(evt);
        }
      }
      setEventGroups(groups);
      setCurrentGroupIdx(-1);
      setCurrentIdx(-1);
    } catch {
      setEvents([]);
      setEventGroups([]);
    } finally {
      setLoading(false);
    }
  }, [nodeId, seeds, resolution]);

  useEffect(() => {
    fetchEvents();
  }, [fetchEvents]);

  // Notify parent when active/inactive
  useEffect(() => {
    onActiveChange?.(true);
    return () => {
      onActiveChange?.(false);
      onHighlightsChange?.(null);
    };
  }, [onActiveChange, onHighlightsChange]);

  // Build highlight map from current position + trails
  const buildHighlights = useCallback((groupIdx) => {
    const now = Date.now();
    const highlights = new Map();

    // Add trails (fading)
    trailsRef.current.forEach((trail, key) => {
      const age = now - trail.addedAt;
      if (age > TRAIL_DURATION) {
        trailsRef.current.delete(key);
      } else {
        const intensity = 0.9 * (1 - age / TRAIL_DURATION);
        if (intensity > 0.05) {
          highlights.set(key, { intensity, color: trail.color });
        }
      }
    });

    // Add current group events (full brightness)
    if (groupIdx >= 0 && groupIdx < eventGroups.length) {
      const group = eventGroups[groupIdx];
      for (const evt of group.events) {
        const color = getFlowColor(evt.type);
        highlights.set(evt.edge_key, { intensity: 0.95, color });
        // Add to trails
        trailsRef.current.set(evt.edge_key, { color, addedAt: now });
      }
    }

    return highlights.size > 0 ? highlights : null;
  }, [eventGroups]);

  // Animation loop
  useEffect(() => {
    if (!playing || eventGroups.length === 0) return;

    const tick = () => {
      setCurrentGroupIdx(prev => {
        const next = prev + 1;
        if (next >= eventGroups.length) {
          // End of playback
          setPlaying(false);
          return prev;
        }
        const highlights = buildHighlights(next);
        onHighlightsChange?.(highlights);
        return next;
      });
    };

    const interval = TICK_BASE / speedRef.current;
    timerRef.current = setInterval(tick, interval);

    return () => clearInterval(timerRef.current);
  }, [playing, eventGroups, buildHighlights, onHighlightsChange]);

  // Update speed ref
  useEffect(() => {
    speedRef.current = SPEEDS[speedIdx];
    // Restart interval if playing
    if (playing) {
      clearInterval(timerRef.current);
      const interval = TICK_BASE / speedRef.current;
      timerRef.current = setInterval(() => {
        setCurrentGroupIdx(prev => {
          const next = prev + 1;
          if (next >= eventGroups.length) {
            setPlaying(false);
            return prev;
          }
          const highlights = buildHighlights(next);
          onHighlightsChange?.(highlights);
          return next;
        });
      }, interval);
    }
    return () => clearInterval(timerRef.current);
  }, [speedIdx, playing, eventGroups, buildHighlights, onHighlightsChange]);

  // Trail refresh during playback (for fading effect)
  useEffect(() => {
    if (!playing) return;
    const refreshTrails = setInterval(() => {
      if (currentGroupIdx >= 0) {
        const highlights = buildHighlights(currentGroupIdx);
        onHighlightsChange?.(highlights);
      }
    }, 200);
    return () => clearInterval(refreshTrails);
  }, [playing, currentGroupIdx, buildHighlights, onHighlightsChange]);

  const handlePlay = () => {
    if (currentGroupIdx >= eventGroups.length - 1) {
      // Reset to beginning
      setCurrentGroupIdx(-1);
      trailsRef.current.clear();
    }
    setPlaying(true);
  };

  const handlePause = () => {
    setPlaying(false);
  };

  const handleStep = () => {
    setPlaying(false);
    const next = Math.min(currentGroupIdx + 1, eventGroups.length - 1);
    setCurrentGroupIdx(next);
    const highlights = buildHighlights(next);
    onHighlightsChange?.(highlights);
  };

  const handleReset = () => {
    setPlaying(false);
    setCurrentGroupIdx(-1);
    trailsRef.current.clear();
    onHighlightsChange?.(null);
  };

  const handleSpeedToggle = () => {
    setSpeedIdx(prev => (prev + 1) % SPEEDS.length);
  };

  const currentGroup = currentGroupIdx >= 0 && currentGroupIdx < eventGroups.length ? eventGroups[currentGroupIdx] : null;
  const progress = eventGroups.length > 0 ? Math.max(0, (currentGroupIdx + 1) / eventGroups.length) : 0;

  // Styles
  const panelStyle = {
    position: 'absolute', bottom: '12px', left: '12px', right: '12px',
    backgroundColor: 'rgba(10, 14, 26, 0.95)', border: '1px solid rgba(100, 116, 139, 0.2)',
    borderRadius: '12px', padding: '10px 14px', backdropFilter: 'blur(12px)',
    boxShadow: '0 8px 32px rgba(0,0,0,0.5)', zIndex: 20,
  };
  const btnStyle = {
    padding: '5px 10px', borderRadius: '6px', border: '1px solid rgba(148,163,184,0.15)',
    backgroundColor: 'rgba(255,255,255,0.06)', color: '#e2e8f0',
    fontSize: '11px', fontWeight: 600, cursor: 'pointer', transition: 'all 0.15s',
  };
  const activeBtnStyle = { ...btnStyle, backgroundColor: 'rgba(139, 92, 246, 0.3)', borderColor: '#8b5cf6', color: '#a78bfa' };

  if (loading) {
    return (
      <div data-testid="graph-playback-control" style={panelStyle}>
        <div style={{ color: '#94a3b8', fontSize: '12px', textAlign: 'center' }}>Loading flow events...</div>
      </div>
    );
  }

  if (events.length === 0) {
    return (
      <div data-testid="graph-playback-control" style={panelStyle}>
        <div style={{ color: '#64748b', fontSize: '12px', textAlign: 'center' }}>No flow events available for this graph</div>
      </div>
    );
  }

  return (
    <div data-testid="graph-playback-control" style={panelStyle}>
      {/* Top row: Controls + Speed + Resolution */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
        {/* Play/Pause */}
        {!playing ? (
          <button data-testid="playback-play-btn" onClick={handlePlay} style={activeBtnStyle} title="Play">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="5,3 19,12 5,21"/></svg>
          </button>
        ) : (
          <button data-testid="playback-pause-btn" onClick={handlePause} style={activeBtnStyle} title="Pause">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
          </button>
        )}

        {/* Step */}
        <button data-testid="playback-step-btn" onClick={handleStep} style={btnStyle} title="Step forward">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="4,4 15,12 4,20"/><rect x="16" y="4" width="3" height="16"/></svg>
        </button>

        {/* Reset */}
        <button data-testid="playback-reset-btn" onClick={handleReset} style={btnStyle} title="Reset">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="1,4 1,10 7,10"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/></svg>
        </button>

        {/* Speed */}
        <button data-testid="playback-speed-btn" onClick={handleSpeedToggle} style={btnStyle}>
          {SPEEDS[speedIdx]}x
        </button>

        <div style={{ flex: 1 }} />

        {/* Resolution */}
        <div style={{ display: 'flex', gap: '3px' }}>
          {['1h', '24h', '7d', '30d'].map(r => (
            <button key={r} onClick={() => { setResolution(r); handleReset(); }} style={r === resolution ? activeBtnStyle : btnStyle}>
              {r}
            </button>
          ))}
        </div>
      </div>

      {/* Progress bar */}
      <div style={{ position: 'relative', height: '6px', backgroundColor: 'rgba(100,116,139,0.15)', borderRadius: '3px', marginBottom: '6px', cursor: 'pointer' }}
        onClick={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          const pct = (e.clientX - rect.left) / rect.width;
          const idx = Math.floor(pct * eventGroups.length);
          setCurrentGroupIdx(Math.min(idx, eventGroups.length - 1));
          trailsRef.current.clear();
          const highlights = buildHighlights(idx);
          onHighlightsChange?.(highlights);
        }}
      >
        <div style={{
          height: '100%', borderRadius: '3px',
          backgroundColor: playing ? '#8b5cf6' : '#64748b',
          width: `${progress * 100}%`,
          transition: playing ? 'none' : 'width 0.2s ease',
        }} />
      </div>

      {/* Bottom row: Time info + Event stats */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', gap: '12px', fontSize: '10px', color: '#64748b' }}>
          <span>{formatTimestamp(timeRange.start)}</span>
          {currentGroup && (
            <span style={{ color: '#a78bfa', fontWeight: 600 }}>
              {formatTimestamp(currentGroup.timestamp)}
            </span>
          )}
        </div>
        <div style={{ display: 'flex', gap: '12px', fontSize: '10px', color: '#64748b' }}>
          <span>{events.length} events</span>
          <span>{eventGroups.length} frames</span>
          {currentGroup && (
            <span style={{ color: '#e2e8f0' }}>
              ${currentGroup.events.reduce((s, e) => s + e.volume_usd, 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}
            </span>
          )}
          <span>{formatTimestamp(timeRange.end)}</span>
        </div>
      </div>
    </div>
  );
}
