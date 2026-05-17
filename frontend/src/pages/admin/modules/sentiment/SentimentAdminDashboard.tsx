import React from "react";
import Card from "./components/Card";
import ErrorCard from "./components/ErrorCard";
import LoadingCard from "./components/LoadingCard";
import HeaderStrip from "./components/panels/HeaderStrip";
import ParserHealthPanel from "./components/panels/ParserHealthPanel";
import UriPanel from "./components/panels/UriPanel";
import GuardActionsPanel from "./components/panels/GuardActionsPanel";
import DriftPanel from "./components/panels/DriftPanel";
import CapitalPanel from "./components/panels/CapitalPanel";
import LifecyclePanel from "./components/panels/LifecyclePanel";
import CalibrationPanel from "./components/panels/CalibrationPanel";
import EvidencePanel from "./components/panels/EvidencePanel";
import FeatureLockPanel from "./components/panels/FeatureLockPanel";
import ManualActionsPanel from "./components/panels/ManualActionsPanel";
import MarketRegimePanel from "./components/panels/MarketRegimePanel";
import DistributionPanel from "./components/panels/DistributionPanel";
import PerformanceComparePanel from "./components/panels/PerformanceComparePanel";
import SignalStabilityPanel from "./components/panels/SignalStabilityPanel";
import { useSentimentAdminStatus, useSentimentIntelligence } from "./hooks/useSentimentStatus";

export default function SentimentAdminDashboard() {
  const { data, error, isLoading, refetch } = useSentimentAdminStatus({
    pollMs: 15000,
  });
  
  const { data: intelligenceData } = useSentimentIntelligence({
    pollMs: 30000,
  });

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-50 p-6 space-y-4">
        <LoadingCard title="Загрузка..." />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <LoadingCard title="URI" />
          <LoadingCard title="Парсер" />
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen bg-slate-50 p-6">
        <ErrorCard
          title="Ошибка загрузки Sentiment"
          message={String(error?.message ?? "Нет данных от API")}
          onRetry={refetch}
        />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 p-6 space-y-4">
      {/* Header */}
      <HeaderStrip snapshot={data} />

      {/* Row 1: URI + Parser Health + Guard Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <UriPanel snapshot={data} />
        <ParserHealthPanel snapshot={data} />
        <GuardActionsPanel snapshot={data} />
      </div>

      {/* Row 2: Drift + Capital */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <DriftPanel snapshot={data} />
        <CapitalPanel snapshot={data} />
      </div>

      {/* Row 3: Market Regime + Distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <MarketRegimePanel 
          regime={intelligenceData?.regime?.marketRegime}
          trendStrength={intelligenceData?.regime?.trendStrength}
        />
        <DistributionPanel 
          confidenceHistogram={intelligenceData?.distribution?.confidenceHistogram}
          biasDistribution={intelligenceData?.distribution?.biasDistribution}
        />
      </div>

      {/* Row 4: Performance Compare + Signal Stability */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <PerformanceComparePanel 
          mlEquity={intelligenceData?.performance?.mlEquity}
          ruleEquity={intelligenceData?.performance?.ruleEquity}
          rollingHitRate={intelligenceData?.performance?.rollingHitRate}
          rollingSharpe={intelligenceData?.performance?.rollingSharpe}
        />
        <SignalStabilityPanel 
          uriAdjustmentsPct={intelligenceData?.stability?.uriAdjustmentsPct}
          safeModePct={intelligenceData?.stability?.safeModePct}
          calibrationAdjustmentsPct={intelligenceData?.stability?.calibrationAdjustmentsPct}
          lowDataPct={intelligenceData?.stability?.lowDataPct}
        />
      </div>

      {/* Row 5: Lifecycle + Calibration */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <LifecyclePanel snapshot={data} />
        <CalibrationPanel snapshot={data} />
      </div>

      {/* Row 6: Feature Lock + Quick Stats + Manual Actions */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <FeatureLockPanel featureLock={undefined} />
        
        {/* Быстрая статистика */}
        <Card title="Быстрая статистика">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-center py-2">
            <div>
              <div className="text-xl font-bold text-slate-800">{data.capital?.trades ?? 0}</div>
              <div className="text-xs text-slate-500">Сделки</div>
            </div>
            <div>
              <div className={`text-xl font-bold ${(data.capital?.expectancy ?? 0) >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                {((data.capital?.expectancy ?? 0) * 100).toFixed(2)}%
              </div>
              <div className="text-xs text-slate-500">Ожидание</div>
            </div>
            <div>
              <div className="text-xl font-bold text-slate-800">
                {((data.capital?.winRate ?? 0) * 100).toFixed(1)}%
              </div>
              <div className="text-xs text-slate-500">Win Rate</div>
            </div>
            <div>
              <div className="text-xl font-bold text-slate-800">
                {Math.round(data.uri.uriScore * 100)}%
              </div>
              <div className="text-xs text-slate-500">URI</div>
            </div>
          </div>
        </Card>

        {/* Manual Actions */}
        <ManualActionsPanel moduleKey="sentiment" />
      </div>

      {/* Row 5: Evidence Log (full width) */}
      <EvidencePanel snapshot={data} />

      {/* Footer with refresh info */}
      <div className="text-center text-xs text-slate-400 pt-4">
        Авто-обновление каждые 15 сек — Последнее: {new Date().toLocaleTimeString()}
      </div>
    </div>
  );
}
