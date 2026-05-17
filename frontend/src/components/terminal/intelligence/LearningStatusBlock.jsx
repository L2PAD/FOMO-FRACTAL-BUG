import React from 'react';
import { Brain, TrendingUp, AlertCircle, Ban, Zap } from 'lucide-react';

const LearningStatusBlock = ({ meta_learning, meta }) => {
  if (!meta_learning) {
    return (
      <div className="bg-[#0A0E13] border border-gray-800 rounded-lg p-4">
        <div className="text-sm text-gray-500">Learning data unavailable</div>
      </div>
    );
  }

  const alphaActions = meta_learning?.alpha_actions || [];
  const policyActions = meta_learning?.policy_actions || [];
  const isActive = meta_learning?.active_learning || false;

  // Get recent alpha actions (last 5)
  const recentAlphaActions = alphaActions.slice(0, 5);

  const getActionIcon = (actionType) => {
    switch (actionType) {
      case 'DISABLE_STRATEGY':
        return <Ban className="w-3 h-3" />;
      case 'BOOST_STRATEGY':
        return <TrendingUp className="w-3 h-3" />;
      case 'CAP_STRATEGY':
        return <AlertCircle className="w-3 h-3" />;
      case 'REDUCE_STRATEGY':
        return <Zap className="w-3 h-3" />;
      default:
        return <Brain className="w-3 h-3" />;
    }
  };

  const getActionColor = (actionType) => {
    switch (actionType) {
      case 'DISABLE_STRATEGY':
        return 'text-red-500 bg-red-500/10';
      case 'BOOST_STRATEGY':
        return 'text-green-500 bg-green-500/10';
      case 'CAP_STRATEGY':
        return 'text-amber-500 bg-amber-500/10';
      case 'REDUCE_STRATEGY':
        return 'text-blue-500 bg-blue-500/10';
      default:
        return 'text-gray-500 bg-gray-500/10';
    }
  };

  const formatReason = (reason) => {
    return reason
      .replace(/_/g, ' ')
      .replace(/\b\w/g, l => l.toUpperCase());
  };

  return (
    <div className="bg-[#0A0E13] border border-gray-800 rounded-lg p-4" data-testid="learning-status-block">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Brain className="w-4 h-4 text-cyan-400" />
          <span className="text-sm font-medium text-gray-300">Adaptive Intelligence</span>
        </div>
        <div className={`flex items-center gap-1.5 text-xs font-medium ${
          isActive ? 'text-cyan-400' : 'text-gray-600'
        }`}>
          {isActive ? (
            <>
              <Zap className="w-3.5 h-3.5" />
              ACTIVE
            </>
          ) : (
            'QUIET'
          )}
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        <div>
          <div className="text-xs text-gray-500">Alpha Actions</div>
          <div className="text-lg font-semibold text-white">{alphaActions.length}</div>
        </div>
        <div>
          <div className="text-xs text-gray-500">Policy Actions</div>
          <div className="text-lg font-semibold text-white">{policyActions.length}</div>
        </div>
      </div>

      {/* Recent Actions */}
      {recentAlphaActions.length > 0 ? (
        <div>
          <div className="text-xs text-gray-500 mb-2">Recent Learning Actions</div>
          <div className="space-y-1.5">
            {recentAlphaActions.map((action, idx) => (
              <div key={idx} className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className={`px-1.5 py-0.5 rounded flex items-center gap-1 ${getActionColor(action.type)}`}>
                    {getActionIcon(action.type)}
                    <span className="text-xs">
                      {action.type.replace('_STRATEGY', '').replace(/_/g, ' ')}
                    </span>
                  </span>
                  <span className="text-xs text-gray-400">{action.strategy_id}</span>
                </div>
                <div className="text-xs text-gray-600">
                  {formatReason(action.reason)}
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="text-center py-3">
          <div className="text-xs text-gray-600">No recent learning actions</div>
          <div className="text-xs text-gray-700 mt-1">System observing performance</div>
        </div>
      )}

      {/* Confidence note */}
      {recentAlphaActions.length > 0 && recentAlphaActions[0].confidence && (
        <div className="mt-3 pt-3 border-t border-gray-800 text-xs text-gray-600">
          Latest confidence: {(recentAlphaActions[0].confidence * 100).toFixed(0)}%
        </div>
      )}
    </div>
  );
};

export default LearningStatusBlock;
