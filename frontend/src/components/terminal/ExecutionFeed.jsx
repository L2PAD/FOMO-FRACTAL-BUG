/**
 * ExecutionFeed → Activity
 *
 * Visual cleanup 2026-04-30. Source endpoint, polling cadence and
 * data shape are UNCHANGED — only labels and layout move.
 *
 * Each event line answers two questions in one glance:
 *   1. What did the system do?  (humanised verb, not raw enum)
 *   2. What does it relate to?  (Decision / Signal / Position / Risk / Execution)
 */
import { useState, useEffect } from 'react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// Map raw event type → { category, label, tone }
// Tone is semantic, not enum-color.
function describeEvent(type) {
  switch (type) {
    case 'ORDER_SUBMIT_REQUESTED':   return { category: 'Execution', label: 'Order submitted',           tone: 'gray'    };
    case 'ORDER_ACKNOWLEDGED':       return { category: 'Execution', label: 'Order acknowledged',        tone: 'blue'    };
    case 'ORDER_FILLED':             return { category: 'Execution', label: 'Order filled',              tone: 'emerald' };
    case 'ORDER_REJECTED':           return { category: 'Execution', label: 'Order rejected',            tone: 'red'     };
    case 'DECISION_EXECUTED':        return { category: 'Decision',  label: 'Decision executed',         tone: 'emerald' };
    case 'PENDING_DECISION_APPROVED':return { category: 'Decision',  label: 'Pending decision approved', tone: 'emerald' };
    case 'PENDING_DECISION_REJECTED':return { category: 'Decision',  label: 'Pending decision rejected', tone: 'red'     };
    case 'SIGNAL_GENERATED':         return { category: 'Signal',    label: 'Signal generated',          tone: 'gray'    };
    case 'POSITION_OPENED':          return { category: 'Position',  label: 'Position opened',           tone: 'emerald' };
    case 'POSITION_CLOSED':          return { category: 'Position',  label: 'Position closed',           tone: 'gray'    };
    case 'RISK_BLOCKED':             return { category: 'Risk',      label: 'Risk blocked trade',        tone: 'red'     };
    case 'RISK_RESET':               return { category: 'Risk',      label: 'Risk state reset',          tone: 'blue'    };
    default: {
      // Generic fallback — humanise enum to title case, no shout.
      const label = String(type || '')
        .toLowerCase()
        .replace(/_/g, ' ')
        .replace(/^./, (c) => c.toUpperCase());
      // Best-effort category guess from prefix.
      const upper = String(type || '').toUpperCase();
      const category =
        upper.startsWith('DECISION') ? 'Decision'
      : upper.startsWith('SIGNAL')   ? 'Signal'
      : upper.startsWith('POSITION') ? 'Position'
      : upper.startsWith('RISK')     ? 'Risk'
      : upper.startsWith('ORDER')    ? 'Execution'
      : '—';
      return { category, label, tone: 'gray' };
    }
  }
}

// Cleanup 2026-05-01: flat monochrome category labels — no tinted pill
// backgrounds. Semantic colour stays in the text only.
const CATEGORY_TONE = {
  Decision:  'text-emerald-700',
  Signal:    'text-amber-700',
  Position:  'text-indigo-700',
  Risk:      'text-red-700',
  Execution: 'text-slate-600',
  '—':       'text-slate-400',
};

const TEXT_TONE = {
  emerald: 'text-emerald-700',
  red:     'text-red-700',
  blue:    'text-blue-700',
  gray:    'text-slate-700',
};

function formatTime(ts) {
  if (!ts) return '—';
  try {
    const d = new Date(ts);
    if (Number.isNaN(d.getTime())) return '—';
    return d.toLocaleTimeString('en-GB', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    });
  } catch (_e) {
    return '—';
  }
}

function stripUsdt(symbol) {
  if (!symbol) return '';
  return String(symbol).replace(/USDT$/i, '');
}

export default function ExecutionFeed() {
  const [events, setEvents] = useState([]);

  useEffect(() => {
    let alive = true;
    const fetchEvents = async () => {
      try {
        const res = await fetch(`${API_URL}/api/execution/feed?limit=20`);
        const data = await res.json();
        if (alive) setEvents(data.feed || []);
      } catch (_err) { /* silent */ }
    };
    fetchEvents();
    const interval = setInterval(fetchEvents, 3000);
    return () => { alive = false; clearInterval(interval); };
  }, []);

  return (
    <div className="px-4 py-2.5" data-testid="execution-feed">
      <div className="flex items-center gap-2 mb-1.5">
        <span className="text-xs font-semibold text-gray-700">Activity</span>
        <span
          className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"
          aria-hidden
        />
      </div>

      {events.length === 0 ? (
        <p className="text-xs text-gray-500">
          Quiet for now. New decisions and fills will appear here in real time.
        </p>
      ) : (
        <ul className="space-y-1">
          {events.slice(0, 6).map((e, i) => {
            const desc = describeEvent(e.type);
            return (
              <li
                key={e.event_id || i}
                className="flex items-center gap-3 text-xs"
                style={{ fontVariantNumeric: 'tabular-nums' }}
              >
                <span className="w-[44px] flex-shrink-0 text-gray-400">
                  {formatTime(e.timestamp)}
                </span>
                <span
                  className={`flex-shrink-0 text-[10px] font-semibold uppercase tracking-wider ${
                    CATEGORY_TONE[desc.category] || CATEGORY_TONE['—']
                  }`}
                >
                  {desc.category}
                </span>
                <span className="flex-shrink-0 w-[60px] font-medium text-gray-900">
                  {stripUsdt(e.symbol)}
                </span>
                <span className={`font-medium ${TEXT_TONE[desc.tone]}`}>
                  {desc.label}
                </span>
                {e.fill_price && (
                  <span className="text-gray-500">@ ${e.fill_price}</span>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
