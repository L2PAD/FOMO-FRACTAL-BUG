const API = process.env.REACT_APP_BACKEND_URL || '';

async function get<T>(url: string, params: Record<string, string>): Promise<T> {
  const qs = new URLSearchParams(params).toString();
  const res = await fetch(`${API}${url}?${qs}`, { cache: 'no-store' });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json() as Promise<T>;
}

export interface OverviewData {
  total_forecasts: number;
  evaluated: number;
  evaluated_pct: number;
  hit_rate: number;
  fp_rate: number;
  avg_error: number;
  sample_size: number;
  active_layers: Record<string, boolean>;
}

export interface CalibrationBucket { conf: number; actual: number; count: number; }
export interface CalibrationData {
  ece: number | null;
  brier: number | null;
  sharpness: number | null;
  sample_size: number;
  buckets: CalibrationBucket[];
}

export interface StatePerf { state: string; accuracy: number; fp_rate: number; count: number; }
export interface InteractionData {
  sample_size: number;
  state_distribution: Record<string, number>;
  performance_by_state: StatePerf[];
  confidence_delta: Record<string, number>;
  confidence_flow: { avg_before: number | null; avg_after: number | null; avg_delta: number | null };
}

export interface HorizonEntry { horizon: string; long: number; short: number; neutral: number; }
export interface DecisionData {
  sample_size: number;
  direction_distribution: Record<string, number>;
  by_horizon: HorizonEntry[];
}

export interface HistBucket { bucket: string; count: number; }
export interface DistributionData { confidence_histogram: HistBucket[]; }

export interface AlertItem { type: string; message: string; severity: string; }
export interface AlertsData { alerts: AlertItem[]; }

type Filters = { horizon: string; period: string };

export const dashboardApi = {
  overview: (f: Filters) => get<OverviewData>('/api/dashboard/overview', f),
  calibration: (f: Filters) => get<CalibrationData>('/api/dashboard/calibration', f),
  interaction: (f: Filters) => get<InteractionData>('/api/dashboard/interaction', f),
  decision: (f: Filters) => get<DecisionData>('/api/dashboard/decision', f),
  distribution: (f: Filters) => get<DistributionData>('/api/dashboard/distribution', f),
  alerts: (f: Filters) => get<AlertsData>('/api/dashboard/alerts', f),
};
