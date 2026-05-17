/**
 * WatchlistTable Component (BLOCK 5.1 UI)
 * Displays user's watchlist with current scores and changes
 */
import React from 'react';
import { Link } from 'react-router-dom';
import { Star, TrendingUp, TrendingDown, Minus, Trash2, ExternalLink } from 'lucide-react';
import { Button } from '../ui/button';

function getTierColor(tier) {
  const colors = {
    S: 'text-purple-400 bg-purple-500/20',
    A: 'text-blue-400 bg-blue-500/20',
    B: 'text-green-400 bg-green-500/20',
    C: 'text-yellow-400 bg-yellow-500/20',
    D: 'text-red-400 bg-red-500/20',
  };
  return colors[tier] || 'text-gray-400 bg-gray-500/20';
}

function TrendIcon({ trend }) {
  if (trend === 'RISING') return <TrendingUp className="h-4 w-4 text-green-400" />;
  if (trend === 'FALLING') return <TrendingDown className="h-4 w-4 text-red-400" />;
  return <Minus className="h-4 w-4 text-gray-400" />;
}

function DeltaBadge({ delta, suffix = '' }) {
  if (delta == null) return <span className="text-gray-500">—</span>;
  
  const isPositive = delta > 0;
  const isNegative = delta < 0;
  
  return (
    <span className={`text-sm font-medium ${
      isPositive ? 'text-green-400' : isNegative ? 'text-red-400' : 'text-gray-400'
    }`}>
      {isPositive ? '+' : ''}{delta.toFixed(1)}{suffix}
    </span>
  );
}

export function WatchlistTable({ items, onRemove, loading }) {
  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-amber-500" />
      </div>
    );
  }

  if (!items || items.length === 0) {
    return (
      <div className="text-center py-12 text-gray-400" data-testid="watchlist-empty">
        <Star className="h-12 w-12 mx-auto mb-4 opacity-30" />
        <p className="text-lg mb-2">Ваш список наблюдения пуст</p>
        <p className="text-sm">Добавьте каналы, чтобы отслеживать их показатели</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto" data-testid="watchlist-table">
      <table className="w-full">
        <thead>
          <tr className="border-b border-gray-800 text-left text-sm text-gray-400">
            <th className="pb-3 pr-4">Канал</th>
            <th className="pb-3 px-4 text-center">Tier</th>
            <th className="pb-3 px-4 text-right">Intel</th>
            <th className="pb-3 px-4 text-right">Δ Intel</th>
            <th className="pb-3 px-4 text-right">Momentum</th>
            <th className="pb-3 px-4 text-right">Δ Momentum</th>
            <th className="pb-3 px-4 text-center">Trend</th>
            <th className="pb-3 px-4 text-right">Добавлен</th>
            <th className="pb-3 pl-4"></th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr
              key={item.username}
              className="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors"
              data-testid={`watchlist-row-${item.username}`}
            >
              <td className="py-4 pr-4">
                <Link
                  to={`/telegram/${item.username}`}
                  className="flex items-center gap-2 hover:text-amber-400 transition-colors"
                >
                  <Star className="h-4 w-4 text-amber-500 fill-amber-500" />
                  <span className="font-medium">@{item.username}</span>
                  <ExternalLink className="h-3 w-3 opacity-50" />
                </Link>
                {item.note && (
                  <p className="text-xs text-gray-500 mt-1 ml-6">{item.note}</p>
                )}
                {item.tags?.length > 0 && (
                  <div className="flex gap-1 mt-1 ml-6">
                    {item.tags.map((tag) => (
                      <span
                        key={tag}
                        className="text-xs px-1.5 py-0.5 bg-gray-700 rounded text-gray-300"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
              </td>
              <td className="py-4 px-4 text-center">
                <span className={`px-2 py-1 rounded text-xs font-bold ${getTierColor(item.currentScores?.tier)}`}>
                  {item.currentScores?.tier || '—'}
                </span>
              </td>
              <td className="py-4 px-4 text-right font-mono">
                {item.currentScores?.intelScore != null
                  ? item.currentScores.intelScore.toFixed(1)
                  : '—'}
              </td>
              <td className="py-4 px-4 text-right">
                <DeltaBadge delta={item.changes?.intelDelta} />
              </td>
              <td className="py-4 px-4 text-right font-mono">
                {item.currentScores?.momentumScore != null
                  ? item.currentScores.momentumScore.toFixed(1)
                  : '—'}
              </td>
              <td className="py-4 px-4 text-right">
                <DeltaBadge delta={item.changes?.momentumDelta} />
              </td>
              <td className="py-4 px-4 text-center">
                <TrendIcon trend={item.currentScores?.trend} />
              </td>
              <td className="py-4 px-4 text-right text-sm text-gray-400">
                {new Date(item.addedAt).toLocaleDateString('ru-RU')}
              </td>
              <td className="py-4 pl-4">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onRemove?.(item.username)}
                  className="text-gray-400 hover:text-red-400"
                  data-testid={`watchlist-remove-${item.username}`}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default WatchlistTable;
