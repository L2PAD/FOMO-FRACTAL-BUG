/**
 * Sprint 6.4: Learning Insights Panel
 * ====================================
 * 
 * Shows system learning insights WITHOUT ML.
 * Pure pattern extraction - deterministic, explainable.
 * 
 * Answers:
 * - Does high confidence actually work?
 * - Does R2 reduce losses?
 * - Does operator improve system?
 * - Is confidence calibrated correctly?
 */

import React from 'react';
import { useLearningInsights } from '../../../hooks/analytics/useLearningInsights';

export default function LearningInsightsPanel() {
  const { data, loading, error } = useLearningInsights();

  if (loading) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="flex items-center gap-3">
          <div className="w-5 h-5 border-2 border-gray-300 border-t-gray-900 rounded-full animate-spin" />
          <span className="text-sm text-gray-600">Loading insights...</span>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-2">🧠 System Learning</h3>
        <p className="text-sm text-gray-500">Failed to load insights</p>
      </div>
    );
  }

  const hasData = data.total_decisions > 0;

  return (
    <div className="bg-white rounded-lg border border-gray-200">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-100">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">🧠 System Learning</h3>
            <p className="text-xs text-gray-500 mt-1">
              Pattern extraction · {hasData ? `${data.total_decisions} decisions` : 'No data yet'}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-1 bg-green-50 text-green-700 text-xs font-medium rounded">
              NO ML
            </span>
            <span className="px-2 py-1 bg-blue-50 text-blue-700 text-xs font-medium rounded">
              READ ONLY
            </span>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="p-6">
        {!hasData ? (
          <div className="text-center py-8">
            <div className="text-gray-400 text-4xl mb-3">📊</div>
            <p className="text-sm text-gray-600 font-medium">No learning data available</p>
            <p className="text-xs text-gray-500 mt-1">
              System will extract patterns after decisions have outcomes
            </p>
          </div>
        ) : (
          <div className="space-y-6">
            {/* Insights List */}
            <div className="space-y-4">
              {/* Confidence Insight */}
              <div className="flex gap-3">
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-50 flex items-center justify-center">
                  <span className="text-blue-600 text-sm">📈</span>
                </div>
                <div className="flex-1">
                  <div className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
                    Confidence Analysis
                  </div>
                  <div className="text-sm text-gray-900">
                    {data.confidence_insight}
                  </div>
                </div>
              </div>

              {/* R2 Insight */}
              <div className="flex gap-3">
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-purple-50 flex items-center justify-center">
                  <span className="text-purple-600 text-sm">🛡️</span>
                </div>
                <div className="flex-1">
                  <div className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
                    R2 Risk Impact
                  </div>
                  <div className="text-sm text-gray-900">
                    {data.r2_insight}
                  </div>
                </div>
              </div>

              {/* Operator Insight */}
              <div className="flex gap-3">
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-green-50 flex items-center justify-center">
                  <span className="text-green-600 text-sm">👤</span>
                </div>
                <div className="flex-1">
                  <div className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
                    Operator Impact
                  </div>
                  <div className="text-sm text-gray-900">
                    {data.operator_insight}
                  </div>
                </div>
              </div>
            </div>

            {/* Confidence Calibration */}
            {data.confidence_calibration && Object.keys(data.confidence_calibration).length > 0 && (
              <div className="border-t border-gray-100 pt-6">
                <div className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-3">
                  Confidence Calibration (Reality Check)
                </div>
                <div className="grid grid-cols-2 gap-3">
                  {Object.entries(data.confidence_calibration)
                    .sort((a, b) => b[0].localeCompare(a[0])) // Sort descending
                    .map(([bucket, winRate]) => {
                      const isGood = winRate >= 60;
                      const isBad = winRate < 40;
                      
                      return (
                        <div
                          key={bucket}
                          className={`p-3 rounded-lg border ${
                            isGood
                              ? 'bg-green-50 border-green-200'
                              : isBad
                              ? 'bg-red-50 border-red-200'
                              : 'bg-gray-50 border-gray-200'
                          }`}
                        >
                          <div className="text-xs font-medium text-gray-600 mb-1">
                            Confidence {bucket}
                          </div>
                          <div className={`text-2xl font-bold ${
                            isGood
                              ? 'text-green-700'
                              : isBad
                              ? 'text-red-700'
                              : 'text-gray-700'
                          }`}>
                            {winRate}%
                          </div>
                          <div className="text-xs text-gray-500 mt-1">
                            actual win rate
                          </div>
                        </div>
                      );
                    })}
                </div>
                <div className="mt-3 text-xs text-gray-500 italic">
                  Shows actual performance vs system confidence. Green = calibrated well.
                </div>
              </div>
            )}

            {/* Footer Note */}
            <div className="border-t border-gray-100 pt-4">
              <p className="text-xs text-gray-500">
                <strong>Note:</strong> This is explicit pattern extraction, not ML. 
                System learns from reality but doesn't auto-adjust.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
