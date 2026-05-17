import { useState, useEffect, useCallback } from 'react';

const API = process.env.REACT_APP_BACKEND_URL;

export interface EngineScores {
  composite: number;
  smart_money: number;
  cex: number;
  token: number;
  entities: number;
  weights: Record<string, number>;
}

export interface EngineConfidence {
  level: string;
  score: number;
  factors: {
    agreement: number;
    coverage_bonus: number;
    risk_penalty: number;
    variance_penalty: number;
  };
}

export interface EngineSetup {
  type: string;
  bias: string;
  description: string;
}

export interface EngineGate {
  status: string;
  modules_agreeing?: number;
  total_modules?: number;
  verdicts?: Record<string, string>;
  factors?: string[];
  count?: number;
  issues?: string[];
  missing_count?: number;
}

export interface EvidenceBlock {
  module: string;
  summary: string;
  detail: string;
  signals: string[];
}

export interface EngineDiagnosticsData {
  integrity: {
    confirmed: number;
    contradicted: number;
    neutral: number;
    total: number;
    agreement_rate: number;
  };
  data_quality: {
    coverage: string;
    missing_sources: string[];
    risk_level: string;
  };
  confidence_breakdown: Record<string, number>;
}

export interface ContextMatrixItem {
  market_bias?: string;
  liquidity_shock?: string;
  inventory_state?: string;
  stablecoin_bias?: string;
  pressure_bias?: string;
  net_liquidity?: number;
  net_flow?: number;
  net_flow_fmt?: string;
  conviction?: number;
  clusters?: number;
  signal_count?: number;
  regime?: string;
  pattern?: string;
  confidence?: number;
  token_count?: number;
  active_actors?: number;
  direction?: string;
  avg_smart_score?: number;
  net_flow_fmt2?: string;
  // V4: Actor Intelligence fields
  pressure_balance?: string;
  bullish_actors?: number;
  bearish_actors?: number;
  top_bullish?: Array<{ name: string; impact: string }>;
  top_bearish?: Array<{ name: string; impact: string }>;
  entity_count?: number;
  actor_interactions?: number;
  dominant_behaviour?: string;
}

export interface EngineV3Data {
  decision: string;
  confidence: EngineConfidence;
  setup: EngineSetup;
  window: string;
  scores: EngineScores;
  gates: {
    evidence: EngineGate;
    risk: EngineGate;
    coverage: EngineGate;
  };
  drivers: string[];
  risks: string[];
  context_matrix: Record<string, ContextMatrixItem>;
  evidence: EvidenceBlock[];
  signals: Record<string, string[]>;
  raw_signals: any[];
  diagnostics: EngineDiagnosticsData;
  // V4.2 fields
  regime_engine: any;
  setup_engine: any;
  probability_layer: any;
  decision_explanation: any;
  hero_summary: any;
  decision_integrity: any;
  otc_data: any;
  mm_data: any;
  // V4.3 fields
  otc_mm_influence: any;
  flow_engine: any;
  liquidity_map: any;
  // V4.4 fields
  narrative: any;
  alerts: any[];
  // V4.5 fields
  snapshot_meta: any;
  risk_engine: any;
  playbook: any;
  market_memory: any;
  loading: boolean;
  error: string | null;
}

export function useEngineV3() {
  const [data, setData] = useState<EngineV3Data>({
    decision: '',
    confidence: { level: '', score: 0, factors: { agreement: 0, coverage_bonus: 0, risk_penalty: 0, variance_penalty: 0 } },
    setup: { type: '', bias: '', description: '' },
    window: '',
    scores: { composite: 0, smart_money: 0, cex: 0, token: 0, entities: 0, weights: {} },
    gates: {
      evidence: { status: '' },
      risk: { status: '' },
      coverage: { status: '' },
    },
    drivers: [],
    risks: [],
    context_matrix: {},
    evidence: [],
    signals: {},
    raw_signals: [],
    diagnostics: {
      integrity: { confirmed: 0, contradicted: 0, neutral: 0, total: 4, agreement_rate: 0 },
      data_quality: { coverage: '', missing_sources: [], risk_level: '' },
      confidence_breakdown: {},
    },
    regime_engine: null,
    setup_engine: null,
    probability_layer: null,
    decision_explanation: null,
    hero_summary: null,
    decision_integrity: null,
    otc_data: null,
    mm_data: null,
    otc_mm_influence: null,
    flow_engine: null,
    liquidity_map: null,
    narrative: null,
    alerts: [],
    snapshot_meta: null,
    risk_engine: null,
    playbook: null,
    market_memory: null,
    loading: true,
    error: null,
  });

  const load = useCallback(async () => {
    setData(prev => ({ ...prev, loading: true, error: null }));
    try {
      const [engineRes, otcRes, mmRes] = await Promise.allSettled([
        fetch(`${API}/api/engine/context`).then(r => r.json()),
        fetch(`${API}/api/intelligence/otc`).then(r => r.json()),
        fetch(`${API}/api/intelligence/market-makers`).then(r => r.json()),
      ]);

      const json = engineRes.status === 'fulfilled' ? engineRes.value : null;
      if (!json || !json.ok) throw new Error(json?.error || 'Engine error');

        // Transform signals from flat array to grouped Record<string, string[]>
        const rawSignals = json.signals || [];
        let groupedSignals: Record<string, string[]> = {};
        if (Array.isArray(rawSignals)) {
          rawSignals.forEach((s: any) => {
            const source = s.source || 'other';
            if (!groupedSignals[source]) groupedSignals[source] = [];
            groupedSignals[source].push(s.description || s.text || JSON.stringify(s));
          });
        } else {
          groupedSignals = rawSignals;
        }

        setData({
        decision: json.decision || '',
        confidence: json.confidence || { level: '', score: 0, factors: {} },
        setup: json.setup || { type: '', bias: '', description: '' },
        window: json.window || '',
        scores: {
          composite: json.scores?.composite || 0,
          smart_money: json.scores?.smart_money_score || json.scores?.smart_money || 0,
          cex: json.scores?.cex_score || json.scores?.cex || 0,
          token: json.scores?.token_score || json.scores?.token || 0,
          entities: json.scores?.entities_score || json.scores?.entities || 0,
          weights: json.scores?.weights || {},
        },
        gates: json.gates || { evidence: {}, risk: {}, coverage: {} },
        drivers: json.drivers || [],
        risks: json.risks || [],
        context_matrix: json.context_matrix || {},
        evidence: json.evidence || [],
        signals: groupedSignals,
        raw_signals: Array.isArray(rawSignals) ? rawSignals : [],
        diagnostics: json.diagnostics || {},
        regime_engine: json.regime_engine || null,
        setup_engine: json.setup_engine || null,
        probability_layer: json.probability_layer || null,
        decision_explanation: json.decision_explanation || null,
        hero_summary: json.hero_summary || null,
        decision_integrity: json.decision_integrity || null,
        otc_data: otcRes.status === 'fulfilled' ? otcRes.value : null,
        mm_data: mmRes.status === 'fulfilled' ? mmRes.value : null,
        otc_mm_influence: json.otc_mm_influence || null,
        flow_engine: json.flow_engine || null,
        liquidity_map: json.liquidity_map || null,
        narrative: json.narrative || null,
        alerts: json.alerts || [],
        snapshot_meta: json.snapshot_meta || null,
        risk_engine: json.risk_engine || null,
        playbook: json.playbook || null,
        market_memory: json.market_memory || null,
        loading: false,
        error: null,
      });
    } catch (e: any) {
      setData(prev => ({ ...prev, loading: false, error: e.message }));
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  return { ...data, refresh: load };
}
