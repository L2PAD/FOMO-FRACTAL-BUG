import React from 'react';
import { Layers, TrendingUp, AlertCircle, Ban } from 'lucide-react';

const MetaLayerBlock = ({ meta, meta_execution }) => {
  if (!meta) {
    return (
      <div className="bg-[#0A0E13] border border-gray-800 rounded-lg p-4">
        <div className="text-sm text-gray-500">Meta layer data unavailable</div>
      </div>
    );
  }

  const allocations = meta?.allocations || [];
  const actions = meta?.actions || [];
  const currentStrategy = meta_execution?.strategy_id || 'unknown';
  const currentUsage = meta_execution?.strategy_usage || 0;
  const currentAllocated = meta_execution?.allocated_capital || 0;
  const currentPolicy = meta_execution?.strategy_policy || {};

  // Group actions by strategy
  const actionsByStrategy = {};
  actions.forEach(action => {
    const sid = action.strategy_id;
    if (!actionsByStrategy[sid]) actionsByStrategy[sid] = [];
    actionsByStrategy[sid].push(action.type);
  });

  // Get policy icon and color
  const getPolicyBadge = (strategyId, allocation) => {
    const strategyActions = actionsByStrategy[strategyId] || [];
    
    if (strategyActions.includes('DISABLE_STRATEGY')) {
      return { icon: <Ban className="w-3 h-3" />, text: 'DISABLED', color: 'text-red-500 bg-red-500/10' };
    }
    if (strategyActions.includes('BOOST_STRATEGY')) {
      return { icon: <TrendingUp className="w-3 h-3" />, text: 'BOOST', color: 'text-green-500 bg-green-500/10' };
    }
    if (strategyActions.includes('CAP_STRATEGY')) {
      return { icon: <AlertCircle className="w-3 h-3" />, text: 'CAP', color: 'text-amber-500 bg-amber-500/10' };
    }
    
    return null;
  };

  return (
    <div className="bg-[#0A0E13] border border-gray-800 rounded-lg p-4" data-testid="meta-layer-block">
      {/* Header */}
      <div className="flex items-center gap-2 mb-4">
        <Layers className="w-4 h-4 text-purple-400" />
        <span className="text-sm font-medium text-gray-300">Meta Layer</span>
        <span className="ml-auto text-xs text-gray-600">
          {allocations.length} strategies
        </span>
      </div>

      {/* Current Strategy */}
      {currentStrategy !== 'unknown' && (
        <div className="mb-3 pb-3 border-b border-gray-800">
          <div className="text-xs text-gray-500 mb-1">Active Strategy</div>
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-white">{currentStrategy}</span>
            {currentPolicy.disabled && (
              <span className="text-xs px-1.5 py-0.5 rounded bg-red-500/10 text-red-500 flex items-center gap-1">
                <Ban className="w-3 h-3" />
                DISABLED
              </span>
            )}
            {currentPolicy.boosted && !currentPolicy.disabled && (
              <span className="text-xs px-1.5 py-0.5 rounded bg-green-500/10 text-green-500 flex items-center gap-1">
                <TrendingUp className="w-3 h-3" />
                BOOST
              </span>
            )}
            {currentPolicy.capped && !currentPolicy.disabled && !currentPolicy.boosted && (
              <span className="text-xs px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-500 flex items-center gap-1">
                <AlertCircle className="w-3 h-3" />
                CAP
              </span>
            )}
          </div>
          {currentAllocated > 0 && (
            <div className="mt-1 text-xs text-gray-600">
              Usage: ${currentUsage.toLocaleString()} / ${currentAllocated.toLocaleString()}
            </div>
          )}
        </div>
      )}

      {/* Strategy Allocations */}
      <div className="space-y-2">
        {allocations.slice(0, 4).map((alloc) => {
          const badge = getPolicyBadge(alloc.strategy_id, alloc);
          
          return (
            <div key={alloc.strategy_id} className="flex items-center justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-400">{alloc.strategy_id}</span>
                  {badge && (
                    <span className={`text-xs px-1.5 py-0.5 rounded flex items-center gap-1 ${badge.color}`}>
                      {badge.icon}
                      {badge.text}
                    </span>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="text-xs text-gray-600">
                  score: <span className="text-gray-400">{alloc.score?.toFixed(2) || '0.00'}</span>
                </div>
                <div className="text-xs font-medium text-white">
                  {(alloc.weight * 100).toFixed(0)}%
                </div>
                <div className="text-xs text-gray-500 w-16 text-right">
                  ${(alloc.capital || 0).toLocaleString('en-US', { maximumFractionDigits: 0 })}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {allocations.length > 4 && (
        <div className="mt-2 text-xs text-gray-600 text-center">
          +{allocations.length - 4} more strategies
        </div>
      )}
    </div>
  );
};

export default MetaLayerBlock;
