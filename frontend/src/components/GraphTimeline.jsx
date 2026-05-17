import React, { useState, useCallback, useRef, useEffect } from 'react';
import { useGraphStore } from '../graph/store/graphStore';
import { Play, Pause, RotateCcw } from 'lucide-react';

const PRESETS = [
  { label: '24h', seconds: 86400 },
  { label: '7d', seconds: 604800 },
  { label: '30d', seconds: 2592000 },
  { label: '90d', seconds: 7776000 },
  { label: 'All', seconds: 0 },
];

const GraphTimeline = ({ style }) => {
  const { timeRange, setTimeRange, clearTimeRange, graphData } = useGraphStore();
  const [playing, setPlaying] = useState(false);
  const [activePreset, setActivePreset] = useState('All');
  const playRef = useRef(null);

  // Compute time bounds from graph edges
  const timeBounds = React.useMemo(() => {
    const timestamps = (graphData.edges || [])
      .map(e => e.timestamp)
      .filter(t => t && t > 0);
    if (timestamps.length === 0) return null;
    return {
      min: Math.min(...timestamps),
      max: Math.max(...timestamps),
    };
  }, [graphData.edges]);

  const handlePreset = useCallback((preset) => {
    setActivePreset(preset.label);
    if (preset.seconds === 0) {
      clearTimeRange();
      return;
    }
    const now = Math.floor(Date.now() / 1000);
    setTimeRange({ start: now - preset.seconds, end: now });
  }, [setTimeRange, clearTimeRange]);

  // Playback: animate through time range
  const startPlayback = useCallback(() => {
    if (!timeBounds) return;
    setPlaying(true);

    const duration = timeBounds.max - timeBounds.min;
    const steps = 20;
    const stepSize = Math.floor(duration / steps);
    let step = 0;

    playRef.current = setInterval(() => {
      step++;
      if (step > steps) {
        clearInterval(playRef.current);
        setPlaying(false);
        clearTimeRange();
        return;
      }
      setTimeRange({
        start: timeBounds.min,
        end: timeBounds.min + stepSize * step,
      });
    }, 500);
  }, [timeBounds, setTimeRange, clearTimeRange]);

  const stopPlayback = useCallback(() => {
    if (playRef.current) clearInterval(playRef.current);
    setPlaying(false);
  }, []);

  useEffect(() => {
    return () => {
      if (playRef.current) clearInterval(playRef.current);
    };
  }, []);

  const hasTimestamps = timeBounds !== null;

  return (
    <div
      data-testid="graph-timeline"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        padding: '6px 12px',
        backgroundColor: 'rgba(15, 23, 42, 0.8)',
        borderRadius: '8px',
        backdropFilter: 'blur(10px)',
        border: '1px solid rgba(148, 163, 184, 0.15)',
        ...style,
      }}
    >
      {/* Play/Pause */}
      <button
        data-testid="graph-playback-btn"
        onClick={playing ? stopPlayback : startPlayback}
        disabled={!hasTimestamps}
        style={{
          background: 'none',
          border: '1px solid rgba(148, 163, 184, 0.3)',
          borderRadius: '6px',
          padding: '4px 6px',
          color: hasTimestamps ? '#f8fafc' : '#475569',
          cursor: hasTimestamps ? 'pointer' : 'not-allowed',
          display: 'flex',
          alignItems: 'center',
        }}
      >
        {playing ? <Pause size={14} /> : <Play size={14} />}
      </button>

      {/* Preset buttons */}
      {PRESETS.map(p => (
        <button
          key={p.label}
          data-testid={`timeline-preset-${p.label}`}
          onClick={() => handlePreset(p)}
          style={{
            background: activePreset === p.label ? 'rgba(245, 158, 11, 0.2)' : 'transparent',
            border: activePreset === p.label ? '1px solid rgba(245, 158, 11, 0.4)' : '1px solid transparent',
            borderRadius: '4px',
            padding: '2px 8px',
            fontSize: '11px',
            color: activePreset === p.label ? '#f59e0b' : '#94a3b8',
            cursor: 'pointer',
            fontWeight: activePreset === p.label ? 600 : 400,
          }}
        >
          {p.label}
        </button>
      ))}

      {/* Reset */}
      <button
        data-testid="timeline-reset-btn"
        onClick={() => { clearTimeRange(); setActivePreset('All'); stopPlayback(); }}
        style={{
          background: 'none',
          border: 'none',
          padding: '4px',
          color: '#64748b',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
        }}
      >
        <RotateCcw size={12} />
      </button>

      {/* Status */}
      {timeRange.start && (
        <span style={{ fontSize: '10px', color: '#64748b', marginLeft: '4px' }}>
          {new Date(timeRange.start * 1000).toLocaleDateString()} — {new Date((timeRange.end || Date.now() / 1000) * 1000).toLocaleDateString()}
        </span>
      )}
    </div>
  );
};

export default GraphTimeline;
