import React from 'react';
import { IntelligenceBlock } from '../../../../../components/intelligence';
import type { TokenScore } from '../hooks/useTokenIntelligence';

export function SmartTiming({ scores, loading }: { scores: TokenScore[]; loading: boolean }) {
  if (loading && scores.length === 0) {
    return (
      <IntelligenceBlock dark testId="smart-timing">
        <div className="py-8 text-center">
          <div className="animate-spin w-5 h-5 border-2 border-emerald-400 border-t-transparent rounded-full mx-auto" />
        </div>
      </IntelligenceBlock>
    );
  }

  const withTiming = scores.filter(s => s.avg_timing > 0);
  const avgLead = withTiming.length > 0
    ? withTiming.reduce((s, t) => s + t.avg_timing, 0) / withTiming.length : 0;
  const earlyEntries = withTiming.filter(s => s.avg_timing >= 5).length;
  const successRate = withTiming.length > 0
    ? Math.round((earlyEntries / withTiming.length) * 100) : 0;

  const best = [...scores].sort((a, b) => b.avg_timing - a.avg_timing)[0];
  const leadColor = avgLead >= 7 ? 'text-emerald-400' : avgLead >= 4 ? 'text-amber-400' : 'text-gray-400';

  return (
    <IntelligenceBlock dark testId="smart-timing">
      <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em] mb-4">Smart Money Timing</h3>

      <div className="space-y-4">
        {/* Main metric */}
        <div>
          <div className="text-[9px] font-bold text-gray-500 uppercase tracking-wider mb-0.5">Average Lead Time</div>
          <div className={`text-3xl font-black tabular-nums ${leadColor}`}>+{avgLead.toFixed(1)}h</div>
          <div className="text-[10px] text-gray-500">before price move</div>
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <div className="text-[9px] font-bold text-gray-500 uppercase tracking-wider mb-0.5">Signal Success Rate</div>
            <div className={`text-xl font-black ${successRate >= 70 ? 'text-emerald-400' : 'text-amber-400'}`}>{successRate}%</div>
          </div>
          <div>
            <div className="text-[9px] font-bold text-gray-500 uppercase tracking-wider mb-0.5">Early Entries</div>
            <div className="text-xl font-black text-white">{earlyEntries}</div>
          </div>
        </div>

        {/* Best signal - proof of edge */}
        {best && best.avg_timing > 0 && (
          <div className="pt-3 border-t border-gray-800">
            <div className="text-[9px] font-bold text-gray-500 uppercase tracking-wider mb-2">Best Signal</div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-sm font-black text-white">{best.token}</span>
                <span className={`text-[10px] font-bold uppercase ${
                  best.pattern === 'accumulation' ? 'text-emerald-400' :
                  best.pattern === 'distribution' ? 'text-red-400' : 'text-gray-400'
                }`}>{best.pattern}</span>
              </div>
              <span className={`text-sm font-black tabular-nums ${best.avg_timing >= 7 ? 'text-emerald-400' : 'text-amber-400'}`}>
                Lead +{best.avg_timing.toFixed(1)}h
              </span>
            </div>
            <div className="mt-1 h-1 bg-gray-800 rounded-full overflow-hidden">
              <div className="h-full rounded-full bg-emerald-400 transition-all duration-700"
                style={{ width: `${Math.min(100, (best.avg_timing / 15) * 100)}%` }} />
            </div>
          </div>
        )}
      </div>
    </IntelligenceBlock>
  );
}
