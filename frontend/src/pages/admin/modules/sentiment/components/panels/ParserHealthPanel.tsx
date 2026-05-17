import React from "react";
import Card from "../Card";
import StatusBadge from "../StatusBadge";
import { SentimentAdminSnapshot } from "../../types/sentimentAdmin.types";
import { Cookie, Clock, AlertTriangle, Activity, Wifi } from "lucide-react";

interface ParserHealthPanelProps {
  snapshot: SentimentAdminSnapshot;
}

function formatDate(iso?: string) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const now = Date.now();
  const diff = now - d.getTime();
  if (diff < 3600000) return `${Math.floor(diff / 60000)} мин назад`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} ч назад`;
  return d.toLocaleString();
}

function getAgeStatus(iso?: string): "fresh" | "stale" | "critical" {
  if (!iso) return "critical";
  const diff = Date.now() - new Date(iso).getTime();
  if (diff < 300000) return "fresh";
  if (diff < 3600000) return "stale";
  return "critical";
}

export default function ParserHealthPanel({ snapshot }: ParserHealthPanelProps) {
  const p = snapshot.parserHealth;
  const ageStatus = getAgeStatus(p.lastIngestAt);

  return (
    <Card 
      title="Здоровье парсера (Twitter)" 
      right={<StatusBadge level={p.level} />}
      className={p.level === "CRITICAL" ? "bg-red-50/50" : ""}
    >
      <div className="space-y-3">
        <div className="flex items-center justify-between py-2">
          <div className="flex items-center gap-2 text-slate-600">
            <Cookie className="w-4 h-4" />
            <span>Cookie-сессии</span>
          </div>
          <span className={`font-medium ${p.cookiesSessions > 0 ? "text-emerald-600" : "text-red-600"}`}>
            {p.cookiesSessions}
          </span>
        </div>
        <div className="flex items-center justify-between py-2">
          <div className="flex items-center gap-2 text-slate-600">
            <Clock className="w-4 h-4" />
            <span>Последний сбор</span>
          </div>
          <span className={`text-sm ${
            ageStatus === "fresh" ? "text-emerald-600" : ageStatus === "stale" ? "text-amber-600" : "text-red-600"
          }`}>
            {formatDate(p.lastIngestAt)}
          </span>
        </div>
        <div className="flex items-center justify-between py-2">
          <div className="flex items-center gap-2 text-slate-600">
            <Activity className="w-4 h-4" />
            <span>Скорость сбора (6ч)</span>
          </div>
          <span className="text-sm text-slate-800">{p.ingestionRatePerHour ?? "—"}</span>
        </div>
        {p.errorRate !== undefined && (
          <div className="flex items-center justify-between py-2">
            <div className="flex items-center gap-2 text-slate-600">
              <AlertTriangle className="w-4 h-4" />
              <span>Процент ошибок</span>
            </div>
            <span className={`text-sm ${(p.errorRate ?? 0) > 0.1 ? "text-red-600" : "text-slate-800"}`}>
              {p.errorRate !== undefined ? `${(p.errorRate * 100).toFixed(1)}%` : "—"}
            </span>
          </div>
        )}
        {p.reasons?.length > 0 && (
          <div className="pt-2">
            <div className="text-xs text-slate-500 mb-2">Причины статуса:</div>
            <div className="flex flex-wrap gap-1.5">
              {p.reasons.map((r, idx) => (
                <span key={idx} className="text-xs text-slate-600">{r}</span>
              ))}
            </div>
          </div>
        )}
        <div className="flex items-center gap-2 pt-2 text-xs">
          <Wifi className={`w-3.5 h-3.5 ${
            p.cookiesSessions > 0 && ageStatus !== "critical" ? "text-emerald-500" : "text-red-500"
          }`} />
          <span className="text-slate-500">
            {p.cookiesSessions > 0 && ageStatus !== "critical" ? "Подключено к Twitter" : "Нет активного подключения"}
          </span>
        </div>
      </div>
    </Card>
  );
}
