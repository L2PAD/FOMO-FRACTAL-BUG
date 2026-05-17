import React from 'react';
import { ShieldAlert, Ban, TrendingDown, Lock } from 'lucide-react';

const GuardActionsBlock = ({ actions }) => {
  if (!actions || actions.length === 0) {
    return (
      <div className="bg-[#0A0E13] border border-gray-800 rounded-lg p-4" data-testid="guard-actions-block">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-cyan-400" />
            <span className="text-sm font-medium text-gray-300">Risk Guard Actions</span>
          </div>
          <div className="text-xs text-green-500 font-medium">CLEAR</div>
        </div>
        <div className="text-xs text-gray-500">No active risk guard actions</div>
      </div>
    );
  }

  // Icon mapping для каждого типа action
  const getActionIcon = (action) => {
    switch (action) {
      case "HARD_STOP":
        return Ban;
      case "CLOSE_ALL":
        return Ban;
      case "REDUCE_SIZE":
        return TrendingDown;
      case "FREEZE_WEAK_STRATEGIES":
        return Lock;
      default:
        return ShieldAlert;
    }
  };

  // Color mapping
  const getActionColor = (action) => {
    if (action === "HARD_STOP" || action === "CLOSE_ALL") {
      return "text-red-500 bg-red-950/30 border-red-800";
    }
    if (action === "REDUCE_SIZE" || action === "FREEZE_WEAK_STRATEGIES") {
      return "text-amber-500 bg-amber-950/20 border-amber-800";
    }
    return "text-gray-400 bg-gray-900/50 border-gray-700";
  };

  // Сортировка actions (CRITICAL первыми)
  const sortedActions = [...actions].sort((a, b) => {
    const priority = {
      "HARD_STOP": 0,
      "CLOSE_ALL": 1,
      "REDUCE_SIZE": 2,
      "FREEZE_WEAK_STRATEGIES": 3
    };
    return (priority[a] || 99) - (priority[b] || 99);
  });

  return (
    <div className="bg-[#0A0E13] border border-gray-800 rounded-lg p-4" data-testid="guard-actions-block">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <ShieldAlert className="w-4 h-4 text-cyan-400" />
          <span className="text-sm font-medium text-gray-300">Risk Guard Actions</span>
        </div>
        <div className="text-xs text-red-500 font-bold">
          {sortedActions.length} ACTIVE
        </div>
      </div>

      {/* Actions List */}
      <div className="space-y-2">
        {sortedActions.map((action, idx) => {
          const Icon = getActionIcon(action);
          const colorClass = getActionColor(action);
          
          return (
            <div
              key={idx}
              className={`flex items-center gap-2 px-3 py-2 rounded border ${colorClass}`}
              data-testid={`guard-action-${action.toLowerCase()}`}
            >
              <Icon className="w-4 h-4" />
              <span className="text-sm font-medium">{action.replace(/_/g, ' ')}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default GuardActionsBlock;
