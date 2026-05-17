/**
 * Token Mentions Table
 * Displays channel's token mentions with performance returns
 * Light institutional style
 */
import { useState, useMemo } from 'react';
import { TrendingUp, TrendingDown, Clock, ExternalLink, ChevronDown, ChevronUp, AlertCircle } from 'lucide-react';

const formatPercent = (val) => {
  if (val === null || val === undefined) return '—';
  const sign = val >= 0 ? '+' : '';
  return `${sign}${val.toFixed(1)}%`;
};

const formatDate = (dateStr) => {
  if (!dateStr) return '—';
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
};

const ReturnBadge = ({ value, label }) => {
  if (value === null || value === undefined) {
    return <span className="text-xs text-gray-400">—</span>;
  }
  
  const isPositive = value > 0;
  const bgColor = isPositive ? 'bg-emerald-50' : value < 0 ? 'bg-rose-50' : 'bg-gray-50';
  const textColor = isPositive ? 'text-emerald-700' : value < 0 ? 'text-rose-700' : 'text-gray-600';
  
  return (
    <div className={`inline-flex items-center gap-1 px-2 py-0.5 rounded ${bgColor}`}>
      {isPositive ? (
        <TrendingUp className="w-3 h-3 text-emerald-500" />
      ) : value < 0 ? (
        <TrendingDown className="w-3 h-3 text-rose-500" />
      ) : null}
      <span className={`text-xs font-medium ${textColor}`}>
        {formatPercent(value)}
      </span>
      {label && <span className="text-xs text-gray-400 ml-0.5">{label}</span>}
    </div>
  );
};

export default function TokenMentionsTable({ 
  data, 
  loading = false,
  showSummary = true,
  maxRows = 50 
}) {
  const [sortBy, setSortBy] = useState('mentionedAt');
  const [sortDir, setSortDir] = useState('desc');
  const [expandedToken, setExpandedToken] = useState(null);

  // Process and sort mentions
  const sortedMentions = useMemo(() => {
    if (!data?.mentions) return [];
    
    return [...data.mentions].sort((a, b) => {
      let aVal, bVal;
      
      switch (sortBy) {
        case 'token':
          aVal = a.token;
          bVal = b.token;
          break;
        case 'r7d':
          aVal = a.returns?.r7d ?? -Infinity;
          bVal = b.returns?.r7d ?? -Infinity;
          break;
        case 'max7d':
          aVal = a.returns?.max7d ?? -Infinity;
          bVal = b.returns?.max7d ?? -Infinity;
          break;
        case 'mentionedAt':
        default:
          aVal = new Date(a.mentionedAt).getTime();
          bVal = new Date(b.mentionedAt).getTime();
      }
      
      if (typeof aVal === 'string') {
        return sortDir === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
      }
      return sortDir === 'asc' ? aVal - bVal : bVal - aVal;
    }).slice(0, maxRows);
  }, [data?.mentions, sortBy, sortDir, maxRows]);

  const handleSort = (col) => {
    if (sortBy === col) {
      setSortDir(prev => prev === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(col);
      setSortDir('desc');
    }
  };

  const SortHeader = ({ column, label }) => (
    <button
      onClick={() => handleSort(column)}
      className="flex items-center gap-1 text-xs font-medium text-gray-500 hover:text-gray-700 transition-colors"
      data-testid={`sort-${column}`}
    >
      {label}
      {sortBy === column && (
        sortDir === 'desc' ? <ChevronDown className="w-3 h-3" /> : <ChevronUp className="w-3 h-3" />
      )}
    </button>
  );

  if (loading) {
    return (
      <div className="bg-white rounded-xl border border-gray-100 p-6">
        <div className="flex items-center justify-center py-12">
          <div className="w-6 h-6 border-2 border-gray-200 border-t-gray-600 rounded-full animate-spin" />
        </div>
      </div>
    );
  }

  if (!data || data.total === 0) {
    return (
      <div className="bg-white rounded-xl border border-gray-100 p-6" data-testid="mentions-empty">
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <AlertCircle className="w-10 h-10 text-gray-300 mb-3" />
          <h3 className="text-sm font-medium text-gray-700">No Token Mentions</h3>
          <p className="text-xs text-gray-400 mt-1">
            This channel hasn't mentioned any tokens in the selected period
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-gray-100" data-testid="token-mentions-table">
      {/* Summary Stats */}
      {showSummary && (
        <div className="px-5 py-4 border-b border-gray-100">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-gray-900">Token Mentions</h3>
              <p className="text-xs text-gray-500 mt-0.5">
                {data.total} mentions • {data.evaluated} evaluated
              </p>
            </div>
            <div className="flex items-center gap-4">
              {data.avgReturn7d !== null && (
                <div className="text-right">
                  <div className="text-xs text-gray-400">Avg 7d Return</div>
                  <ReturnBadge value={data.avgReturn7d} />
                </div>
              )}
              {data.hitRate !== null && (
                <div className="text-right">
                  <div className="text-xs text-gray-400">Hit Rate</div>
                  <span className={`text-sm font-medium ${data.hitRate >= 0.5 ? 'text-emerald-600' : 'text-gray-600'}`}>
                    {(data.hitRate * 100).toFixed(0)}%
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Top Tokens Summary */}
      {data.topTokens?.length > 0 && (
        <div className="px-5 py-3 border-b border-gray-50 bg-gray-50/50">
          <div className="flex flex-wrap gap-2">
            {data.topTokens.slice(0, 8).map((t) => (
              <button
                key={t.token}
                onClick={() => setExpandedToken(expandedToken === t.token ? null : t.token)}
                className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs transition-all ${
                  expandedToken === t.token 
                    ? 'bg-gray-900 text-white' 
                    : 'bg-white border border-gray-200 text-gray-700 hover:border-gray-300'
                }`}
                data-testid={`token-badge-${t.token}`}
              >
                <span className="font-medium">${t.token}</span>
                <span className="opacity-60">{t.mentionCount}</span>
                {t.avgReturn7d !== null && (
                  <span className={t.avgReturn7d >= 0 ? 'text-emerald-400' : 'text-rose-400'}>
                    {formatPercent(t.avgReturn7d)}
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-100">
              <th className="px-5 py-3 text-left">
                <SortHeader column="token" label="Token" />
              </th>
              <th className="px-5 py-3 text-left">
                <SortHeader column="mentionedAt" label="Date" />
              </th>
              <th className="px-5 py-3 text-right">
                <SortHeader column="r7d" label="7d Return" />
              </th>
              <th className="px-5 py-3 text-right">
                <SortHeader column="max7d" label="Max 7d" />
              </th>
              <th className="px-5 py-3 text-left">
                <span className="text-xs font-medium text-gray-500">Source</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {sortedMentions
              .filter(m => !expandedToken || m.token === expandedToken)
              .map((mention, idx) => (
                <tr 
                  key={`${mention.token}-${mention.messageId}-${idx}`}
                  className="border-b border-gray-50 hover:bg-gray-50/50 transition-colors"
                  data-testid={`mention-row-${idx}`}
                >
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-gray-900">${mention.token}</span>
                      {mention.context?.confidence >= 0.8 && (
                        <span className="px-1.5 py-0.5 bg-blue-50 text-blue-600 text-[10px] font-medium rounded">
                          HIGH
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-1.5 text-sm text-gray-600">
                      <Clock className="w-3.5 h-3.5 text-gray-400" />
                      {formatDate(mention.mentionedAt)}
                    </div>
                  </td>
                  <td className="px-5 py-3 text-right">
                    <ReturnBadge value={mention.returns?.r7d} />
                  </td>
                  <td className="px-5 py-3 text-right">
                    <ReturnBadge value={mention.returns?.max7d} />
                  </td>
                  <td className="px-5 py-3">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs ${
                      mention.context?.source === 'cashtag' 
                        ? 'bg-purple-50 text-purple-600' 
                        : mention.context?.source === 'hashtag'
                        ? 'bg-blue-50 text-blue-600'
                        : 'bg-gray-50 text-gray-600'
                    }`}>
                      {mention.context?.source || 'plain'}
                    </span>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>

      {/* Footer */}
      <div className="px-5 py-3 border-t border-gray-100 bg-gray-50/30">
        <div className="flex items-center justify-between text-xs text-gray-500">
          <span>
            Showing {sortedMentions.filter(m => !expandedToken || m.token === expandedToken).length} of {data.total} mentions
          </span>
          {expandedToken && (
            <button 
              onClick={() => setExpandedToken(null)}
              className="text-blue-600 hover:text-blue-700"
            >
              Clear filter
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
