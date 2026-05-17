/**
 * Network Alpha Evidence Table
 * Shows tokens where channel was an early source
 * Block UI-4: Institutional evidence for NetworkAlphaScore
 */
import { useState, useMemo } from 'react';
import { TrendingUp, TrendingDown, Clock, Award, ChevronDown, ChevronUp, Zap } from 'lucide-react';

const formatPercent = (val) => {
  if (val === null || val === undefined) return '—';
  const sign = val >= 0 ? '+' : '';
  return `${sign}${val.toFixed(1)}%`;
};

const formatDate = (dateStr) => {
  if (!dateStr) return '—';
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
};

function roiColor(v) {
  if (v >= 20) return 'text-emerald-600';
  if (v >= 0) return 'text-neutral-700';
  return 'text-rose-600';
}

function percentileColor(p) {
  if (p <= 0.1) return 'bg-emerald-50 text-emerald-700 border-emerald-200';
  if (p <= 0.25) return 'bg-blue-50 text-blue-700 border-blue-200';
  return 'bg-neutral-50 text-neutral-600 border-neutral-200';
}

function RankBadge({ rank, cohortSize }) {
  const isFirst = rank === 1;
  return (
    <div className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${
      isFirst ? 'bg-amber-50 text-amber-700 border border-amber-200' : 'bg-neutral-50 text-neutral-600'
    }`}>
      {isFirst && <Award className="w-3 h-3" />}
      <span>{rank}</span>
      <span className="text-neutral-400">/</span>
      <span className="text-neutral-500">{cohortSize}</span>
    </div>
  );
}

export default function NetworkEvidenceTable({ 
  data, 
  loading = false,
  maxRows = 25 
}) {
  const [sortBy, setSortBy] = useState('percentile');
  const [sortDir, setSortDir] = useState('asc');

  const sortedItems = useMemo(() => {
    if (!data?.items) return [];
    
    return [...data.items].sort((a, b) => {
      let aVal, bVal;
      
      switch (sortBy) {
        case 'token':
          aVal = a.token;
          bVal = b.token;
          break;
        case 'return7d':
          aVal = a.return7d ?? -Infinity;
          bVal = b.return7d ?? -Infinity;
          break;
        case 'earlyRank':
          aVal = a.earlyRank;
          bVal = b.earlyRank;
          break;
        case 'percentile':
        default:
          aVal = a.percentile;
          bVal = b.percentile;
      }
      
      if (typeof aVal === 'string') {
        return sortDir === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
      }
      return sortDir === 'asc' ? aVal - bVal : bVal - aVal;
    }).slice(0, maxRows);
  }, [data?.items, sortBy, sortDir, maxRows]);

  const handleSort = (col) => {
    if (sortBy === col) {
      setSortDir(prev => prev === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(col);
      setSortDir(col === 'return7d' ? 'desc' : 'asc');
    }
  };

  const SortHeader = ({ column, label }) => (
    <button
      onClick={() => handleSort(column)}
      className="flex items-center gap-1 text-xs font-medium text-neutral-500 hover:text-neutral-700 transition-colors"
      data-testid={`sort-evidence-${column}`}
    >
      {label}
      {sortBy === column && (
        sortDir === 'desc' ? <ChevronDown className="w-3 h-3" /> : <ChevronUp className="w-3 h-3" />
      )}
    </button>
  );

  if (loading) {
    return (
      <div className="bg-white rounded-xl border border-neutral-200 p-6">
        <div className="flex items-center justify-center py-12">
          <div className="w-6 h-6 border-2 border-neutral-200 border-t-neutral-600 rounded-full animate-spin" />
        </div>
      </div>
    );
  }

  if (!data || !data.items?.length) {
    return (
      <div className="bg-white rounded-xl border border-neutral-200 p-6" data-testid="network-evidence-empty">
        <div className="flex flex-col items-center justify-center py-8 text-center">
          <Zap className="w-8 h-8 text-neutral-300 mb-2" />
          <h3 className="text-sm font-medium text-neutral-700">No Network Alpha Evidence</h3>
          <p className="text-xs text-neutral-400 mt-1">
            This channel hasn't been an early source for successful tokens
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-neutral-200" data-testid="network-evidence-table">
      {/* Header with Summary */}
      <div className="px-5 py-4 border-b border-neutral-100">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-neutral-900">Network Alpha Evidence</h3>
            <p className="text-xs text-neutral-500 mt-0.5">
              Tokens where this channel was an early source
            </p>
          </div>
          
          {data.summary && (
            <div className="flex items-center gap-4 text-sm">
              <div className="text-right">
                <div className="text-xs text-neutral-400">Tokens</div>
                <div className="font-semibold text-neutral-900">{data.summary.totalTokens}</div>
              </div>
              <div className="text-right">
                <div className="text-xs text-neutral-400">First Places</div>
                <div className="font-semibold text-amber-600">{data.summary.firstPlaces}</div>
              </div>
              {data.summary.avgPercentile !== null && (
                <div className="text-right">
                  <div className="text-xs text-neutral-400">Avg Percentile</div>
                  <div className={`font-semibold ${data.summary.avgPercentile <= 0.1 ? 'text-emerald-600' : 'text-neutral-700'}`}>
                    {(data.summary.avgPercentile * 100).toFixed(0)}%
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="border-b border-neutral-100">
            <tr className="text-neutral-600">
              <th className="px-5 py-3 text-left">
                <SortHeader column="token" label="Token" />
              </th>
              <th className="px-5 py-3 text-center">
                <SortHeader column="earlyRank" label="Early Rank" />
              </th>
              <th className="px-5 py-3 text-center">
                <span className="text-xs font-medium text-neutral-500">Delay</span>
              </th>
              <th className="px-5 py-3 text-center">
                <SortHeader column="percentile" label="Percentile" />
              </th>
              <th className="px-5 py-3 text-center">
                <SortHeader column="return7d" label="7d ROI" />
              </th>
              <th className="px-5 py-3 text-center">
                <span className="text-xs font-medium text-neutral-500">Cohort</span>
              </th>
            </tr>
          </thead>

          <tbody>
            {sortedItems.map((row, i) => (
              <tr 
                key={`${row.token}-${i}`}
                className="border-b border-neutral-50 hover:bg-neutral-50/50 transition-colors"
                data-testid={`evidence-row-${i}`}
              >
                <td className="px-5 py-3">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-neutral-900">${row.token}</span>
                    {row.isHit && (
                      <TrendingUp className="w-3.5 h-3.5 text-emerald-500" />
                    )}
                  </div>
                </td>

                <td className="px-5 py-3 text-center">
                  <RankBadge rank={row.earlyRank} cohortSize={row.cohortSize} />
                </td>

                <td className="px-5 py-3 text-center">
                  <div className="flex items-center justify-center gap-1 text-neutral-600">
                    <Clock className="w-3.5 h-3.5 text-neutral-400" />
                    <span>{row.delayHours}h</span>
                  </div>
                </td>

                <td className="px-5 py-3 text-center">
                  <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium border ${percentileColor(row.percentile)}`}>
                    {(row.percentile * 100).toFixed(0)}%
                  </span>
                </td>

                <td className={`px-5 py-3 text-center font-semibold ${roiColor(row.return7d)}`}>
                  {formatPercent(row.return7d)}
                </td>

                <td className="px-5 py-3 text-center text-neutral-500">
                  {row.cohortSize}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Footer */}
      <div className="px-5 py-3 border-t border-neutral-100 bg-neutral-50/30">
        <div className="text-xs text-neutral-500">
          Showing {sortedItems.length} of {data.count} tokens • Lower percentile = earlier than others
        </div>
      </div>
    </div>
  );
}
