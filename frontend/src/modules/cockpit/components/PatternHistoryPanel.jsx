/**
 * PatternHistoryPanel — Market Evolution Display
 * ===============================================
 * 
 * Shows pattern history timeline:
 * - Key events (breakouts, invalidations)
 * - Market state changes
 * - Toggle for history overlay
 */

import React from 'react';
import { Clock, TrendingUp, TrendingDown, X, AlertCircle } from 'lucide-react';

// Event type icons and colors
const EVENT_CONFIG = {
  breakout: { icon: TrendingUp, color: '#22c55e', label: 'Breakout' },
  breakdown: { icon: TrendingDown, color: '#ef4444', label: 'Breakdown' },
  invalidation: { icon: X, color: '#64748b', label: 'Invalidated' },
  pattern_change: { icon: AlertCircle, color: '#f59e0b', label: 'Pattern Change' },
  initial: { icon: Clock, color: '#94a3b8', label: 'Initial' },
  update: { icon: Clock, color: '#475569', label: 'Update' },
};

// Format timestamp
const formatTime = (timestamp) => {
  if (!timestamp) return '';
  const date = new Date(timestamp * 1000);
  const now = new Date();
  const diff = now - date;
  
  // If less than 24 hours, show time
  if (diff < 86400000) {
    return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
  }
  // If less than 7 days, show day + time
  if (diff < 604800000) {
    return date.toLocaleDateString('en-US', { weekday: 'short', hour: '2-digit', minute: '2-digit' });
  }
  // Otherwise show date
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
};

// Format pattern type
const formatType = (type) => {
  if (!type) return 'Unknown';
  return type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
};

// Single event item
const EventItem = ({ event }) => {
  const config = EVENT_CONFIG[event.event_type] || EVENT_CONFIG.update;
  const Icon = config.icon;
  
  return (
    <div 
      className="flex items-center gap-2 py-1.5 px-2 rounded hover:bg-zinc-800/50 transition-colors"
      data-testid={`history-event-${event.event_type}`}
    >
      {/* Event icon */}
      <Icon 
        size={14} 
        style={{ color: config.color }}
        className="flex-shrink-0"
      />
      
      {/* Pattern type */}
      <span className="text-xs font-medium text-zinc-200 flex-1 truncate">
        {formatType(event.type)}
      </span>
      
      {/* Lifecycle badge */}
      {event.lifecycle && event.lifecycle !== 'forming' && (
        <span 
          className="text-[9px] font-bold uppercase px-1.5 py-0.5 rounded"
          style={{
            background: event.lifecycle.includes('confirmed') ? 'rgba(34,197,94,0.15)' : 
                       event.lifecycle === 'invalidated' ? 'rgba(100,116,139,0.15)' : 'transparent',
            color: event.lifecycle.includes('confirmed') ? '#22c55e' :
                  event.lifecycle === 'invalidated' ? '#64748b' : '#94a3b8',
          }}
        >
          {event.lifecycle === 'confirmed_up' ? '↑' :
           event.lifecycle === 'confirmed_down' ? '↓' :
           event.lifecycle === 'invalidated' ? '✕' : ''}
        </span>
      )}
      
      {/* Time */}
      <span className="text-[10px] text-zinc-500 flex-shrink-0">
        {formatTime(event.timestamp)}
      </span>
    </div>
  );
};

// Main component
const PatternHistoryPanel = ({ 
  history = [], 
  events = [],
  showOverlay,
  onToggleOverlay,
  isLoading = false,
}) => {
  // Use events if provided, otherwise extract from history
  const displayEvents = events.length > 0 ? events : history.slice(0, 5).map(h => ({
    timestamp: h.timestamp,
    event_type: h.event_type || 'update',
    type: h.dominant?.type,
    lifecycle: h.dominant?.lifecycle,
    market_state: h.market_state,
    confidence: h.dominant?.confidence,
  }));

  if (isLoading) {
    return (
      <div className="bg-zinc-900/80 border border-zinc-800 rounded-lg p-3">
        <div className="text-xs text-zinc-500 animate-pulse">Loading history...</div>
      </div>
    );
  }

  if (displayEvents.length === 0) {
    return (
      <div className="bg-zinc-900/80 border border-zinc-800 rounded-lg p-3">
        <div className="text-xs text-zinc-500">No history available</div>
      </div>
    );
  }

  return (
    <div 
      className="bg-zinc-900/80 border border-zinc-800 rounded-lg overflow-hidden"
      data-testid="pattern-history-panel"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-zinc-800">
        <div className="flex items-center gap-2">
          <Clock size={14} className="text-zinc-400" />
          <span className="text-xs font-semibold text-zinc-300">Market Evolution</span>
        </div>
        
        {/* History overlay toggle */}
        {onToggleOverlay && (
          <button
            onClick={onToggleOverlay}
            className={`text-[10px] px-2 py-1 rounded transition-colors ${
              showOverlay 
                ? 'bg-cyan-500/20 text-cyan-400' 
                : 'bg-zinc-800 text-zinc-500 hover:text-zinc-300'
            }`}
            data-testid="toggle-history-overlay"
          >
            {showOverlay ? 'Overlay ON' : 'Overlay OFF'}
          </button>
        )}
      </div>
      
      {/* Events list */}
      <div className="px-1 py-1 max-h-[200px] overflow-y-auto custom-scrollbar">
        {displayEvents.map((event, idx) => (
          <EventItem key={idx} event={event} />
        ))}
      </div>
    </div>
  );
};

export default PatternHistoryPanel;
