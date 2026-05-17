import React from "react";
import Card from "../Card";
import StatusBadge from "../StatusBadge";
import { SentimentAdminSnapshot } from "../../types/sentimentAdmin.types";
import { Lock, Shield, Zap, Clock, Database } from "lucide-react";

interface HeaderStripProps {
  snapshot: SentimentAdminSnapshot;
}

function getDataFreshness(lastIngestAt?: string): { label: string; status: "fresh" | "stale" | "critical" } {
  if (!lastIngestAt) return { label: "Нет данных", status: "critical" };
  const diff = Date.now() - new Date(lastIngestAt).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 5) return { label: `${minutes} мин назад`, status: "fresh" };
  if (minutes < 30) return { label: `${minutes} мин назад`, status: "stale" };
  return { label: `${minutes} мин назад`, status: "critical" };
}

export default function HeaderStrip({ snapshot }: HeaderStripProps) {
  const { manifest, uri, parserHealth } = snapshot;
  const freshness = getDataFreshness(parserHealth?.lastIngestAt);

  return (
    <Card
      title="Sentiment — Центр управления"
      right={
        <div className="flex items-center gap-3">
          <StatusBadge level={uri.uriLevel} size="lg" />
          {manifest.frozen && (
            <span className="flex items-center gap-1.5 text-sm text-blue-600 font-semibold">
              <Lock className="w-3.5 h-3.5" />
              ЗАМОРОЖЕН
            </span>
          )}
          {uri.actions.safeMode && (
            <span className="flex items-center gap-1.5 text-sm text-red-600 font-semibold">
              <Shield className="w-3.5 h-3.5" />
              БЕЗОПАСНЫЙ РЕЖИМ
            </span>
          )}
        </div>
      }
    >
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-4 text-sm">
        <div className="space-y-1">
          <div className="text-slate-500">Версия</div>
          <div className="font-medium text-slate-900">{manifest.version}</div>
        </div>
        <div className="space-y-1">
          <div className="text-slate-500">Режим</div>
          <div className="font-medium text-slate-900">{manifest.featureMode ?? "—"}</div>
        </div>
        <div className="space-y-1">
          <div className="text-slate-500">URI</div>
          <div className="font-medium text-slate-900">{Math.round(uri.uriScore * 100)}%</div>
        </div>
        <div className="space-y-1">
          <div className="text-slate-500">Увер. ×</div>
          <div className="font-medium text-slate-900">{uri.actions.confidenceMultiplier.toFixed(2)}</div>
        </div>
        <div className="space-y-1">
          <div className="text-slate-500">Размер ×</div>
          <div className="font-medium text-slate-900">{uri.actions.sizeMultiplier.toFixed(2)}</div>
        </div>
        <div className="space-y-1">
          <div className="text-slate-500">Обучение</div>
          <div className="flex items-center gap-1.5">
            {uri.actions.trainingBlocked ? (
              <span className="text-red-600 text-xs font-medium">ЗАБЛОК.</span>
            ) : (
              <span className="text-emerald-600 text-xs flex items-center gap-1 font-medium">
                <Zap className="w-3 h-3" /> ОК
              </span>
            )}
          </div>
        </div>
        <div className="space-y-1">
          <div className="text-slate-500 flex items-center gap-1">
            <Database className="w-3 h-3" />
            Свежесть данных
          </div>
          <div className={`text-xs font-medium flex items-center gap-1.5 ${
            freshness.status === "fresh" ? "text-emerald-600" :
            freshness.status === "stale" ? "text-amber-600" :
            "text-red-600"
          }`}>
            <Clock className="w-3 h-3" />
            {freshness.label}
            <span className={`px-1.5 py-0.5 text-[10px] font-medium ${
              freshness.status === "fresh" ? "text-emerald-600" :
              freshness.status === "stale" ? "text-amber-600" :
              "text-red-600"
            }`}>
              {freshness.status === "fresh" ? "ОК" : freshness.status === "stale" ? "УСТАРЕЛО" : "КРИТИЧНО"}
            </span>
          </div>
        </div>
        <div className="space-y-1">
          <div className="text-slate-500">Режим решений</div>
          <div className={`font-medium ${
            snapshot.lifecycle?.mode === "ML" ? "text-blue-600" : "text-slate-600"
          }`}>
            {snapshot.lifecycle?.mode ?? "RULE"}
          </div>
        </div>
      </div>
    </Card>
  );
}
