/**
 * Bootstrap Progress Card
 * 
 * Shows progress from 0 to 30 samples for BOOTSTRAP → HEALTHY transition
 */

import React from 'react';

export function BootstrapProgressCard({ sampleCount = 0, minSamples = 30 }) {
  const progress = Math.min(100, Math.round((sampleCount / minSamples) * 100));
  const isComplete = sampleCount >= minSamples;
  
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4" data-testid="bootstrap-progress">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-medium text-gray-700">Накопление данных</h3>
        <span className={`text-xs px-2 py-0.5 rounded ${
          isComplete ? 'bg-green-100 text-green-800' : 'bg-amber-100 text-amber-800'
        }`}>
          {isComplete ? 'READY' : 'BOOTSTRAP'}
        </span>
      </div>
      
      <div className="flex items-center gap-3">
        {/* Progress Bar */}
        <div className="flex-1">
          <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
            <div 
              className={`h-full transition-all duration-500 rounded-full ${
                isComplete ? 'bg-green-500' : 'bg-amber-500'
              }`}
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
        
        {/* Count */}
        <div className="text-sm font-mono text-gray-600">
          {sampleCount}/{minSamples}
        </div>
      </div>
      
      {!isComplete && (
        <p className="mt-2 text-xs text-gray-500">
          Необходимо {minSamples - sampleCount} outcomes для перехода в HEALTHY
        </p>
      )}
    </div>
  );
}

/**
 * Rollback Button Card
 * 
 * Shows rollback option when model is in CRITICAL state
 */
export function RollbackCard({ health, onRollback }) {
  const isCritical = health?.grade === 'CRITICAL' || health?.grade === 'DEGRADED';
  const [showConfirm, setShowConfirm] = React.useState(false);
  const [loading, setLoading] = React.useState(false);
  
  const handleRollback = async () => {
    setLoading(true);
    try {
      await onRollback?.();
      setShowConfirm(false);
    } finally {
      setLoading(false);
    }
  };
  
  if (!isCritical) {
    return null;
  }
  
  return (
    <div className="bg-red-50 rounded-xl border border-red-200 p-4" data-testid="rollback-card">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-medium text-red-800">Модель в критическом состоянии</h3>
          <p className="text-xs text-red-600 mt-1">
            Grade: {health?.grade} | Reasons: {health?.reasons?.join(', ') || 'Unknown'}
          </p>
        </div>
        
        {!showConfirm ? (
          <button
            onClick={() => setShowConfirm(true)}
            className="px-4 py-2 bg-red-600 text-white text-sm font-medium rounded-lg hover:bg-red-700 transition-colors"
            data-testid="rollback-btn"
          >
            Откатить к stable
          </button>
        ) : (
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowConfirm(false)}
              className="px-3 py-1.5 bg-gray-200 text-gray-700 text-sm rounded-lg hover:bg-gray-300"
              disabled={loading}
            >
              Отмена
            </button>
            <button
              onClick={handleRollback}
              disabled={loading}
              className="px-4 py-1.5 bg-red-600 text-white text-sm font-medium rounded-lg hover:bg-red-700 disabled:opacity-50"
              data-testid="confirm-rollback-btn"
            >
              {loading ? 'Откат...' : 'Подтвердить'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default BootstrapProgressCard;
