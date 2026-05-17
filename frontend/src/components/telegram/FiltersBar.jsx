/**
 * Telegram Filters Bar
 * URL-synced filters for leaderboard
 */
import { useState, useEffect } from 'react';
import { Search, Filter, SlidersHorizontal } from 'lucide-react';

export default function FiltersBar({ filters, onChange }) {
  const [search, setSearch] = useState(filters?.search || '');

  useEffect(() => {
    const timer = setTimeout(() => {
      if (search !== filters?.search) {
        onChange({ ...filters, search });
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  const handleTierChange = (e) => {
    onChange({ ...filters, tier: e.target.value || undefined });
  };

  const handleSortChange = (e) => {
    onChange({ ...filters, sort: e.target.value });
  };

  const handleMaxFraudChange = (e) => {
    const val = e.target.value;
    onChange({ ...filters, maxFraud: val ? Number(val) : undefined });
  };

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4" data-testid="filters-bar">
      <div className="flex flex-wrap items-center gap-3">
        {/* Search */}
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search channel..."
            className="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            data-testid="filter-search"
          />
        </div>

        {/* Tier Filter */}
        <select
          value={filters?.tier || ''}
          onChange={handleTierChange}
          className="px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500"
          data-testid="filter-tier"
        >
          <option value="">All Tiers</option>
          <option value="S">S Tier</option>
          <option value="A">A Tier</option>
          <option value="B">B Tier</option>
          <option value="C">C Tier</option>
          <option value="D">D Tier</option>
        </select>

        {/* Sort */}
        <select
          value={filters?.sort || 'intelScore'}
          onChange={handleSortChange}
          className="px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500"
          data-testid="filter-sort"
        >
          <option value="intelScore">Intel Score</option>
          <option value="alphaScore">Alpha Score</option>
          <option value="credibilityScore">Credibility</option>
          <option value="networkAlphaScore">Network Alpha</option>
        </select>

        {/* Max Fraud */}
        <select
          value={filters?.maxFraud ?? ''}
          onChange={handleMaxFraudChange}
          className="px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500"
          data-testid="filter-fraud"
        >
          <option value="">Any Fraud Risk</option>
          <option value="0.25">Low Fraud (&lt;25%)</option>
          <option value="0.5">Medium (&lt;50%)</option>
          <option value="0.75">High (&lt;75%)</option>
        </select>
      </div>
    </div>
  );
}
