import React from "react";
import Card from "../Card";

interface ConfidenceBucket { bucket: string; count: number; }
interface BiasDistribution { longPct: number; shortPct: number; neutralPct: number; }
interface DistributionPanelProps {
  confidenceHistogram?: ConfidenceBucket[];
  biasDistribution?: BiasDistribution;
}

export default function DistributionPanel({ 
  confidenceHistogram = [], 
  biasDistribution = { longPct: 0, shortPct: 0, neutralPct: 1 }
}: DistributionPanelProps) {
  const maxCount = Math.max(...confidenceHistogram.map(d => d.count), 1);

  return (
    <Card title="Распределение уверенности и смещения (30Д)">
      <div className="mb-4">
        <div className="text-xs text-slate-500 mb-2">Распределение уверенности</div>
        <div className="flex items-end gap-2 h-20">
          {confidenceHistogram.map((bucket, i) => (
            <div key={i} className="flex-1 flex flex-col items-center">
              <div className="w-full bg-indigo-500 rounded-t transition-all"
                style={{ height: `${(bucket.count / maxCount) * 100}%`, minHeight: bucket.count > 0 ? '4px' : '0' }} />
              <div className="text-[10px] text-slate-400 mt-1 text-center truncate w-full">{bucket.bucket}</div>
            </div>
          ))}
        </div>
      </div>
      <div className="pt-3">
        <div className="text-xs text-slate-500 mb-2">Распределение смещения (Bias)</div>
        <div className="flex gap-4">
          <div className="flex items-center gap-2"><div className="w-3 h-3 rounded-full bg-emerald-500" /><span className="text-xs text-slate-600">Long {Math.round(biasDistribution.longPct * 100)}%</span></div>
          <div className="flex items-center gap-2"><div className="w-3 h-3 rounded-full bg-red-500" /><span className="text-xs text-slate-600">Short {Math.round(biasDistribution.shortPct * 100)}%</span></div>
          <div className="flex items-center gap-2"><div className="w-3 h-3 rounded-full bg-slate-300" /><span className="text-xs text-slate-600">Neutral {Math.round(biasDistribution.neutralPct * 100)}%</span></div>
        </div>
        <div className="mt-2 h-3 flex rounded-full overflow-hidden bg-slate-100">
          <div className="bg-emerald-500 transition-all" style={{ width: `${biasDistribution.longPct * 100}%` }} />
          <div className="bg-red-500 transition-all" style={{ width: `${biasDistribution.shortPct * 100}%` }} />
          <div className="bg-slate-300 transition-all" style={{ width: `${biasDistribution.neutralPct * 100}%` }} />
        </div>
      </div>
    </Card>
  );
}
