/**
 * Sprint 7.9: Adaptation Recommendations Panel
 * ============================================
 * 
 * Shows system-generated adaptation recommendations.
 * Operator must explicitly approve or reject.
 * 
 * CRITICAL INVARIANT:
 * System may recommend. Only operator may apply.
 * 
 * UI Requirements:
 * - Bucket name
 * - Actual vs Expected win rate
 * - Suggested change (current → new)
 * - Sample size
 * - Reason
 * - Apply/Reject buttons
 * 
 * Safety:
 * - Max 3 recommendations shown
 * - Sample size < 20 → Apply disabled
 * - Clear color coding (overestimation vs underestimation)
 */

import React, { useState } from 'react';
import { useAdaptationRecommendations } from '../../../hooks/adaptation/useAdaptationRecommendations';
import { useApplyAdaptation } from '../../../hooks/adaptation/useApplyAdaptation';

const MINIMUM_SAMPLE_SIZE = 20;

export default function AdaptationRecommendationsPanel() {
  const { data, loading, error, refresh } = useAdaptationRecommendations();
  const { apply, reject, loading: actionLoading } = useApplyAdaptation();
  
  const [actionStates, setActionStates] = useState({}); // Track applied/rejected state per change_id

  const handleApply = async (recommendation) => {
    const result = await apply(recommendation.change_id);
    if (result.success) {
      setActionStates(prev => ({
        ...prev,
        [recommendation.change_id]: { status: 'APPLIED', data: result.data }
      }));
      // Refresh recommendations after apply
      setTimeout(refresh, 1000);
    }
  };

  const handleReject = async (recommendation) => {
    const result = await reject(recommendation.change_id);
    if (result.success) {
      setActionStates(prev => ({
        ...prev,
        [recommendation.change_id]: { status: 'REJECTED' }
      }));
      // Refresh recommendations after reject
      setTimeout(refresh, 1000);
    }
  };

  if (loading) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="flex items-center gap-3">
          <div className="w-5 h-5 border-2 border-gray-300 border-t-gray-900 rounded-full animate-spin" />
          <span className="text-sm text-gray-600">Loading recommendations...</span>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-2">⚙️ System Adaptation</h3>
        <p className="text-sm text-gray-500">Failed to load recommendations</p>
      </div>
    );
  }

  const recommendations = data.recommendations || [];
  const hasRecommendations = recommendations.length > 0;
  
  // Show max 3 recommendations
  const displayRecommendations = recommendations.slice(0, 3);

  return (
    <div className="bg-white rounded-lg border border-gray-200">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-100">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">⚙️ System Adaptation</h3>
            <p className="text-xs text-gray-500 mt-1">
              Controlled recommendations · Operator approval required
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-1 bg-amber-50 text-amber-700 text-xs font-medium rounded">
              OPERATOR ONLY
            </span>
            <span className="px-2 py-1 bg-blue-50 text-blue-700 text-xs font-medium rounded">
              VERSIONED
            </span>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="p-6">
        {!hasRecommendations ? (
          <div className="text-center py-8">
            <div className="text-gray-400 text-4xl mb-3">✓</div>
            <p className="text-sm text-gray-600 font-medium">No recommendations</p>
            <p className="text-xs text-gray-500 mt-1">
              {data.reason || 'System is well-calibrated'}
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {displayRecommendations.map((rec) => {
              const actionState = actionStates[rec.change_id];
              const isApplied = actionState?.status === 'APPLIED';
              const isRejected = actionState?.status === 'REJECTED';
              const lowSample = rec.sample_size < MINIMUM_SAMPLE_SIZE;
              
              // Determine if this is overestimation or underestimation
              const isOverestimation = rec.suggested_weight < rec.current_weight;
              const isUnderestimation = rec.suggested_weight > rec.current_weight;
              
              return (
                <div
                  key={rec.change_id}
                  className={`border rounded-lg p-4 ${
                    isOverestimation
                      ? 'border-red-200 bg-red-50'
                      : isUnderestimation
                      ? 'border-green-200 bg-green-50'
                      : 'border-gray-200 bg-gray-50'
                  }`}
                >
                  {/* Title */}
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex-1">
                      <h4 className="text-sm font-semibold text-gray-900 mb-1">
                        Confidence {rec.bucket} {isOverestimation ? 'is overestimated' : 'is underestimated'}
                      </h4>
                      <p className="text-xs text-gray-600">
                        {rec.reason}
                      </p>
                    </div>
                    {lowSample && (
                      <span className="px-2 py-1 bg-yellow-100 text-yellow-800 text-xs font-medium rounded">
                        LOW SAMPLE
                      </span>
                    )}
                  </div>

                  {/* Metrics Grid */}
                  <div className="grid grid-cols-3 gap-3 mb-4">
                    {/* Actual Win Rate */}
                    <div className="bg-white rounded p-2">
                      <div className="text-xs text-gray-500 mb-1">Actual win rate</div>
                      <div className={`text-lg font-bold ${
                        rec.actual_win_rate === 0 
                          ? 'text-red-600' 
                          : rec.actual_win_rate >= 60 
                          ? 'text-green-600' 
                          : 'text-gray-900'
                      }`}>
                        {rec.actual_win_rate?.toFixed(1) || 0}%
                      </div>
                    </div>

                    {/* Expected Floor (if available) */}
                    {rec.expected_floor !== undefined && (
                      <div className="bg-white rounded p-2">
                        <div className="text-xs text-gray-500 mb-1">Expected</div>
                        <div className="text-lg font-bold text-gray-700">
                          ≥{rec.expected_floor.toFixed(0)}%
                        </div>
                      </div>
                    )}

                    {/* Sample Size */}
                    <div className="bg-white rounded p-2">
                      <div className="text-xs text-gray-500 mb-1">Sample size</div>
                      <div className="text-lg font-bold text-gray-900">
                        {rec.sample_size}
                      </div>
                    </div>
                  </div>

                  {/* Suggested Change */}
                  <div className="bg-white rounded p-3 mb-4">
                    <div className="text-xs text-gray-500 mb-2">Suggested weight adjustment</div>
                    <div className="flex items-center gap-3">
                      <div className="text-2xl font-bold text-gray-400">
                        {rec.current_weight.toFixed(2)}
                      </div>
                      <div className="text-gray-400">→</div>
                      <div className={`text-2xl font-bold ${
                        isOverestimation ? 'text-red-600' : 'text-green-600'
                      }`}>
                        {rec.suggested_weight.toFixed(2)}
                      </div>
                      <div className={`text-sm font-medium ${
                        isOverestimation ? 'text-red-600' : 'text-green-600'
                      }`}>
                        ({isOverestimation ? '-' : '+'}{Math.abs(rec.suggested_weight - rec.current_weight).toFixed(2)})
                      </div>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-3">
                    {isApplied ? (
                      <div className="flex-1 text-center py-2 bg-green-100 text-green-800 rounded text-sm font-medium">
                        ✓ Applied → config v{actionState.data?.config_version}
                      </div>
                    ) : isRejected ? (
                      <div className="flex-1 text-center py-2 bg-gray-100 text-gray-600 rounded text-sm font-medium">
                        Rejected
                      </div>
                    ) : (
                      <>
                        <button
                          onClick={() => handleApply(rec)}
                          disabled={lowSample || actionLoading}
                          className={`flex-1 px-4 py-2 rounded font-medium text-sm transition-colors ${
                            lowSample
                              ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                              : 'bg-gray-900 text-white hover:bg-gray-800'
                          }`}
                          title={lowSample ? `Need ${MINIMUM_SAMPLE_SIZE}+ decisions to apply` : 'Apply change'}
                        >
                          {lowSample ? 'Needs more data' : 'Apply'}
                        </button>
                        <button
                          onClick={() => handleReject(rec)}
                          disabled={actionLoading}
                          className="px-4 py-2 rounded border border-gray-300 text-gray-700 hover:bg-gray-50 font-medium text-sm transition-colors"
                        >
                          Reject
                        </button>
                      </>
                    )}
                  </div>

                  {/* Low sample warning */}
                  {lowSample && !isApplied && !isRejected && (
                    <div className="mt-3 text-xs text-yellow-700 bg-yellow-50 rounded p-2">
                      ⚠️ Low confidence recommendation (sample &lt; {MINIMUM_SAMPLE_SIZE}). More decisions needed for safe application.
                    </div>
                  )}
                </div>
              );
            })}

            {recommendations.length > 3 && (
              <div className="text-center text-xs text-gray-500 mt-4">
                Showing top 3 of {recommendations.length} recommendations
              </div>
            )}

            {/* Info footer */}
            <div className="border-t border-gray-100 pt-4 mt-4">
              <p className="text-xs text-gray-500">
                <strong>Note:</strong> All changes are versioned and audited. 
                System cannot auto-apply — operator approval required.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
