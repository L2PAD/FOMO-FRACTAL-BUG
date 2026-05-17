/**
 * PatternReplaySlider — Replay Pro with Events
 * ==============================================
 * 
 * Features:
 * - Timeline scrubber
 * - Auto-play with speed control
 * - Jump to key events (breakout, breakdown, invalidation)
 * - Confidence evolution mini-chart
 */

import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Play, Pause, SkipForward, SkipBack, Clock, Zap, Radio } from 'lucide-react';

// Event icons and colors
const EVENT_CONFIG = {
  breakout_up: { icon: '▲', color: '#22c55e', label: 'Breakout' },
  breakdown: { icon: '▼', color: '#ef4444', label: 'Breakdown' },
  invalidation: { icon: '✕', color: '#64748b', label: 'Invalid' },
  pattern_change: { icon: '⇄', color: '#f59e0b', label: 'Change' },
  market_state_change: { icon: '◉', color: '#8b5cf6', label: 'Regime' },
  confidence_jump: { icon: '◎', color: '#06b6d4', label: 'Conf' },
};

// Format timestamp
const formatTimestamp = (timestamp) => {
  if (!timestamp) return '';
  const date = new Date(timestamp * 1000);
  return date.toLocaleDateString('en-US', { 
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
  });
};

// Format pattern type
const formatType = (type) => {
  if (!type) return 'Unknown';
  return type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
};

// Confidence Evolution Mini-Chart
const ConfidenceEvolution = ({ timeline, cursor }) => {
  if (!timeline?.length || timeline.length < 2) return null;

  const width = 200;
  const height = 40;
  const maxX = Math.max(timeline.length - 1, 1);

  const points = timeline
    .map((item, i) => {
      const conf = item?.dominant?.confidence ?? 0;
      const x = (i / maxX) * width;
      const y = height - 4 - conf * (height - 8);
      return `${x},${y}`;
    })
    .join(" ");

  // Current position
  const cursorX = (cursor / maxX) * width;

  return (
    <div className="mt-2">
      <div className="text-[10px] text-zinc-500 mb-1">Confidence</div>
      <svg width={width} height={height} className="overflow-visible bg-zinc-900/50 rounded">
        {/* Grid lines */}
        <line x1="0" y1={height/2} x2={width} y2={height/2} stroke="#27272a" strokeWidth="1" />
        
        {/* Confidence line */}
        <polyline
          points={points}
          fill="none"
          stroke="#06b6d4"
          strokeWidth="1.5"
          opacity="0.8"
        />
        
        {/* Current position marker */}
        <line
          x1={cursorX}
          y1="0"
          x2={cursorX}
          y2={height}
          stroke="#fbbf24"
          strokeWidth="1"
          strokeDasharray="2 2"
        />
        <circle cx={cursorX} cy={height - 4 - (timeline[cursor]?.dominant?.confidence ?? 0) * (height - 8)} r="3" fill="#fbbf24" />
      </svg>
    </div>
  );
};

const PatternReplaySlider = ({
  timeline = [],
  events = [],
  cursor,
  setCursor,
  mode,
  setMode,
  speed,
  setSpeed,
  isPlaying,
  setIsPlaying,
  onJumpToEvent,
  onClose,
}) => {
  const playIntervalRef = useRef(null);

  // Current snapshot
  const currentSnapshot = timeline[cursor] || null;

  // Auto-play logic
  useEffect(() => {
    if (isPlaying && mode === 'replay' && timeline.length > 0) {
      playIntervalRef.current = setInterval(() => {
        setCursor(prev => {
          const next = prev + 1;
          if (next >= timeline.length) {
            setIsPlaying(false);
            return prev;
          }
          return next;
        });
      }, speed);
    }

    return () => {
      if (playIntervalRef.current) {
        clearInterval(playIntervalRef.current);
      }
    };
  }, [isPlaying, mode, speed, timeline.length, setCursor, setIsPlaying]);

  // Play/Pause toggle
  const togglePlay = useCallback(() => {
    if (cursor >= timeline.length - 1) {
      setCursor(0);
    }
    setIsPlaying(prev => !prev);
  }, [cursor, timeline.length, setCursor, setIsPlaying]);

  // Jump functions
  const jumpToStart = useCallback(() => {
    setIsPlaying(false);
    setCursor(0);
  }, [setCursor, setIsPlaying]);

  const jumpToEnd = useCallback(() => {
    setIsPlaying(false);
    setCursor(timeline.length - 1);
  }, [setCursor, timeline.length, setIsPlaying]);

  // Handle slider change
  const handleSliderChange = useCallback((e) => {
    setIsPlaying(false);
    setCursor(Number(e.target.value));
  }, [setCursor, setIsPlaying]);

  // Cycle speed
  const cycleSpeed = useCallback(() => {
    setSpeed(prev => {
      if (prev === 900) return 600;
      if (prev === 600) return 300;
      if (prev === 300) return 150;
      return 900;
    });
  }, [setSpeed]);

  // Get speed label
  const getSpeedLabel = () => {
    if (speed === 900) return '0.5x';
    if (speed === 600) return '1x';
    if (speed === 300) return '2x';
    if (speed === 150) return '4x';
    return '1x';
  };

  if (timeline.length === 0) {
    return null;
  }

  return (
    <div 
      className="bg-zinc-900/95 border border-zinc-700 rounded-lg p-3 backdrop-blur-sm"
      data-testid="pattern-replay-slider"
    >
      {/* Header with mode toggle */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Clock size={14} className="text-cyan-400" />
          <span className="text-xs font-semibold text-zinc-200">Market Replay</span>
        </div>
        
        <div className="flex items-center gap-2">
          {/* Mode toggle */}
          <button
            onClick={() => { setMode('live'); setIsPlaying(false); }}
            className={`flex items-center gap-1 text-[10px] px-2 py-1 rounded transition-colors ${
              mode === 'live' ? 'bg-green-500/20 text-green-400' : 'bg-zinc-800 text-zinc-500'
            }`}
            data-testid="mode-live"
          >
            <Radio size={10} />
            Live
          </button>
          <button
            onClick={() => setMode('replay')}
            className={`text-[10px] px-2 py-1 rounded transition-colors ${
              mode === 'replay' ? 'bg-cyan-500/20 text-cyan-400' : 'bg-zinc-800 text-zinc-500'
            }`}
            data-testid="mode-replay"
          >
            Replay
          </button>
        </div>
      </div>

      {mode === 'replay' && (
        <>
          {/* Current state info */}
          {currentSnapshot && (
            <div className="flex items-center gap-3 mb-3 px-2 py-1.5 bg-zinc-800/50 rounded">
              <span className="text-xs font-medium text-zinc-300">
                {formatType(currentSnapshot.dominant?.type)}
              </span>
              
              {/* Lifecycle badge */}
              {currentSnapshot.dominant?.lifecycle && (
                <span 
                  className="text-[9px] font-bold uppercase px-1.5 py-0.5 rounded"
                  style={{
                    background: currentSnapshot.dominant.lifecycle.includes('confirmed') 
                      ? 'rgba(34,197,94,0.15)' 
                      : currentSnapshot.dominant.lifecycle === 'invalidated'
                        ? 'rgba(100,116,139,0.15)'
                        : 'rgba(148,163,184,0.1)',
                    color: currentSnapshot.dominant.lifecycle.includes('confirmed')
                      ? '#22c55e'
                      : currentSnapshot.dominant.lifecycle === 'invalidated'
                        ? '#64748b'
                        : '#94a3b8',
                  }}
                >
                  {currentSnapshot.dominant.lifecycle.replace(/_/g, ' ')}
                </span>
              )}
              
              {/* Confidence */}
              <span className="text-[10px] text-cyan-400">
                {Math.round((currentSnapshot.dominant?.confidence || 0) * 100)}%
              </span>
              
              <span className="text-[10px] text-zinc-500 ml-auto">
                {formatTimestamp(currentSnapshot.timestamp)}
              </span>
            </div>
          )}

          {/* Slider */}
          <div className="relative mb-3">
            <input
              type="range"
              min={0}
              max={timeline.length - 1}
              value={cursor}
              onChange={handleSliderChange}
              className="w-full h-2 bg-zinc-800 rounded-lg appearance-none cursor-pointer"
              style={{
                background: `linear-gradient(to right, #06b6d4 0%, #06b6d4 ${(cursor / (timeline.length - 1)) * 100}%, #27272a ${(cursor / (timeline.length - 1)) * 100}%, #27272a 100%)`,
              }}
              data-testid="replay-slider"
            />
            
            {/* Event markers on slider */}
            <div className="absolute top-0 left-0 right-0 h-2 pointer-events-none">
              {events.map((event, idx) => {
                const eventIdx = timeline.findIndex(t => t.timestamp === event.timestamp);
                if (eventIdx === -1) return null;
                
                const position = (eventIdx / (timeline.length - 1)) * 100;
                const config = EVENT_CONFIG[event.type] || { color: '#64748b' };
                
                return (
                  <div
                    key={idx}
                    className="absolute w-1.5 h-1.5 rounded-full -translate-x-1/2 top-1/2 -translate-y-1/2"
                    style={{ left: `${position}%`, backgroundColor: config.color }}
                    title={event.label}
                  />
                );
              })}
            </div>
          </div>

          {/* Controls */}
          <div className="flex items-center justify-center gap-2 mb-3">
            <button
              onClick={jumpToStart}
              className="p-1.5 rounded hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 transition-colors"
              title="Jump to start"
              data-testid="replay-start"
            >
              <SkipBack size={16} />
            </button>
            
            <button
              onClick={togglePlay}
              className={`p-2 rounded-full transition-colors ${
                isPlaying ? 'bg-cyan-500/20 text-cyan-400' : 'bg-zinc-800 text-zinc-200 hover:bg-zinc-700'
              }`}
              title={isPlaying ? 'Pause' : 'Play'}
              data-testid="replay-play-pause"
            >
              {isPlaying ? <Pause size={18} /> : <Play size={18} />}
            </button>
            
            <button
              onClick={jumpToEnd}
              className="p-1.5 rounded hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 transition-colors"
              title="Jump to live"
              data-testid="replay-end"
            >
              <SkipForward size={16} />
            </button>
            
            <button
              onClick={cycleSpeed}
              className="ml-2 px-2 py-1 rounded text-[10px] font-mono bg-zinc-800 text-zinc-300 hover:bg-zinc-700 transition-colors"
              title="Change speed"
              data-testid="replay-speed"
            >
              {getSpeedLabel()}
            </button>
          </div>

          {/* Event jump buttons */}
          {events.length > 0 && (
            <div className="flex gap-1.5 overflow-x-auto pb-1 mb-2">
              {events.map((event, idx) => {
                const config = EVENT_CONFIG[event.type] || { icon: '•', color: '#64748b', label: event.type };
                return (
                  <button
                    key={idx}
                    onClick={() => onJumpToEvent && onJumpToEvent(event.timestamp)}
                    className="flex items-center gap-1 whitespace-nowrap rounded px-2 py-1 text-[10px] bg-zinc-800 hover:bg-zinc-700 transition-colors"
                    style={{ color: config.color }}
                    data-testid={`event-${event.type}`}
                  >
                    <span>{config.icon}</span>
                    <span>{event.label || config.label}</span>
                  </button>
                );
              })}
            </div>
          )}

          {/* Confidence evolution */}
          <ConfidenceEvolution timeline={timeline} cursor={cursor} />

          {/* Position indicator */}
          <div className="text-[10px] text-zinc-500 text-center mt-2">
            {cursor + 1} / {timeline.length}
          </div>
        </>
      )}
    </div>
  );
};

export default PatternReplaySlider;
