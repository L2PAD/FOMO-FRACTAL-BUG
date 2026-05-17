/**
 * MarketsTab — colored filter labels, status filter.
 */
import { useState, useEffect } from 'react';
import MarketCard from './MarketCard';
import { fillIfEmpty } from '../../adapters/uiCase.adapter';

const FILTERS = [
  { key: 'all',    label: 'All',     color: 'text-gray-700' },
  { key: 'entry',  label: 'Entry',   color: 'text-emerald-600' },
  { key: 'moving', label: 'Moving',  color: 'text-blue-600' },
  { key: 'watch',  label: 'Watch',   color: 'text-gray-500' },
  { key: 'avoid',  label: 'Avoid',   color: 'text-red-500' },
];

export default function MarketsTab({ uiCases, grouped, initialFilter }) {
  const [filter, setFilter] = useState(initialFilter || 'all');

  useEffect(() => {
    if (initialFilter) setFilter(initialFilter);
  }, [initialFilter]);

  const filtered = filter === 'all' ? uiCases : grouped[filter] || [];
  const displayed = filter !== 'all' && filter !== 'watch' && filter !== 'avoid'
    ? fillIfEmpty(filtered, grouped.watch || [], 3)
    : filtered;

  return (
    <div className="px-6 py-5 space-y-4" data-testid="markets-tab">
      <div className="flex items-center gap-1" data-testid="market-filters">
        {FILTERS.map(f => {
          const count = f.key === 'all' ? uiCases.length : (grouped[f.key]?.length || 0);
          const isActive = filter === f.key;
          return (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              data-testid={`filter-${f.key}`}
              className={`px-3 py-1.5 text-sm font-medium rounded-lg transition-all ${
                isActive
                  ? 'bg-gray-900 text-white'
                  : `${f.color} hover:bg-gray-100`
              }`}
            >
              {f.label}
              <span className={`ml-1 text-xs ${isActive ? 'text-gray-300' : 'opacity-60'}`}>{count}</span>
            </button>
          );
        })}
      </div>

      {displayed.length > 0 ? (
        <div className="bg-white rounded-lg border border-gray-200/60">
          {displayed.map(c => <MarketCard key={c.id} c={c} />)}
        </div>
      ) : (
        <p className="text-sm text-gray-400 py-6">No markets in this category</p>
      )}
    </div>
  );
}
