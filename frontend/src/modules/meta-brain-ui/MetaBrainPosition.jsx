/**
 * MetaBrainPosition — Suggested position based on Meta Brain verdict
 * Shows direction, size, risk level, and cooldown status
 */
import React from 'react';
import { Shield, AlertTriangle, Zap } from 'lucide-react';

function getRiskLevel(confidence, entropy) {
  if (confidence > 0.6 && entropy < 0.5) return { level: 'Low', color: 'text-emerald-600', bg: 'bg-emerald-50' };
  if (confidence > 0.35) return { level: 'Medium', color: 'text-amber-600', bg: 'bg-amber-50' };
  return { level: 'High', color: 'text-red-600', bg: 'bg-red-50' };
}

function getPositionSize(confidence, verdict) {
  if (verdict === 'NEUTRAL') return '0x';
  if (confidence > 0.7) return '1.0x';
  if (confidence > 0.5) return '0.6x';
  if (confidence > 0.3) return '0.3x';
  return '0.1x';
}

export default function MetaBrainPosition({ data }) {
  if (!data) return null;

  const conf = data.metaConfidence || 0;
  const entropy = data.metaConfidenceDetail?.entropy || 0;
  const risk = getRiskLevel(conf, entropy);
  const size = getPositionSize(conf, data.verdict);

  const rows = [
    { label: 'Direction', value: data.verdict || 'NEUTRAL', testId: 'pos-direction' },
    { label: 'Size', value: size, testId: 'pos-size' },
    { label: 'Risk', value: risk.level, testId: 'pos-risk', color: risk.color },
    { label: 'Cooldown', value: data.stability?.cooldownActive ? 'Active' : 'Inactive', testId: 'pos-cooldown' },
  ];

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5" data-testid="meta-brain-position">
      <div className="flex items-center gap-2 mb-4">
        <Shield className="w-4 h-4 text-gray-400" />
        <p className="text-[10px] uppercase tracking-wider text-gray-400 font-medium">Suggested Position</p>
      </div>

      <div className="grid grid-cols-4 gap-3">
        {rows.map(r => (
          <div key={r.label}>
            <p className="text-[10px] text-gray-400 uppercase tracking-wider mb-1">{r.label}</p>
            <p className={`text-sm font-semibold ${r.color || 'text-gray-900'}`} data-testid={r.testId}>{r.value}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
