/**
 * Execution Workspace — Sprint 3: Stabilized
 * 
 * Shows execution state with proper loading guards and empty states.
 */
import { useState, useEffect } from 'react';
import { LoadingGuard, EmptyState } from '../guards/TerminalGuard';
import { Activity, Zap } from 'lucide-react';
import ExecutionHero from "../execution/ExecutionHero";
import ExecutionTimeline from "../execution/ExecutionTimeline";
import ExecutionQualityPanel from "../execution/ExecutionQualityPanel";
import ExecutionImpact from "../execution/ExecutionImpact";

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

function ExecutionFeed() {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(`${API_URL}/api/execution/feed?limit=20`);
        const data = await res.json();
        setEvents(data.events || data.feed || []);
        setError(null);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    load();
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <LoadingGuard loading={loading} error={error}>
      {events.length === 0 ? (
        <EmptyState 
          icon={Zap} 
          title="No execution events yet" 
          subtitle="Events appear when runtime processes signals" 
        />
      ) : (
        <div className="space-y-1" data-testid="execution-feed-list">
          {events.slice(0, 15).map((evt, i) => (
            <div key={i} className="flex items-center gap-3 px-3 py-2 bg-gray-800/30 rounded text-xs">
              <span className="text-gray-500 font-mono w-24 flex-shrink-0">
                {new Date(evt.timestamp_dt || evt.timestamp).toLocaleTimeString()}
              </span>
              <span className={`font-medium w-48 flex-shrink-0 ${
                evt.type?.includes('APPROVED') ? 'text-green-400' :
                evt.type?.includes('REJECTED') || evt.type?.includes('BLOCKED') ? 'text-red-400' :
                evt.type?.includes('SIGNAL') ? 'text-blue-400' :
                'text-gray-400'
              }`}>
                {evt.type}
              </span>
              <span className="text-gray-300">{evt.symbol || ''}</span>
              <span className="text-gray-500 truncate">{evt.reason || evt.side || ''}</span>
            </div>
          ))}
        </div>
      )}
    </LoadingGuard>
  );
}

export default function ExecutionWorkspace() {
  return (
    <div className="flex flex-col h-full p-6 gap-4 overflow-y-auto bg-[hsl(var(--bg-2))]" data-testid="execution-workspace">
      
      {/* HERO — Execution Status */}
      <ExecutionHero />

      {/* Core Grid */}
      <div className="grid grid-cols-3 gap-4">
        
        {/* LEFT: Timeline + Impact */}
        <div className="col-span-2 flex flex-col gap-4">
          <ExecutionTimeline />
          <ExecutionImpact />
        </div>

        {/* RIGHT: Quality Panel */}
        <ExecutionQualityPanel />
      </div>
      
      {/* Sprint 3: Live execution feed */}
      <div className="bg-gray-900/50 border border-gray-800 rounded-lg p-4">
        <div className="flex items-center gap-2 mb-3">
          <Activity size={16} className="text-blue-400" />
          <h4 className="text-sm font-medium text-gray-300">Execution Feed</h4>
        </div>
        <ExecutionFeed />
      </div>
    </div>
  );
}
