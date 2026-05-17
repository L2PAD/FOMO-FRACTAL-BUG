import React from 'react';
import { Activity, ArrowDown, Move, Ban, TrendingUp } from 'lucide-react';

const LifecycleControlBlock = ({ lifecycle_control }) => {
  if (!lifecycle_control) {
    return (
      <div className="bg-[#0A0E13] border border-gray-800 rounded-lg p-4">
        <div className="text-sm text-gray-500">Lifecycle data unavailable</div>
      </div>
    );
  }

  const actions = lifecycle_control?.actions || [];
  const actionsCount = lifecycle_control?.actions_count || 0;
  const successCount = lifecycle_control?.success_count || 0;

  const getActionIcon = (actionType) => {
    switch (actionType) {
      case 'REDUCE_POSITION':
        return <ArrowDown className="w-3.5 h-3.5" />;
      case 'CLOSE_POSITION':
        return <Ban className="w-3.5 h-3.5" />;
      case 'TRAIL_STOP':
        return <TrendingUp className="w-3.5 h-3.5" />;
      case 'CANCEL_ORDER':
      case 'REPLACE_ORDER':
        return <Move className="w-3.5 h-3.5" />;
      default:
        return <Activity className="w-3.5 h-3.5" />;
    }
  };

  const getActionColor = (actionType) => {
    switch (actionType) {
      case 'REDUCE_POSITION':
        return 'text-amber-400';
      case 'CLOSE_POSITION':
        return 'text-red-400';
      case 'TRAIL_STOP':
        return 'text-green-400';
      case 'CANCEL_ORDER':
      case 'REPLACE_ORDER':
        return 'text-blue-400';
      default:
        return 'text-gray-400';
    }
  };

  const formatReason = (reason) => {
    return reason
      .replace(/_/g, ' ')
      .replace(/\b\w/g, l => l.toUpperCase());
  };

  return (
    <div className="bg-[#0A0E13] border border-gray-800 rounded-lg p-4" data-testid="lifecycle-control-block">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-emerald-400" />
          <span className="text-sm font-medium text-gray-300">Lifecycle Control</span>
        </div>
        <div className="text-xs text-gray-600">
          {successCount}/{actionsCount} executed
        </div>
      </div>

      {/* Actions */}
      {actions.length > 0 ? (
        <div className="space-y-2">
          {actions.map((action, idx) => (
            <div key={idx} className="flex items-start gap-2">
              <div className={`mt-0.5 ${getActionColor(action.action_type)}`}>
                {getActionIcon(action.action_type)}
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-medium text-white">
                    {action.target_id || 'Position'}
                  </span>
                  <span className={`text-xs ${getActionColor(action.action_type)}`}>
                    {action.action_type.replace(/_/g, ' ')}
                  </span>
                </div>
                <div className="text-xs text-gray-600">
                  {formatReason(action.reason)}
                </div>
                {action.payload && Object.keys(action.payload).length > 0 && (
                  <div className="text-xs text-gray-700 mt-0.5">
                    {action.payload.reduce_qty && `Reduce: ${action.payload.reduce_qty}`}
                    {action.payload.new_stop && `Stop: ${action.payload.new_stop}`}
                  </div>
                )}
              </div>
              <div className="text-xs text-gray-600">
                {action.priority}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center py-4">
          <div className="text-xs text-gray-600">No active lifecycle actions</div>
          <div className="text-xs text-gray-700 mt-1">System monitoring positions</div>
        </div>
      )}
    </div>
  );
};

export default LifecycleControlBlock;
