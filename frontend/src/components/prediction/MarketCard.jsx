/**
 * MarketCard — Compact Decision Card
 * Colored text for labels (no backgrounds/borders).
 * Hot signals get visual emphasis.
 */
import { useState } from 'react';
import { ChevronDown, ChevronRight, Flame } from 'lucide-react';
import MarketCardExpanded from './MarketCardExpanded';

export default function MarketCard({ c }) {
  const [open, setOpen] = useState(false);

  return (
    <div data-testid={`case-${c.id}`}>
      <div
        className={`px-6 py-4 flex items-start gap-4 cursor-pointer transition-colors ${open ? 'bg-gray-50' : 'hover:bg-gray-50/50'}`}
        onClick={() => setOpen(!open)}
        data-testid={`case-toggle-${c.id}`}
      >
        {/* Status — colored text */}
        <span
          data-testid={`status-${c.statusKey}`}
          className={`shrink-0 text-xs font-semibold uppercase tracking-wider mt-1 w-16 ${c.statusColor}`}
        >
          {c.statusLabel}
        </span>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            {c.isHot && <Flame className="w-3.5 h-3.5 text-amber-500 shrink-0" />}
            <h3 className={`text-sm font-medium leading-snug ${c.isHot ? 'text-gray-900' : 'text-gray-700'}`}>
              {c.question}
            </h3>
          </div>
          <p className={`text-sm mt-0.5 leading-relaxed ${c.isHot ? 'text-gray-600' : 'text-gray-500'}`}>
            {c.summary}
          </p>
          <div className="flex items-center gap-4 mt-1.5">
            <span className="text-xs text-gray-400">
              Edge: <span className={`font-medium ${c.edge.color}`}>{c.edge.text}</span>
            </span>
            <span className="text-xs text-gray-400">
              Confidence: <span className={`font-medium ${c.confidence.color}`}>{c.confidence.text}</span>
            </span>
            {c.entryType && (
              <span className="text-xs font-medium text-blue-600">{c.entryType}</span>
            )}
          </div>
        </div>

        {/* Action */}
        <div className="shrink-0 flex items-center gap-2 mt-0.5">
          <span
            data-testid={`action-btn-${c.id}`}
            className={`px-3 py-1.5 rounded-md text-xs font-medium ${
              c.statusKey === 'entry'
                ? 'bg-emerald-600 text-white'
                : c.statusKey === 'moving'
                ? 'bg-blue-600 text-white'
                : c.statusKey === 'avoid'
                ? 'bg-gray-200 text-gray-500'
                : 'bg-gray-900 text-white'
            }`}
          >
            {c.actionLabel}
          </span>
          <span className="text-gray-400">
            {open ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          </span>
        </div>
      </div>

      {open && <MarketCardExpanded c={c} />}
      <div className="border-b border-gray-100 mx-6" />
    </div>
  );
}
