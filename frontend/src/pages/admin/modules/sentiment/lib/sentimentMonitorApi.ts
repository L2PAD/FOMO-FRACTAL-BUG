const API = process.env.REACT_APP_BACKEND_URL || '';

async function get<T>(url: string): Promise<T> {
  const res = await fetch(`${API}${url}`, { cache: 'no-store' });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json() as Promise<T>;
}

export interface SentimentStats {
  ok: boolean;
  total: number;
  by_sentiment: Record<string, number>;
  by_intent: Record<string, number>;
  avg_confidence: number;
  uncertain_pct: number;
}

export interface DataAccumulation {
  ok: boolean;
  data: {
    collections: Record<string, { count: number; label: string }>;
    mlReadiness: {
      status: string;
      dirSamples: number;
      shadowDecisions: number;
      minThreshold: number;
      goodThreshold: number;
      progress: number;
    };
    timestamp: string;
  };
}

export interface DatasetEntriesStats {
  ok: boolean;
  total: number;
  by_label: Record<string, number>;
  by_source: Record<string, number>;
  by_type: Record<string, number>;
  avg_dqs: number;
  ready_for_ml: boolean;
  dataset_distribution: { good_pct: number; neutral_pct: number; bad_pct: number };
  distribution_health: string;
}

export interface DatasetV3Stats {
  ok: boolean;
  total: number;
  resolved: number;
  tradeable: number;
  tradeable_pct: number;
  quality: { avg_dqs: number; high: number; high_pct: number; medium: number; low: number; low_pct: number };
  distribution: {
    by_intent: Record<string, number>;
    by_position: Record<string, number>;
    by_role: Record<string, number>;
    by_regime: Record<string, number>;
  };
  diversity: { unique_actors: number; unique_tokens: number; actor_gini: number; token_gini: number };
}

export interface OutcomeStats {
  ok: boolean;
  total: number;
  resolved: number;
  unresolved: number;
  labels: Record<string, number>;
  tradeable: number;
  tradeable_pct: number;
  resolution_pct: number;
}

export interface IngestionStats {
  ok: boolean;
  events: { total: number; real: number; synthetic: number; real_pct: number };
  dataset: { total: number; real: number; synthetic: number; real_pct: number };
  actors: { real_unique: number; synth_unique: number; overlap: number };
}

export interface CronStatus {
  ok: boolean;
  total_cycles: number;
  pipeline_enabled: boolean;
  last_cycle: {
    cycle_at: string;
    completed_at: string;
    duration_sec: number;
    total_new_signals: number;
    stages: { stage: string; ok: boolean; duration_sec: number; error?: string; attempt: number }[];
  } | null;
  data_health: { status: string; avg_dqs_24h: number; avg_dqs_7d: number; alerts: string[] };
}

export interface DatasetHealth {
  ok: boolean;
  status: string;
  avg_dqs_24h: number;
  avg_dqs_7d: number;
  alerts: string[];
  total: number;
}

export interface EnrichmentStats {
  ok: boolean;
  total: number;
  by_position: Record<string, number>;
  by_actor_role: Record<string, number>;
  by_regime: Record<string, number>;
  by_intent: Record<string, number>;
  avg_actor_score: number;
}

export interface LabelV2Compare {
  ok: boolean;
  total_resolved: number;
  v2_labeled: number;
  v1_distribution: Record<string, number>;
  v2_distribution: Record<string, number>;
  transitions: { old: string; new: string; count: number }[];
  avg_v2_confidence: number | null;
}

export interface EvalAlignment {
  ok: boolean;
  total: number;
  early_exit_rate: number;
  avg_time_to_peak_up: number | null;
  avg_time_to_peak_down: number | null;
  avg_peak_vs_final_gap: number | null;
  peak_captured_but_final_missed: number;
  peak_captured_pct: number;
  by_event_type: Record<string, {
    count: number;
    early_exits: number;
    labels: Record<string, number>;
  }>;
}

export interface SamplingQuality {
  ok: boolean;
  total: number;
  include_rate_new: number;
  included_count: number;
  rejected_count: number;
  avg_score: number | null;
  avg_score_included: number | null;
  score_histogram: { range: string; count: number }[];
  by_reason: Record<string, number>;
  by_event_type: Record<string, {
    count: number;
    included: number;
    avg_score: number;
    include_rate: number;
  }>;
  percentiles?: {
    p50: number;
    p75: number;
    p90: number;
    p95: number;
    max_score: number;
  };
  priority_buckets?: {
    high: { count: number; pct: number };
    medium: { count: number; pct: number };
    low: { count: number; pct: number };
  };
}

export interface RolloutStatus {
  ok: boolean;
  labels_v2_production: boolean;
  sampling_rollout_pct: number;
  total_resolved: number;
  v2_labeled: number;
  v1_labeled: number;
  v2_pct: number;
  sampling_active_count: number;
  rollout_state?: {
    consecutive_passes: number;
    last_rollout_at: string | null;
    last_check_at: string | null;
    last_rollback_at: string | null;
    status: string;
  };
  next_step?: number;
  rollout_steps?: number[];
}

export interface RolloutCheck {
  ok: boolean;
  current_pct: number;
  next_step: number;
  distribution: {
    high_pct: number;
    medium_pct: number;
    low_pct: number;
    include_rate: number;
    total: number;
  };
  health: {
    healthy: boolean;
    ready_for_promotion: boolean;
    needs_rollback: boolean;
    rollback_reasons: string[];
    checks: Record<string, { value: number; range: number[]; pass: boolean }>;
  };
  state: {
    status: string;
    consecutive_passes?: number;
    stability_required?: number;
    current_pct?: number;
    next_step?: number;
    hours_remaining?: number;
  };
}

export interface MlRiskStatus {
  ok: boolean;
  model_trained: boolean;
  dataset_size: number;
  shadow_scored: number;
  metrics: {
    roc_auc: number;
    train_size: number;
    test_size: number;
    positive_rate: number;
    total_samples: number;
    top_features: [string, number][];
    classification_report: Record<string, any>;
  } | null;
}

export interface MlRiskShadowStats {
  ok: boolean;
  total: number;
  bucket_low: { count: number; error_count: number; error_rate: number; avg_conf_before: number; avg_conf_after: number };
  bucket_medium: { count: number; error_count: number; error_rate: number; avg_conf_before: number; avg_conf_after: number };
  bucket_high: { count: number; error_count: number; error_rate: number; avg_conf_before: number; avg_conf_after: number };
  risk_percentiles: { p50: number; p75: number; p90: number; p95: number };
  model_validation: { high_worse_than_low: boolean; high_error_rate: number; low_error_rate: number; verdict: string };
  live_stats?: { live_applied_count: number; live_pct: number };
  preflight_stats?: { triggered_count: number; trigger_rate: number; overlap_with_ml: number; triggered_without_ml: number };
}

export interface MlRiskRolloutStatus {
  ok: boolean;
  ml_overlay: {
    enabled: boolean;
    mode: string;
    live_pct: number;
    risk_threshold: number;
    kill_switch: boolean;
    cap: number;
    multiplier: number;
    salt: string;
  };
  preflight: {
    enabled: boolean;
    mode: string;
    threshold: number;
    base_penalty: number;
    cap: number;
    use_ml: boolean;
  };
  global: { confidence_floor: number };
}

export const sentimentMonitorApi = {
  sentimentStats:    () => get<SentimentStats>('/api/sentiment/stats'),
  dataAccumulation:  () => get<DataAccumulation>('/api/admin/data-accumulation'),
  datasetEntries:    () => get<DatasetEntriesStats>('/api/dataset/entries/stats'),
  datasetV3:         () => get<DatasetV3Stats>('/api/dataset/v3/stats'),
  outcomeStats:      () => get<OutcomeStats>('/api/outcome/stats'),
  ingestionStats:    () => get<IngestionStats>('/api/ml/ingest/status'),
  cronStatus:        () => get<CronStatus>('/api/ingestion/cron/status'),
  datasetHealth:     () => get<DatasetHealth>('/api/dataset/v3/health'),
  enrichmentStats:   () => get<EnrichmentStats>('/api/enrichment/stats'),
  labelV2Compare:    () => get<LabelV2Compare>('/api/outcome/labels-v2-compare'),
  evalAlignment:     () => get<EvalAlignment>('/api/outcome/evaluation-alignment'),
  samplingQuality:   () => get<SamplingQuality>('/api/outcome/sampling-quality'),
  rolloutStatus:     () => get<RolloutStatus>('/api/outcome/rollout-status'),
  rolloutCheck:      () => get<RolloutCheck>('/api/outcome/rollout-check'),
  mlRiskStatus:      () => get<MlRiskStatus>('/api/ml-risk/status'),
  mlRiskShadow:      () => get<MlRiskShadowStats>('/api/ml-risk/shadow-stats'),
  mlRiskRollout:     () => get<MlRiskRolloutStatus>('/api/ml-risk/rollout-status'),
};
