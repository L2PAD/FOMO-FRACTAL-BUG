/**
 * Manual Actions Panel
 * =====================
 * 

 */

import React, { useState } from 'react';
import Card from '../Card';
import { rerunDriftCheck, rerunCalibration, recomputeCapital, flushEvidence } from '../../lib/adminExchangeApi';

interface ManualActionsPanelProps {
  onActionComplete?: () => void;
}

interface ActionButtonProps {
  label: string;
  description: string;
  onClick: () => Promise<void>;
  loading: boolean;
}

function ActionButton({ label, description, onClick, loading }: ActionButtonProps) {
  return (
    <button
      onClick={onClick}
      disabled={loading}
      className="flex items-start gap-3 p-3 w-full text-left bg-gray-50 hover:bg-gray-100 rounded-lg transition-colors disabled:opacity-50"
    >
      <div className="w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center flex-shrink-0">
        {loading ? (
          <div className="w-4 h-4 rounded-full bg-blue-500 animate-spin" />
        ) : (
          <svg className="w-4 h-4 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        )}
      </div>
      <div>
        <div className="font-medium text-gray-900">{label}</div>
        <div className="text-xs text-gray-500">{description}</div>
      </div>
    </button>
  );
}

export default function ManualActionsPanel({ onActionComplete }: ManualActionsPanelProps) {
  const [loading, setLoading] = useState<string | null>(null);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const handleAction = async (action: string, fn: () => Promise<any>) => {
    setLoading(action);
    setMessage(null);
    try {
      const result = await fn();
      setMessage({ type: 'success', text: result.message || 'Action completed' });
      onActionComplete?.();
    } catch (e: any) {
      setMessage({ type: 'error', text: e.message || 'Action failed' });
    } finally {
      setLoading(null);
    }
  };

  return (
    <Card title="Manual Controls" right={<span className="text-xs text-gray-500">Admin only</span>}>
      <div className="grid grid-cols-2 gap-3">
        <ActionButton
          label="Re-run Drift Check"
          description="Recalculate PSI and update stabilized status"
          onClick={() => handleAction('drift', rerunDriftCheck)}
          loading={loading === 'drift'}
        />
        <ActionButton
          label="Re-run Calibration"
          description="Update ECE and bucket posteriors"
          onClick={() => handleAction('calibration', rerunCalibration)}
          loading={loading === 'calibration'}
        />
        <ActionButton
          label="Recalculate Capital Window"
          description="Refresh 30D rolling performance metrics"
          onClick={() => handleAction('capital', recomputeCapital)}
          loading={loading === 'capital'}
        />
        <ActionButton
          label="Force Evidence Flush"
          description="Persist pending evidence events"
          onClick={() => handleAction('evidence', flushEvidence)}
          loading={loading === 'evidence'}
        />
      </div>

      {message && (
        <div className={`mt-3 p-2 rounded-lg text-sm ${
          message.type === 'success' 
            ? 'text-emerald-600' 
            : 'text-red-600'
        }`}>
          {message.text}
        </div>
      )}

      <div className="mt-3 pt-3 text-xs text-gray-500">
        Actions are logged in Evidence Trail
      </div>
    </Card>
  );
}
