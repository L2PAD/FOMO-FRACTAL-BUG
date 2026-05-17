/**
 * P5.2 — Timeline Tab (Light Theme)
 * 
 * Version history showing lifecycle events (PROMOTE/ROLLBACK/CONFIG_UPDATE).
 * Displays config diffs, health snapshots, and artifact counts.
 */

import React, { useState, useEffect, useCallback } from 'react';

const API_BASE = process.env.REACT_APP_BACKEND_URL || '';

const SCOPES = ['BTC', 'SPX', 'DXY', 'CROSS_ASSET'];

const EVENT_COLORS = {
  PROMOTE: 'bg-green-100 text-green-700',
  ROLLBACK: 'bg-red-100 text-red-700',
  CONFIG_UPDATE: 'bg-blue-100 text-blue-700',
  FREEZE: 'bg-purple-100 text-purple-700',
  UNFREEZE: 'bg-cyan-100 text-cyan-700',
  FORCE_OVERRIDE: 'bg-orange-100 text-orange-700',
  HEALTH_TRANSITION: 'bg-amber-100 text-amber-700',
};

const GRADE_COLORS = {
  HEALTHY: 'text-green-600',
  DEGRADED: 'text-amber-600',
  CRITICAL: 'text-red-600',
};

function EventTypeBadge({ type }) {
  const color = EVENT_COLORS[type] || EVENT_COLORS.PROMOTE;
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${color}`}>
      {type}
    </span>
  );
}

function GradeBadge({ grade }) {
  const color = GRADE_COLORS[grade] || 'text-gray-500';
  const icons = { HEALTHY: '✓', DEGRADED: '⚠', CRITICAL: '✗' };
  return (
    <span className={`text-sm flex items-center gap-1 ${color}`}>
      {icons[grade] || '○'} {grade}
    </span>
  );
}

function DiffItem({ diff }) {
  return (
    <div className="text-xs font-mono bg-gray-100 rounded px-2 py-1 flex items-center gap-2">
      <span className="text-gray-500">{diff.path}:</span>
      <span className="text-red-500 line-through">{JSON.stringify(diff.from)}</span>
      <span className="text-gray-400">→</span>
      <span className="text-green-600">{JSON.stringify(diff.to)}</span>
    </div>
  );
}

function TimelineEvent({ event, expanded, onToggle }) {
  const hasDetails = event.config?.diff?.length > 0 || event.health?.reasons?.length > 0;
  
  return (
    <div className="relative">
      {/* Timeline line */}
      <div className="absolute left-5 top-10 bottom-0 w-0.5 bg-gray-200" />
      
      {/* Event card */}
      <div className="relative pl-12 pb-4">
        {/* Timeline dot */}
        <div className="absolute left-3.5 top-2 w-3 h-3 rounded-full bg-blue-500 border-2 border-white shadow" />
        
        <div 
          className={`bg-white rounded-lg border border-gray-200 overflow-hidden ${hasDetails ? 'cursor-pointer' : ''}`}
          onClick={() => hasDetails && onToggle()}
        >
          {/* Header */}
          <div className="px-4 py-3 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <EventTypeBadge type={event.type} />
              <span className="text-sm font-mono text-gray-600">
                {event.versionId || 'N/A'}
              </span>
              <GradeBadge grade={event.health?.grade || 'HEALTHY'} />
            </div>
            
            <div className="flex items-center gap-4">
              {/* Artifacts */}
              <div className="flex items-center gap-3 text-xs text-gray-400">
                {event.artifacts?.snapshotsCreated > 0 && (
                  <span>+{event.artifacts.snapshotsCreated} snapshots</span>
                )}
                {event.artifacts?.outcomesCreated > 0 && (
                  <span>+{event.artifacts.outcomesCreated} outcomes</span>
                )}
              </div>
              
              {/* Timestamp */}
              <span className="text-xs text-gray-400">
                {new Date(event.at).toLocaleString()}
              </span>
              
              {/* Expand icon */}
              {hasDetails && (
                <svg 
                  className={`w-4 h-4 text-gray-400 transition-transform ${expanded ? 'rotate-180' : ''}`} 
                  fill="none" 
                  stroke="currentColor" 
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              )}
            </div>
          </div>
          
          {/* Quick diff preview */}
          {!expanded && event.config?.diff?.length > 0 && (
            <div className="px-4 pb-3 flex flex-wrap gap-2">
              {event.config.diff.slice(0, 3).map((d, i) => (
                <span key={i} className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
                  {d.path}
                </span>
              ))}
              {event.config.diff.length > 3 && (
                <span className="text-xs text-gray-400">+{event.config.diff.length - 3} more</span>
              )}
            </div>
          )}
          
          {/* Expanded details */}
          {expanded && (
            <div className="border-t border-gray-200 p-4 bg-gray-50 space-y-4">
              {/* Config Diff */}
              {event.config?.diff?.length > 0 && (
                <div>
                  <div className="text-xs text-gray-500 uppercase mb-2 flex items-center gap-1">
                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                    Config Changes
                  </div>
                  <div className="space-y-1">
                    {event.config.diff.map((d, i) => (
                      <DiffItem key={i} diff={d} />
                    ))}
                  </div>
                </div>
              )}
              
              {/* Health Metrics */}
              {event.health?.metrics && (
                <div>
                  <div className="text-xs text-gray-500 uppercase mb-2">Health Metrics</div>
                  <div className="grid grid-cols-3 gap-2 text-sm">
                    <div className="bg-white rounded px-2 py-1 border border-gray-200">
                      <span className="text-gray-500">Hit Rate: </span>
                      <span className="text-gray-900 font-medium">
                        {event.health.metrics.hitRate 
                          ? (event.health.metrics.hitRate * 100).toFixed(1) + '%'
                          : 'N/A'}
                      </span>
                    </div>
                    <div className="bg-white rounded px-2 py-1 border border-gray-200">
                      <span className="text-gray-500">Avg Error: </span>
                      <span className="text-gray-900 font-medium">
                        {event.health.metrics.avgAbsError?.toFixed(2) || 'N/A'}%
                      </span>
                    </div>
                    <div className="bg-white rounded px-2 py-1 border border-gray-200">
                      <span className="text-gray-500">Samples: </span>
                      <span className="text-gray-900 font-medium">
                        {event.health.metrics.sampleCount || 0}
                      </span>
                    </div>
                  </div>
                </div>
              )}
              
              {/* Reasons */}
              {event.health?.reasons?.length > 0 && (
                <div>
                  <div className="text-xs text-gray-500 uppercase mb-2">Reasons</div>
                  <ul className="space-y-1">
                    {event.health.reasons.map((reason, i) => (
                      <li key={i} className="text-sm text-gray-600 flex items-center gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-gray-400" />
                        {reason}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              
              {/* Version transition */}
              {(event.fromVersionId || event.toVersionId) && (
                <div className="text-xs text-gray-500">
                  {event.fromVersionId && (
                    <span>From: <code className="text-gray-700">{event.fromVersionId}</code></span>
                  )}
                  {event.fromVersionId && event.toVersionId && <span> → </span>}
                  {event.toVersionId && (
                    <span>To: <code className="text-gray-700">{event.toVersionId}</code></span>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function TimelineTab() {
  const [scope, setScope] = useState('BTC');
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [expandedId, setExpandedId] = useState(null);
  const [summary, setSummary] = useState({});
  
  const fetchTimeline = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/admin/timeline?scope=${scope}&limit=50`);
      const data = await res.json();
      
      if (data.ok) {
        setEvents(data.items || []);
      } else {
        setError(data.error || 'Failed to fetch timeline');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [scope]);
  
  const fetchSummary = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/admin/timeline/summary`);
      const data = await res.json();
      if (data.ok) {
        setSummary(data.summary || {});
      }
    } catch (err) {
      console.error('Failed to fetch summary:', err);
    }
  }, []);
  
  useEffect(() => {
    fetchTimeline();
    fetchSummary();
  }, [fetchTimeline, fetchSummary]);
  
  const toggleEvent = (id) => {
    setExpandedId(expandedId === id ? null : id);
  };
  
  return (
    <div className="space-y-6" data-testid="timeline-tab">
      {/* Header Card */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <div className="px-4 py-3 bg-slate-900 flex items-center justify-between">
          <div>
            <h3 className="font-bold text-white">История версий</h3>
            <p className="text-xs text-slate-400">Хронология изменений и событий модели</p>
          </div>
          <button
            onClick={fetchTimeline}
            disabled={loading}
            className="p-2 text-white hover:bg-slate-700 rounded transition-colors disabled:opacity-50"
            title="Refresh"
            data-testid="refresh-timeline-btn"
          >
            <svg className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
        </div>
        
        {error && (
          <div className="px-4 py-2 bg-red-50 text-red-600 text-sm">{error}</div>
        )}
        
        {/* Scope Selector */}
        <div className="p-4 flex gap-2 border-b border-gray-200">
          {SCOPES.map(s => {
            const scopeSummary = summary[s] || {};
            return (
              <button
                key={s}
                onClick={() => setScope(s)}
                className={`px-3 py-1.5 rounded text-sm font-medium transition-colors flex items-center gap-2 ${
                  scope === s 
                    ? 'bg-blue-600 text-white' 
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
                data-testid={`scope-btn-${s}`}
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                </svg>
                {s}
                {scopeSummary.eventCount > 0 && (
                  <span className={`text-xs px-1.5 py-0.5 rounded-full ${
                    scope === s ? 'bg-blue-500' : 'bg-gray-300'
                  }`}>
                    {scopeSummary.eventCount}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>
      
      {/* Timeline */}
      {loading && events.length === 0 ? (
        <div className="bg-white rounded-lg border border-gray-200 p-8 text-center">
          <svg className="w-8 h-8 mx-auto mb-3 text-blue-500 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          <p className="text-gray-500">Загрузка истории...</p>
        </div>
      ) : events.length === 0 ? (
        <div className="bg-white rounded-lg border border-gray-200 p-8 text-center">
          <svg className="w-12 h-12 mx-auto mb-3 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="text-gray-600">Событий для {scope} пока нет</p>
          <p className="text-sm text-gray-400 mt-1">События появятся при промоции или откате версий</p>
        </div>
      ) : (
        <div className="relative">
          {events.map((event) => (
            <TimelineEvent
              key={event.id}
              event={event}
              expanded={expandedId === event.id}
              onToggle={() => toggleEvent(event.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default TimelineTab;
