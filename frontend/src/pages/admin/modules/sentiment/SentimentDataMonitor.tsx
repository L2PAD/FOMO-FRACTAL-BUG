import { useState, useEffect, useCallback } from 'react';
import { Loader2, RefreshCw, AlertTriangle, XCircle, CheckCircle, Info, ChevronUp, Shield } from 'lucide-react';
import {
  sentimentMonitorApi,
  SentimentStats, DataAccumulation, DatasetEntriesStats,
  DatasetV3Stats, OutcomeStats, IngestionStats, CronStatus,
  DatasetHealth, EnrichmentStats, LabelV2Compare, EvalAlignment, SamplingQuality,
  RolloutStatus, RolloutCheck, MlRiskStatus, MlRiskShadowStats,
} from './lib/sentimentMonitorApi';
import Card from './components/Card';

/* ─── Helpers ─── */
function Metric({ label, value, sub, warn, critical }: {
  label: string; value: string; sub?: string; warn?: boolean; critical?: boolean;
}) {
  return (
    <div>
      <div className="text-xs text-slate-500">{label}</div>
      <div className={`text-lg font-bold ${critical ? 'text-red-600' : warn ? 'text-amber-600' : 'text-slate-900'}`}>{value}</div>
      {sub && <div className="text-xs text-slate-400">{sub}</div>}
    </div>
  );
}

function ProgressBar({ value, max, color }: { value: number; max: number; color: string }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  return (
    <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
      <div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

function FunnelStep({ label, value, arrow }: { label: string; value: number; arrow?: boolean }) {
  return (
    <div className="flex items-center gap-2">
      <div className="text-center min-w-[80px]">
        <div className="text-lg font-bold text-slate-900">{value.toLocaleString()}</div>
        <div className="text-xs text-slate-500">{label}</div>
      </div>
      {arrow && <div className="text-slate-300 text-lg">→</div>}
    </div>
  );
}

/* ═══ BLOCK 1: WHY ML IS NOT READY + ALERTS ═══ */
function AlertsBlock({ entries, outcome, accum, cron }: {
  entries: DatasetEntriesStats | null;
  outcome: OutcomeStats | null;
  accum: DataAccumulation | null;
  cron: CronStatus | null;
}) {
  const alerts: { level: 'CRITICAL' | 'WARNING' | 'ERROR' | 'OK'; message: string }[] = [];

  // ML readiness
  if (entries && !entries.ready_for_ml) {
    alerts.push({ level: 'CRITICAL', message: 'ML NOT READY — модель не может обучиться' });
  }
  if (entries && entries.distribution_health === 'CRITICAL') {
    alerts.push({ level: 'CRITICAL', message: `Distribution CRITICAL: NEUTRAL = ${entries.dataset_distribution.neutral_pct.toFixed(1)}%` });
  }
  if (outcome && (outcome.labels['BAD'] ?? 0) === 0) {
    alerts.push({ level: 'CRITICAL', message: 'BAD samples = 0 — модель не видит негативных исходов' });
  }

  // Thresholds
  const dir = accum?.data?.mlReadiness?.dirSamples ?? 0;
  if (dir < 300) {
    alerts.push({ level: 'WARNING', message: `Dir samples = ${dir} < 300 (недостаточно для ML)` });
  }
  if (entries && entries.avg_dqs < 0.6) {
    alerts.push({ level: 'WARNING', message: `Avg DQS = ${entries.avg_dqs.toFixed(3)} < 0.6 (низкое качество данных)` });
  }

  // Pipeline errors
  if (cron?.last_cycle?.stages) {
    const failed = cron.last_cycle.stages.filter(s => !s.ok);
    for (const s of failed) {
      alerts.push({ level: 'ERROR', message: `Pipeline stage "${s.stage}" failed: ${s.error || 'unknown'}` });
    }
  }

  if (alerts.length === 0) {
    alerts.push({ level: 'OK', message: 'Все системы работают нормально' });
  }

  const levelColors: Record<string, string> = {
    CRITICAL: 'bg-red-50 border-red-200 text-red-700',
    WARNING: 'bg-amber-50 border-amber-200 text-amber-700',
    ERROR: 'bg-orange-50 border-orange-200 text-orange-700',
    OK: 'bg-emerald-50 border-emerald-200 text-emerald-700',
  };
  const levelIcons: Record<string, React.ReactNode> = {
    CRITICAL: <XCircle className="w-4 h-4 flex-shrink-0" />,
    WARNING: <AlertTriangle className="w-4 h-4 flex-shrink-0" />,
    ERROR: <AlertTriangle className="w-4 h-4 flex-shrink-0" />,
    OK: <CheckCircle className="w-4 h-4 flex-shrink-0" />,
  };

  // WHY ML IS NOT READY block
  const reasons: string[] = [];
  if (outcome && (outcome.labels['BAD'] ?? 0) === 0) reasons.push('BAD samples = 0');
  if (entries && entries.dataset_distribution.neutral_pct > 90) reasons.push(`NEUTRAL dominance = ${entries.dataset_distribution.neutral_pct.toFixed(1)}%`);
  if (entries && entries.total < 300) reasons.push(`Dataset size = ${entries.total} (нужно 300+)`);
  if (dir < 500) reasons.push(`Dir samples = ${dir} / 500`);

  return (
    <div className="space-y-3" data-testid="alerts-block">
      {reasons.length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4" data-testid="ml-not-ready-block">
          <div className="flex items-center gap-2 mb-2">
            <XCircle className="w-5 h-5 text-red-600" />
            <span className="font-bold text-red-700 text-sm">ML NOT READY — ПРИЧИНЫ:</span>
          </div>
          <ul className="space-y-1">
            {reasons.map((r, i) => (
              <li key={i} className="text-sm text-red-600 flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-red-400 flex-shrink-0" />
                {r}
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className="space-y-1.5">
        {alerts.map((a, i) => (
          <div key={i} className={`flex items-center gap-2 text-xs px-3 py-2 rounded-lg border ${levelColors[a.level]}`}>
            {levelIcons[a.level]}
            <span className="font-semibold">{a.level}:</span>
            <span>{a.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ═══ BLOCK 2: ML READINESS ═══ */
function MLReadinessBlock({ accum, entries, outcome }: {
  accum: DataAccumulation | null;
  entries: DatasetEntriesStats | null;
  outcome: OutcomeStats | null;
}) {
  if (!accum || !entries) return null;
  const ml = accum.data.mlReadiness;
  const statusColors: Record<string, string> = {
    NOT_READY: 'text-red-600',
    MINIMUM_MET: 'text-amber-600',
    READY: 'text-emerald-600',
  };

  return (
    <Card title="ML Readiness" right={
      <span className={`text-sm font-bold ${statusColors[ml.status] || 'text-slate-600'}`}>{ml.status}</span>
    }>
      <div className="space-y-4" data-testid="ml-readiness-block">
        {/* Progress bars */}
        <div className="space-y-3">
          <div>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-slate-500">Dir Samples</span>
              <span className="font-medium text-slate-700">{ml.dirSamples} / {ml.goodThreshold}</span>
            </div>
            <ProgressBar value={ml.dirSamples} max={ml.goodThreshold}
              color={ml.dirSamples >= ml.goodThreshold ? 'bg-emerald-500' : ml.dirSamples >= ml.minThreshold ? 'bg-amber-500' : 'bg-red-500'} />
          </div>
          <div>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-slate-500">Dataset Entries</span>
              <span className="font-medium text-slate-700">{entries.total} / 300</span>
            </div>
            <ProgressBar value={entries.total} max={300}
              color={entries.total >= 300 ? 'bg-emerald-500' : 'bg-red-500'} />
          </div>
          <div>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-slate-500">Shadow Decisions</span>
              <span className="font-medium text-slate-700">{ml.shadowDecisions.toLocaleString()}</span>
            </div>
            <ProgressBar value={ml.shadowDecisions} max={5000} color="bg-blue-500" />
          </div>
        </div>

        {/* Distribution Health */}
        <div>
          <div className="text-xs text-slate-500 mb-2">Distribution Health:
            <span className={`ml-1 font-bold ${entries.distribution_health === 'CRITICAL' ? 'text-red-600' : entries.distribution_health === 'WARNING' ? 'text-amber-600' : 'text-emerald-600'}`}>
              {entries.distribution_health}
            </span>
          </div>
          <div className="flex h-6 rounded-lg overflow-hidden">
            {entries.dataset_distribution.good_pct > 0 && (
              <div className="bg-emerald-500 flex items-center justify-center text-white text-xs font-medium"
                   style={{ width: `${Math.max(entries.dataset_distribution.good_pct, 5)}%` }}>
                {entries.dataset_distribution.good_pct.toFixed(1)}%
              </div>
            )}
            {entries.dataset_distribution.neutral_pct > 0 && (
              <div className="bg-slate-300 flex items-center justify-center text-slate-700 text-xs font-medium"
                   style={{ width: `${entries.dataset_distribution.neutral_pct}%` }}>
                {entries.dataset_distribution.neutral_pct.toFixed(1)}%
              </div>
            )}
            {entries.dataset_distribution.bad_pct > 0 && (
              <div className="bg-red-500 flex items-center justify-center text-white text-xs font-medium"
                   style={{ width: `${Math.max(entries.dataset_distribution.bad_pct, 5)}%` }}>
                {entries.dataset_distribution.bad_pct.toFixed(1)}%
              </div>
            )}
          </div>
          <div className="flex justify-between text-xs text-slate-400 mt-1">
            <span>GOOD: {outcome?.labels['GOOD'] ?? 0}</span>
            <span>NEUTRAL: {outcome?.labels['NEUTRAL'] ?? 0}</span>
            <span>BAD: {outcome?.labels['BAD'] ?? 0}</span>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <Metric label="Ready for ML" value={entries.ready_for_ml ? 'YES' : 'NO'}
                  critical={!entries.ready_for_ml} />
          <Metric label="Avg DQS" value={entries.avg_dqs.toFixed(3)}
                  warn={entries.avg_dqs < 0.6} />
        </div>
      </div>
    </Card>
  );
}

/* ═══ BLOCK 3: DATA FUNNEL ═══ */
function DataFunnelBlock({ accum, ingestion, enrichment, dsV3, outcome, entries }: {
  accum: DataAccumulation | null;
  ingestion: IngestionStats | null;
  enrichment: EnrichmentStats | null;
  dsV3: DatasetV3Stats | null;
  outcome: OutcomeStats | null;
  entries: DatasetEntriesStats | null;
}) {
  const aggregates = accum?.data?.collections?.sentiment_aggregates?.count ?? 0;
  const events = ingestion?.events?.total ?? 0;
  const enriched = enrichment?.total ?? 0;
  const dataset = dsV3?.total ?? 0;
  const resolved = outcome?.resolved ?? 0;
  const mlReady = entries?.ready_for_ml ? entries.total : 0;

  return (
    <Card title="Data Funnel">
      <div data-testid="data-funnel-block">
        <div className="flex items-center justify-between flex-wrap gap-2 py-2">
          <FunnelStep label="Aggregates" value={aggregates} arrow />
          <FunnelStep label="Events" value={events} arrow />
          <FunnelStep label="Enriched" value={enriched} arrow />
          <FunnelStep label="Dataset" value={dataset} arrow />
          <FunnelStep label="Resolved" value={resolved} arrow />
          <FunnelStep label="ML-Ready" value={mlReady} />
        </div>
        {ingestion && (
          <div className="mt-3 pt-3 border-t border-slate-100">
            <div className="grid grid-cols-3 gap-4">
              <Metric label="Real Events" value={`${ingestion.events.real.toLocaleString()} (${ingestion.events.real_pct}%)`} />
              <Metric label="Synthetic" value={`${ingestion.events.synthetic.toLocaleString()}`} />
              <Metric label="Real Actors" value={`${ingestion.actors.real_unique.toLocaleString()}`} sub={`synth: ${ingestion.actors.synth_unique}`} />
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}

/* ═══ BLOCK 4: DISTRIBUTION HEALTH ═══ */
function DistributionBlock({ dsV3, sentiment, enrichment }: {
  dsV3: DatasetV3Stats | null;
  sentiment: SentimentStats | null;
  enrichment: EnrichmentStats | null;
}) {
  if (!dsV3) return null;
  const diversity = dsV3.diversity || {
    unique_actors: 0,
    unique_tokens: 0,
    actor_gini: 0,
    token_gini: 0,
  };
  const distribution = dsV3.distribution || {
    by_intent: {},
    by_role: {},
    by_token: {},
  };

  function MiniDistBar({ data, colors }: { data: Record<string, number>; colors: Record<string, string> }) {
    const total = Object.values(data).reduce((a, b) => a + b, 0);
    if (total === 0) return <div className="text-xs text-slate-400">Нет данных</div>;
    return (
      <div className="space-y-1">
        {Object.entries(data).sort((a, b) => b[1] - a[1]).map(([k, v]) => (
          <div key={k} className="flex items-center gap-2 text-xs">
            <span className="w-24 text-slate-500 truncate">{k}</span>
            <div className="flex-1 h-3 bg-slate-100 rounded overflow-hidden">
              <div className={`h-full rounded ${colors[k] || 'bg-indigo-400'}`}
                   style={{ width: `${(v / total) * 100}%` }} />
            </div>
            <span className="w-8 text-right text-slate-600">{v}</span>
          </div>
        ))}
      </div>
    );
  }

  const intentColors: Record<string, string> = {
    BULLISH_SIGNAL: 'bg-emerald-500', BEARISH_SIGNAL: 'bg-red-500',
    HYPE: 'bg-purple-500', INFORMATIONAL: 'bg-blue-500',
    WARNING: 'bg-amber-500', NOISE: 'bg-slate-400',
  };
  const roleColors: Record<string, string> = {
    TRACKER: 'bg-blue-500', NOISE: 'bg-slate-400', UNKNOWN: 'bg-slate-300',
  };

  return (
    <Card title="Distribution Health">
      <div className="space-y-4" data-testid="distribution-block">
        <div className="grid grid-cols-4 gap-3">
          <Metric label="Unique Actors" value={String(diversity.unique_actors)} />
          <Metric label="Unique Tokens" value={String(diversity.unique_tokens)} />
          <Metric label="Actor Gini" value={(diversity.actor_gini ?? 0).toFixed(3)}
                  warn={(diversity.actor_gini ?? 0) > 0.5} sub={(diversity.actor_gini ?? 0) > 0.5 ? 'high concentration' : ''} />
          <Metric label="Token Gini" value={(diversity.token_gini ?? 0).toFixed(3)}
                  warn={(diversity.token_gini ?? 0) > 0.5} />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div>
            <div className="text-xs text-slate-500 font-medium mb-1.5">By Intent</div>
            <MiniDistBar data={distribution.by_intent} colors={intentColors} />
          </div>
          <div>
            <div className="text-xs text-slate-500 font-medium mb-1.5">By Role</div>
            <MiniDistBar data={distribution.by_role} colors={roleColors} />
          </div>
        </div>

        {sentiment && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 pt-3 border-t border-slate-100">
            <div>
              <div className="text-xs text-slate-500 font-medium mb-1.5">Sentiment Distribution ({sentiment.total.toLocaleString()} total)</div>
              <MiniDistBar data={sentiment.by_sentiment} colors={{
                POSITIVE: 'bg-emerald-500', NEGATIVE: 'bg-red-500', NEUTRAL: 'bg-slate-400',
              }} />
            </div>
            <div>
              <div className="text-xs text-slate-500 font-medium mb-1.5">Inference Quality</div>
              <div className="grid grid-cols-2 gap-3">
                <Metric label="Avg Confidence" value={`${(sentiment.avg_confidence * 100).toFixed(1)}%`} />
                <Metric label="Uncertain" value={`${sentiment.uncertain_pct.toFixed(1)}%`}
                        warn={sentiment.uncertain_pct > 10} />
              </div>
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}

/* ═══ BLOCK 5: PIPELINE STATUS ═══ */
function PipelineBlock({ cron, health }: { cron: CronStatus | null; health: DatasetHealth | null }) {
  if (!cron) return null;
  const lc = cron.last_cycle;
  const stages = lc?.stages ?? [];
  const successCount = stages.filter(s => s.ok).length;
  const totalStages = stages.length;

  return (
    <Card title="Pipeline Status" right={
      <span className={`text-xs font-medium ${cron.pipeline_enabled ? 'text-emerald-600' : 'text-red-600'}`}>
        {cron.pipeline_enabled ? 'ENABLED' : 'DISABLED'}
      </span>
    }>
      <div className="space-y-4" data-testid="pipeline-block">
        <div className="grid grid-cols-4 gap-3">
          <Metric label="Total Cycles" value={String(cron.total_cycles)} />
          <Metric label="Success Rate" value={totalStages > 0 ? `${successCount}/${totalStages}` : '—'}
                  warn={successCount < totalStages} />
          <Metric label="Last Signals" value={String(lc?.total_new_signals ?? 0)} />
          <Metric label="Duration" value={lc ? `${(lc.duration_sec ?? 0).toFixed(0)}s` : '—'} />
        </div>

        {lc && (
          <div>
            <div className="text-xs text-slate-500 mb-2">Stages ({successCount}/{totalStages} OK)</div>
            <div className="grid grid-cols-3 sm:grid-cols-5 gap-1.5">
              {stages.map((s, i) => (
                <div key={i} className={`text-xs px-2 py-1.5 rounded-lg border ${
                  s.ok ? 'bg-emerald-50 border-emerald-200 text-emerald-700' : 'bg-red-50 border-red-200 text-red-700'
                }`} data-testid={`stage-${s.stage}`}>
                  <div className="font-medium truncate">{s.ok ? '\u2713' : '\u2717'} {s.stage}</div>
                  <div className="text-slate-400">{(s.duration_sec ?? 0).toFixed(1)}s</div>
                  {!s.ok && s.error && <div className="text-red-500 truncate mt-0.5" title={s.error}>{s.error}</div>}
                </div>
              ))}
            </div>
          </div>
        )}

        {health && (
          <div className="pt-3 border-t border-slate-100 grid grid-cols-3 gap-3">
            <Metric label="Health" value={(health.status || 'unknown').toUpperCase()}
                    warn={health.status !== 'healthy'} />
            <Metric label="DQS 24h" value={(health.avg_dqs_24h ?? 0).toFixed(3)} warn={(health.avg_dqs_24h ?? 0) < 0.6} />
            <Metric label="DQS 7d" value={(health.avg_dqs_7d ?? 0).toFixed(3)} warn={(health.avg_dqs_7d ?? 0) < 0.6} />
          </div>
        )}

        {lc && (
          <div className="text-xs text-slate-400">
            Last cycle: {new Date(lc.completed_at).toLocaleString()}
          </div>
        )}
      </div>
    </Card>
  );
}

/* ═══ BLOCK 6: LABEL V2 SHADOW COMPARE ═══ */
function LabelV2Block({ d }: { d: LabelV2Compare }) {
  const v2Labels = ['STRONG_GOOD', 'WEAK_GOOD', 'NEUTRAL', 'WEAK_BAD', 'STRONG_BAD'];
  const v2Colors: Record<string, string> = {
    STRONG_GOOD: 'bg-emerald-500', WEAK_GOOD: 'bg-emerald-300',
    NEUTRAL: 'bg-slate-300',
    WEAK_BAD: 'bg-red-300', STRONG_BAD: 'bg-red-500',
  };
  const v2Total = Object.values(d.v2_distribution).reduce((a, b) => a + b, 0) || 1;
  const v1Total = Object.values(d.v1_distribution).reduce((a, b) => a + b, 0) || 1;

  // Filter meaningful transitions (old != new)
  const deltas = d.transitions.filter(t => t.old !== t.new).sort((a, b) => b.count - a.count);

  return (
    <Card title="Label V2 Shadow Compare" right={
      <span className="text-xs text-slate-500">shadow mode • {d.v2_labeled} labeled</span>
    }>
      <div className="space-y-4" data-testid="label-v2-block">
        {/* Side-by-side bars */}
        <div className="grid grid-cols-2 gap-6">
          <div>
            <div className="text-xs text-slate-500 font-medium mb-2">V1 (Production)</div>
            {Object.entries(d.v1_distribution).sort((a, b) => b[1] - a[1]).map(([k, v]) => (
              <div key={k} className="flex items-center gap-2 text-xs mb-1">
                <span className="w-20 text-slate-500">{k}</span>
                <div className="flex-1 h-4 bg-slate-100 rounded overflow-hidden">
                  <div className="h-full bg-slate-400 rounded" style={{ width: `${(v / v1Total) * 100}%` }} />
                </div>
                <span className="w-14 text-right font-medium">{((v / v1Total) * 100).toFixed(1)}%</span>
              </div>
            ))}
          </div>
          <div>
            <div className="text-xs text-slate-500 font-medium mb-2">V2 (Shadow — 5 labels)</div>
            {v2Labels.map(k => {
              const v = d.v2_distribution[k] || 0;
              if (v === 0) return null;
              return (
                <div key={k} className="flex items-center gap-2 text-xs mb-1">
                  <span className="w-24 text-slate-500">{k}</span>
                  <div className="flex-1 h-4 bg-slate-100 rounded overflow-hidden">
                    <div className={`h-full rounded ${v2Colors[k]}`} style={{ width: `${(v / v2Total) * 100}%` }} />
                  </div>
                  <span className="w-14 text-right font-medium">{((v / v2Total) * 100).toFixed(1)}%</span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Delta transitions */}
        {deltas.length > 0 && (
          <div className="pt-3 border-t border-slate-100">
            <div className="text-xs text-slate-500 font-medium mb-2">Transitions (what V2 unfroze)</div>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5">
              {deltas.map((t, i) => (
                <div key={i} className="text-xs bg-slate-50 rounded-lg px-2 py-1.5 flex items-center gap-1">
                  <span className="text-slate-400">{t.old}</span>
                  <span className="text-slate-300">→</span>
                  <span className={`font-medium ${t.new.includes('GOOD') ? 'text-emerald-600' : t.new.includes('BAD') ? 'text-red-600' : 'text-slate-600'}`}>{t.new}</span>
                  <span className="ml-auto text-slate-500 font-bold">{t.count}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {d.avg_v2_confidence != null && (
          <div className="text-xs text-slate-400">
            Avg V2 confidence score: <span className="font-medium text-slate-600">{d.avg_v2_confidence.toFixed(4)}</span>
          </div>
        )}
      </div>
    </Card>
  );
}

/* ═══ BLOCK 7: EVALUATION ALIGNMENT ═══ */
function EvalAlignmentBlock({ d }: { d: EvalAlignment }) {
  const typeColors: Record<string, string> = {
    social_spike: 'bg-purple-100 text-purple-700',
    narrative: 'bg-indigo-100 text-indigo-700',
    whale_move: 'bg-amber-100 text-amber-700',
    unknown: 'bg-slate-100 text-slate-600',
  };

  return (
    <Card title="Evaluation Alignment" right={
      <span className="text-xs text-slate-500">{d.total} samples analyzed</span>
    }>
      <div className="space-y-4" data-testid="eval-alignment-block">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <Metric label="Early Exit Rate" value={`${d.early_exit_rate}%`}
                  sub="strong hit within 24h" />
          <Metric label="Avg Time to Peak Up" value={d.avg_time_to_peak_up != null ? `${d.avg_time_to_peak_up}h` : '—'} />
          <Metric label="Avg Time to Peak Down" value={d.avg_time_to_peak_down != null ? `${d.avg_time_to_peak_down}h` : '—'} />
          <Metric label="Peak vs Final Gap" value={d.avg_peak_vs_final_gap != null ? `${d.avg_peak_vs_final_gap.toFixed(2)}%` : '—'}
                  sub="divergence" />
          <Metric label="Peak Captured, Final Missed"
                  value={`${d.peak_captured_but_final_missed} (${d.peak_captured_pct}%)`}
                  warn={d.peak_captured_pct > 10}
                  sub="signals lost to reversal" />
        </div>

        {Object.keys(d.by_event_type).length > 0 && (
          <div className="pt-3 border-t border-slate-100">
            <div className="text-xs text-slate-500 font-medium mb-2">By Event Type</div>
            <div className="space-y-2">
              {Object.entries(d.by_event_type).map(([et, info]) => {
                const total = info.count;
                return (
                  <div key={et} className="flex items-start gap-3">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${typeColors[et] || typeColors.unknown}`}>
                      {et}
                    </span>
                    <div className="flex-1">
                      <div className="flex items-center gap-2 text-xs text-slate-600">
                        <span>{total} samples</span>
                        {info.early_exits > 0 && (
                          <span className="text-emerald-600">{info.early_exits} early exits</span>
                        )}
                      </div>
                      <div className="flex gap-1 mt-1">
                        {Object.entries(info.labels).sort((a, b) => b[1] - a[1]).map(([label, count]) => (
                          <span key={label} className={`text-xs px-1.5 py-0.5 rounded ${
                            label.includes('GOOD') ? 'bg-emerald-50 text-emerald-600' :
                            label.includes('BAD') ? 'bg-red-50 text-red-600' :
                            'bg-slate-50 text-slate-500'
                          }`}>
                            {label}: {count}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}

/* ═══ BLOCK 8: SAMPLING QUALITY ═══ */
function SamplingBlock({ d }: { d: SamplingQuality }) {
  const maxHist = Math.max(...d.score_histogram.map(b => b.count), 1);

  const reasonColors: Record<string, string> = {
    high_signal: 'bg-emerald-100 text-emerald-700',
    medium_signal: 'bg-blue-100 text-blue-700',
    low_signal: 'bg-amber-100 text-amber-700',
    exploration: 'bg-purple-100 text-purple-700',
    medium_rejected: 'bg-slate-100 text-slate-500',
    low_rejected: 'bg-slate-50 text-slate-400',
  };

  const pctl = d.percentiles;
  const pb = d.priority_buckets;

  return (
    <Card title="Sampling Quality (Shadow)" right={
      <span className="text-xs text-slate-500">{d.total} events scored</span>
    }>
      <div className="space-y-4" data-testid="sampling-block">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <Metric label="Include Rate (New)" value={`${d.include_rate_new}%`}
                  sub={`${d.included_count} / ${d.total}`} />
          <Metric label="Rejected" value={`${d.rejected_count}`} sub="would be filtered" />
          <Metric label="Avg Score" value={d.avg_score?.toFixed(4) ?? '—'} />
          <Metric label="Avg Score (Included)" value={d.avg_score_included?.toFixed(4) ?? '—'} />
          <Metric label="Improvement" value={
            d.avg_score && d.avg_score_included
              ? `+${((d.avg_score_included - d.avg_score) / d.avg_score * 100).toFixed(0)}%`
              : '—'
          } sub="included vs all" />
        </div>

        {/* Score Distribution Percentiles + Priority Buckets */}
        {pctl && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 p-3 bg-slate-50 rounded-xl border border-slate-200" data-testid="score-distribution-panel">
            <div>
              <div className="text-xs font-bold text-slate-700 mb-2">Score Distribution</div>
              <div className="grid grid-cols-5 gap-2">
                {(['p50', 'p75', 'p90', 'p95', 'max_score'] as const).map(k => {
                  const val = pctl[k];
                  const labels: Record<string, string> = {
                    p50: 'P50', p75: 'P75', p90: 'P90', p95: 'P95', max_score: 'MAX',
                  };
                  const targets: Record<string, number> = { p95: 0.6, max_score: 0.7 };
                  const target = targets[k];
                  const hit = target ? val >= target : false;
                  const miss = target ? val < target : false;
                  return (
                    <div key={k} className="text-center" data-testid={`percentile-${k}`}>
                      <div className="text-xs text-slate-500">{labels[k]}</div>
                      <div className={`text-base font-bold ${miss ? 'text-red-600' : hit ? 'text-emerald-600' : 'text-slate-900'}`}>
                        {val.toFixed(3)}
                      </div>
                      {target && (
                        <div className={`text-xs ${hit ? 'text-emerald-500' : 'text-red-400'}`}>
                          {hit ? '✓' : '✗'} {'>='}{target}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
            {pb && (
              <div>
                <div className="text-xs font-bold text-slate-700 mb-2">Priority Buckets</div>
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="w-16 text-xs text-slate-500">High {'≥'}0.6</span>
                    <div className="flex-1 h-5 bg-slate-100 rounded overflow-hidden">
                      <div className="h-full bg-emerald-500 rounded" style={{ width: `${Math.max(pb.high.pct, 1)}%` }} />
                    </div>
                    <span className={`w-20 text-right text-xs font-bold ${pb.high.pct > 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                      {pb.high.count} ({pb.high.pct}%)
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-16 text-xs text-slate-500">Med 0.3-0.6</span>
                    <div className="flex-1 h-5 bg-slate-100 rounded overflow-hidden">
                      <div className="h-full bg-blue-400 rounded" style={{ width: `${pb.medium.pct}%` }} />
                    </div>
                    <span className="w-20 text-right text-xs font-bold text-blue-600">
                      {pb.medium.count} ({pb.medium.pct}%)
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-16 text-xs text-slate-500">Low {'<'}0.3</span>
                    <div className="flex-1 h-5 bg-slate-100 rounded overflow-hidden">
                      <div className="h-full bg-slate-300 rounded" style={{ width: `${pb.low.pct}%` }} />
                    </div>
                    <span className="w-20 text-right text-xs font-bold text-slate-500">
                      {pb.low.count} ({pb.low.pct}%)
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Score histogram */}
        <div>
          <div className="text-xs text-slate-500 font-medium mb-1.5">Event Score Distribution</div>
          <div className="space-y-1">
            {d.score_histogram.map((b, i) => (
              <div key={i} className="flex items-center gap-2 text-xs">
                <span className="w-14 text-right text-slate-500">{b.range}</span>
                <div className="flex-1 h-4 bg-slate-100 rounded overflow-hidden">
                  <div className="h-full bg-indigo-400 rounded" style={{ width: `${(b.count / maxHist) * 100}%` }} />
                </div>
                <span className="w-8 text-right text-slate-600 font-medium">{b.count}</span>
              </div>
            ))}
          </div>
        </div>

        {/* By reason + By event type side by side */}
        <div className="grid grid-cols-2 gap-4 pt-3 border-t border-slate-100">
          <div>
            <div className="text-xs text-slate-500 font-medium mb-1.5">By Decision Reason</div>
            <div className="space-y-1">
              {Object.entries(d.by_reason).sort((a, b) => b[1] - a[1]).map(([reason, count]) => (
                <div key={reason} className="flex items-center gap-2">
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${reasonColors[reason] || 'bg-slate-100 text-slate-500'}`}>
                    {reason.replace(/_/g, ' ')}
                  </span>
                  <span className="text-xs text-slate-600 font-medium">{count}</span>
                </div>
              ))}
            </div>
          </div>
          <div>
            <div className="text-xs text-slate-500 font-medium mb-1.5">By Event Type</div>
            <div className="space-y-1.5">
              {Object.entries(d.by_event_type).sort((a, b) => b[1].count - a[1].count).map(([et, info]) => (
                <div key={et} className="text-xs">
                  <div className="flex justify-between">
                    <span className="text-slate-600 font-medium">{et}</span>
                    <span className="text-slate-400">{info.count} / incl: {info.include_rate}%</span>
                  </div>
                  <div className="h-1.5 bg-slate-100 rounded-full mt-0.5">
                    <div className="h-full bg-blue-400 rounded-full" style={{ width: `${info.include_rate}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </Card>
  );
}

/* ═══ BLOCK 9: ROLLOUT STATUS ═══ */
function RolloutBlock({ d, onRefresh }: { d: RolloutStatus; onRefresh: () => void }) {
  const [check, setCheck] = useState<RolloutCheck | null>(null);
  const [checking, setChecking] = useState(false);
  const [promoting, setPromoting] = useState(false);
  const [promoteResult, setPromoteResult] = useState<string | null>(null);

  const v2Active = d.labels_v2_production;
  const samplingPct = d.sampling_rollout_pct;
  const rs = d.rollout_state;
  const isReady = rs?.status?.startsWith('READY_FOR_');

  const runCheck = async () => {
    setChecking(true);
    try {
      const result = await sentimentMonitorApi.rolloutCheck();
      setCheck(result);
    } catch { /* ignore */ }
    setChecking(false);
  };

  const promoteRollout = async () => {
    setPromoting(true);
    setPromoteResult(null);
    try {
      const API = process.env.REACT_APP_BACKEND_URL || '';
      const res = await fetch(`${API}/api/outcome/rollout-promote`, { method: 'POST' });
      const data = await res.json();
      if (data.ok) {
        setPromoteResult(`Promoted: ${data.old_pct}% -> ${data.new_pct}%`);
        onRefresh();
      } else {
        setPromoteResult(data.message || 'Promotion failed');
      }
    } catch (e: any) {
      setPromoteResult(e.message || 'Error');
    }
    setPromoting(false);
  };

  const statusColor = (status: string) => {
    if (status?.startsWith('READY_FOR_')) return 'text-emerald-600 bg-emerald-50';
    if (status === 'COOLDOWN') return 'text-blue-600 bg-blue-50';
    if (status === 'ROLLBACK') return 'text-red-600 bg-red-50';
    if (status === 'FULLY_ROLLED_OUT') return 'text-emerald-700 bg-emerald-100';
    if (status?.startsWith('STABILIZING')) return 'text-amber-600 bg-amber-50';
    return 'text-slate-600 bg-slate-50';
  };

  return (
    <Card title="Production Rollout Control" right={
      <div className="flex items-center gap-2">
        <span className={`text-xs font-bold ${v2Active ? 'text-emerald-600' : 'text-amber-600'}`}>
          {v2Active ? 'V2 LIVE' : 'V1 ACTIVE'}
        </span>
        <button onClick={runCheck} disabled={checking}
          className="text-xs px-2 py-1 rounded bg-slate-100 hover:bg-slate-200 text-slate-600 transition-colors"
          data-testid="rollout-check-btn">
          {checking ? 'Checking...' : 'Health Check'}
        </button>
      </div>
    }>
      <div className="space-y-4" data-testid="rollout-block">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <Metric label="Labels" value={v2Active ? 'V2 PROD' : 'V1'}
                  warn={!v2Active} />
          <Metric label="Sampling" value={`${samplingPct}%`}
                  sub={samplingPct >= 100 ? 'fully rolled out' : `next: ${d.next_step || '—'}%`} />
          <Metric label="V2 Coverage" value={`${d.v2_pct}%`}
                  sub={`${d.v2_labeled}/${d.total_resolved}`} />
          <Metric label="V1 Remaining" value={String(d.v1_labeled)}
                  warn={d.v1_labeled > 0 && v2Active} />
          <div className="text-center">
            <div className="text-xs text-slate-500">Status</div>
            <div className={`text-xs font-bold px-2 py-1 rounded-full mt-1 inline-block ${statusColor(rs?.status || 'STABLE')}`}
                 data-testid="rollout-status-badge">
              {rs?.status || 'STABLE'}
            </div>
          </div>
        </div>

        {/* Progress bar */}
        <div>
          <div className="flex justify-between text-xs mb-1">
            <span className="text-slate-500">Sampling Rollout</span>
            <span className="font-medium text-slate-700">{samplingPct}%</span>
          </div>
          <div className="h-3 bg-slate-100 rounded-full overflow-hidden relative">
            <div className={`h-full rounded-full transition-all ${
              samplingPct >= 100 ? 'bg-emerald-500' : samplingPct >= 70 ? 'bg-blue-500' : samplingPct >= 30 ? 'bg-amber-500' : 'bg-orange-400'
            }`} style={{ width: `${samplingPct}%` }} />
            {(d.rollout_steps || [10, 30, 70, 100]).map(step => (
              <div key={step} className="absolute top-0 h-full border-r border-slate-300"
                   style={{ left: `${step}%` }} />
            ))}
          </div>
          <div className="flex justify-between text-xs text-slate-400 mt-1">
            {(d.rollout_steps || [10, 30, 70, 100]).map(s => (
              <span key={s} className={samplingPct >= s ? 'text-slate-700 font-medium' : ''}>{s}%</span>
            ))}
          </div>
        </div>

        {/* Health Check Results */}
        {check && (
          <div className={`p-3 rounded-xl border ${check.health.needs_rollback ? 'bg-red-50 border-red-200' : check.health.ready_for_promotion ? 'bg-emerald-50 border-emerald-200' : 'bg-amber-50 border-amber-200'}`}
               data-testid="health-check-panel">
            <div className="flex items-center gap-2 mb-2">
              {check.health.needs_rollback ? <XCircle className="w-4 h-4 text-red-500" /> :
               check.health.ready_for_promotion ? <CheckCircle className="w-4 h-4 text-emerald-500" /> :
               <AlertTriangle className="w-4 h-4 text-amber-500" />}
              <span className="text-xs font-bold">
                {check.health.needs_rollback ? 'ROLLBACK TRIGGERED' :
                 check.health.ready_for_promotion ? `READY for ${check.next_step}%` :
                 'NOT READY for promotion'}
              </span>
            </div>
            <div className="grid grid-cols-4 gap-2 text-xs">
              {Object.entries(check.health.checks).map(([key, val]) => (
                <div key={key} className={`px-2 py-1 rounded ${val.pass ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'}`}>
                  <div className="font-medium">{key}</div>
                  <div>{val.value}% <span className="opacity-60">[{val.range[0]}-{val.range[1]}]</span></div>
                </div>
              ))}
            </div>
            {check.state.status?.startsWith('STABILIZING') && (
              <div className="text-xs text-amber-600 mt-2">
                Stability: {check.state.consecutive_passes}/{check.state.stability_required} consecutive passes
              </div>
            )}
            {check.state.status === 'COOLDOWN' && check.state.hours_remaining && (
              <div className="text-xs text-blue-600 mt-2">
                Cooldown: {check.state.hours_remaining}h remaining
              </div>
            )}
          </div>
        )}

        {/* PROMOTE Button */}
        {isReady && (
          <div className="flex items-center gap-3 p-3 bg-emerald-50 border border-emerald-200 rounded-xl" data-testid="promote-panel">
            <Shield className="w-5 h-5 text-emerald-600" />
            <div className="flex-1">
              <div className="text-sm font-bold text-emerald-700">Ready for promotion</div>
              <div className="text-xs text-emerald-600">
                {rs?.consecutive_passes || 0} consecutive health checks passed. Promote to {d.next_step}%?
              </div>
            </div>
            <button onClick={promoteRollout} disabled={promoting}
              className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-bold rounded-lg transition-colors flex items-center gap-1"
              data-testid="promote-btn">
              <ChevronUp className="w-4 h-4" />
              {promoting ? 'Promoting...' : `PROMOTE to ${d.next_step}%`}
            </button>
          </div>
        )}

        {promoteResult && (
          <div className="text-xs text-center text-slate-600 bg-slate-50 p-2 rounded" data-testid="promote-result">
            {promoteResult}
          </div>
        )}
      </div>
    </Card>
  );
}

/* ═══ BLOCK 10: ML RISK OVERLAY ═══ */
function MlRiskBlock({ status, shadow }: { status: MlRiskStatus; shadow: MlRiskShadowStats | null }) {
  const m = status.metrics;
  const v = shadow?.model_validation;

  const bucketColor = (rate: number) => {
    if (rate >= 80) return 'text-red-600';
    if (rate >= 60) return 'text-amber-600';
    return 'text-emerald-600';
  };

  return (
    <Card title="ML Risk Overlay V1 (Shadow)" right={
      <span className={`text-xs font-bold ${status.model_trained ? 'text-emerald-600' : 'text-slate-400'}`}>
        {status.model_trained ? 'MODEL TRAINED' : 'NOT TRAINED'}
      </span>
    }>
      <div className="space-y-4" data-testid="ml-risk-block">
        {/* Model metrics */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <Metric label="ROC AUC" value={m ? m.roc_auc.toFixed(3) : '—'}
                  warn={m ? m.roc_auc < 0.55 : false}
                  sub={m && m.roc_auc > 0.6 ? 'above baseline' : 'needs improvement'} />
          <Metric label="Dataset" value={String(status.dataset_size)} sub="samples" />
          <Metric label="Shadow Scored" value={String(status.shadow_scored)} />
          <Metric label="Error Rate" value={m ? `${(m.positive_rate * 100).toFixed(1)}%` : '—'} sub="in dataset" />
          <Metric label="Verdict" value={v?.verdict || '—'}
                  warn={v?.verdict === 'CHECK_MODEL'} />
        </div>

        {/* Risk buckets */}
        {shadow && shadow.total > 0 && (
          <div className="grid grid-cols-3 gap-3 p-3 bg-slate-50 rounded-xl border border-slate-200" data-testid="risk-buckets">
            {(['low', 'medium', 'high'] as const).map(bk => {
              const d = shadow[`bucket_${bk}`];
              const labels = { low: 'Low Risk', medium: 'Medium Risk', high: 'High Risk' };
              const bgColors = { low: 'bg-emerald-50 border-emerald-200', medium: 'bg-amber-50 border-amber-200', high: 'bg-red-50 border-red-200' };
              return (
                <div key={bk} className={`p-3 rounded-lg border ${bgColors[bk]}`} data-testid={`risk-bucket-${bk}`}>
                  <div className="text-xs font-bold text-slate-700 mb-2">{labels[bk]}</div>
                  <div className="space-y-1 text-xs">
                    <div className="flex justify-between">
                      <span className="text-slate-500">Count</span>
                      <span className="font-medium">{d.count}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">Error Rate</span>
                      <span className={`font-bold ${bucketColor(d.error_rate)}`}>{d.error_rate}%</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">Conf Before</span>
                      <span className="font-medium">{d.avg_conf_before.toFixed(3)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">Conf After ML</span>
                      <span className="font-medium">{d.avg_conf_after.toFixed(3)}</span>
                    </div>
                    {d.avg_conf_before > 0 && (
                      <div className="flex justify-between">
                        <span className="text-slate-500">Reduction</span>
                        <span className="font-bold text-blue-600">
                          {((1 - d.avg_conf_after / d.avg_conf_before) * 100).toFixed(0)}%
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Validation */}
        {v && (
          <div className={`p-3 rounded-xl border text-xs ${v.high_worse_than_low ? 'bg-emerald-50 border-emerald-200' : 'bg-red-50 border-red-200'}`}
               data-testid="model-validation">
            <div className="flex items-center gap-2 mb-1">
              {v.high_worse_than_low ? <CheckCircle className="w-4 h-4 text-emerald-500" /> : <XCircle className="w-4 h-4 text-red-500" />}
              <span className="font-bold">Model Validation: {v.verdict}</span>
            </div>
            <div className="text-slate-600">
              High risk error rate ({v.high_error_rate}%) {v.high_worse_than_low ? '>' : '<='} Low risk error rate ({v.low_error_rate}%)
              {v.high_worse_than_low ? ' — model correctly separates risky predictions' : ' — model needs retraining'}
            </div>
          </div>
        )}

        {/* Live + Preflight stats */}
        {shadow && (shadow.live_stats || shadow.preflight_stats) && (
          <div className="grid grid-cols-2 gap-3" data-testid="live-preflight-stats">
            {shadow.live_stats && (
              <div className="p-3 bg-blue-50 border border-blue-200 rounded-xl text-xs">
                <div className="font-bold text-blue-700 mb-1">Live Modulation (Stage 2)</div>
                <div className="space-y-0.5">
                  <div className="flex justify-between"><span>Live applied</span><span className="font-medium">{shadow.live_stats.live_applied_count}</span></div>
                  <div className="flex justify-between"><span>Coverage</span><span className="font-medium">{shadow.live_stats.live_pct}%</span></div>
                </div>
              </div>
            )}
            {shadow.preflight_stats && (
              <div className="p-3 bg-purple-50 border border-purple-200 rounded-xl text-xs">
                <div className="font-bold text-purple-700 mb-1">Preflight Gate (Shadow)</div>
                <div className="space-y-0.5">
                  <div className="flex justify-between"><span>Triggered</span><span className="font-medium">{shadow.preflight_stats.triggered_count} ({shadow.preflight_stats.trigger_rate}%)</span></div>
                  <div className="flex justify-between"><span>ML overlap</span><span className="font-medium">{shadow.preflight_stats.overlap_with_ml}</span></div>
                  <div className="flex justify-between"><span>Unique triggers</span><span className="font-medium">{shadow.preflight_stats.triggered_without_ml}</span></div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Top features */}
        {m && m.top_features && m.top_features.length > 0 && (
          <div>
            <div className="text-xs text-slate-500 font-medium mb-1.5">Top Features (by coefficient magnitude)</div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-1">
              {m.top_features.slice(0, 8).map(([name, coef]) => (
                <div key={name} className="text-xs px-2 py-1 rounded bg-slate-50 flex justify-between">
                  <span className="text-slate-600 truncate">{name.replace('num__', '').replace('cat__', '')}</span>
                  <span className={`font-medium ml-1 ${coef > 0 ? 'text-red-500' : 'text-emerald-500'}`}>
                    {coef > 0 ? '+' : ''}{coef.toFixed(2)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}

/* ═══ MAIN PAGE ═══ */
export default function SentimentDataMonitor() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sentiment, setSentiment] = useState<SentimentStats | null>(null);
  const [accum, setAccum] = useState<DataAccumulation | null>(null);
  const [entries, setEntries] = useState<DatasetEntriesStats | null>(null);
  const [dsV3, setDsV3] = useState<DatasetV3Stats | null>(null);
  const [outcome, setOutcome] = useState<OutcomeStats | null>(null);
  const [ingestion, setIngestion] = useState<IngestionStats | null>(null);
  const [cron, setCron] = useState<CronStatus | null>(null);
  const [health, setHealth] = useState<DatasetHealth | null>(null);
  const [enrichment, setEnrichment] = useState<EnrichmentStats | null>(null);
  const [labelV2, setLabelV2] = useState<LabelV2Compare | null>(null);
  const [evalAlign, setEvalAlign] = useState<EvalAlignment | null>(null);
  const [sampling, setSampling] = useState<SamplingQuality | null>(null);
  const [rollout, setRollout] = useState<RolloutStatus | null>(null);
  const [mlRiskStatus, setMlRiskStatus] = useState<MlRiskStatus | null>(null);
  const [mlRiskShadow, setMlRiskShadow] = useState<MlRiskShadowStats | null>(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, a, e, d, o, i, c, h, en, lv2, ea, sq, rs, mrs, mrsh] = await Promise.all([
        sentimentMonitorApi.sentimentStats(),
        sentimentMonitorApi.dataAccumulation(),
        sentimentMonitorApi.datasetEntries(),
        sentimentMonitorApi.datasetV3(),
        sentimentMonitorApi.outcomeStats(),
        sentimentMonitorApi.ingestionStats(),
        sentimentMonitorApi.cronStatus(),
        sentimentMonitorApi.datasetHealth(),
        sentimentMonitorApi.enrichmentStats(),
        sentimentMonitorApi.labelV2Compare(),
        sentimentMonitorApi.evalAlignment(),
        sentimentMonitorApi.samplingQuality(),
        sentimentMonitorApi.rolloutStatus(),
        sentimentMonitorApi.mlRiskStatus(),
        sentimentMonitorApi.mlRiskShadow(),
      ]);
      setSentiment(s); setAccum(a); setEntries(e); setDsV3(d);
      setOutcome(o); setIngestion(i); setCron(c); setHealth(h); setEnrichment(en);
      setLabelV2(lv2); setEvalAlign(ea); setSampling(sq); setRollout(rs);
      setMlRiskStatus(mrs); setMlRiskShadow(mrsh);
    } catch (e: any) {
      setError(e.message || 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);
  useEffect(() => {
    const id = setInterval(fetchAll, 30000);
    return () => clearInterval(id);
  }, [fetchAll]);

  return (
    <div className="min-h-screen bg-slate-50 p-6" data-testid="sentiment-data-monitor">
      <div className="max-w-7xl mx-auto space-y-4">
        {/* Header */}
        <div className="bg-white rounded-xl p-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-lg font-bold text-slate-900" data-testid="monitor-title">
                Sentiment Data Accumulation Monitor
              </h1>
              <p className="text-xs text-slate-500">Центр правды по данным — ML Readiness, Pipeline, Quality</p>
            </div>
            <button onClick={fetchAll} className="p-1.5 rounded-lg hover:bg-slate-100 transition-colors"
                    data-testid="refresh-btn">
              <RefreshCw className={`w-4 h-4 text-slate-500 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700" data-testid="error-msg">
            {error}
          </div>
        )}

        {loading && !accum ? (
          <div className="flex items-center justify-center h-64">
            <Loader2 className="w-8 h-8 text-slate-400 animate-spin" />
          </div>
        ) : (
          <>
            {/* BLOCK 1: Alerts + WHY ML IS NOT READY */}
            <AlertsBlock entries={entries} outcome={outcome} accum={accum} cron={cron} />

            {/* BLOCK 2+3: ML Readiness + Data Funnel */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <MLReadinessBlock accum={accum} entries={entries} outcome={outcome} />
              <DataFunnelBlock accum={accum} ingestion={ingestion} enrichment={enrichment}
                              dsV3={dsV3} outcome={outcome} entries={entries} />
            </div>

            {/* BLOCK 4: Distribution Health (full width) */}
            <DistributionBlock dsV3={dsV3} sentiment={sentiment} enrichment={enrichment} />

            {/* BLOCK 5: Pipeline Status (full width) */}
            <PipelineBlock cron={cron} health={health} />

            {/* BLOCK 6: Label V2 Shadow Compare */}
            {labelV2 && labelV2.v2_labeled > 0 && <LabelV2Block d={labelV2} />}

            {/* BLOCK 7: Evaluation Alignment */}
            {evalAlign && evalAlign.total > 0 && <EvalAlignmentBlock d={evalAlign} />}

            {/* BLOCK 8: Sampling Quality */}
            {sampling && sampling.total > 0 && <SamplingBlock d={sampling} />}

            {/* BLOCK 9: Production Rollout */}
            {rollout && <RolloutBlock d={rollout} onRefresh={fetchAll} />}

            {/* BLOCK 10: ML Risk Overlay */}
            {mlRiskStatus && <MlRiskBlock status={mlRiskStatus} shadow={mlRiskShadow} />}
          </>
        )}

        <div className="text-center text-xs text-slate-400 py-2">
          Auto-refresh 30s • Pipeline: every 6h • {cron?.total_cycles ?? 0} cycles total
        </div>
      </div>
    </div>
  );
}
