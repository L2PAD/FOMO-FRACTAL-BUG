import { SentimentAdminSnapshot, ReliabilityLevel, SentimentIntelligenceData } from "../types/sentimentAdmin.types";

const API_URL = process.env.REACT_APP_BACKEND_URL || "";

async function safeJson(res: Response) {
  const txt = await res.text();
  try {
    return JSON.parse(txt);
  } catch {
    return { raw: txt };
  }
}

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...init,
    headers: {
      "content-type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    const body = await safeJson(res);
    throw new Error(`HTTP ${res.status} ${url}: ${JSON.stringify(body).slice(0, 500)}`);
  }
  return (await res.json()) as T;
}

function scoreToLevel(score: number): ReliabilityLevel {
  if (score >= 0.75) return "OK";
  if (score >= 0.60) return "WARN";
  if (score >= 0.40) return "DEGRADED";
  if (score > 0) return "CRITICAL";
  return "UNKNOWN";
}

/**
 * Fetch Sentiment Admin Snapshot from multiple endpoints
 */
export async function getSentimentAdminSnapshot(): Promise<SentimentAdminSnapshot> {
  // Fetch all data in parallel
  const [reliabilityRaw, parserRaw, manifestRaw, driftRaw, capitalRaw, lifecycleRaw, calibrationRaw, evidenceRaw] = 
    await Promise.all([
      fetchJSON<any>(`${API_URL}/api/admin/sentiment-ml/reliability/status`).catch(() => null),
      fetchJSON<any>(`${API_URL}/api/admin/sentiment-ml/guards/parser-health`).catch(() => null),
      fetchJSON<any>(`${API_URL}/api/admin/sentiment-ml/reliability/module-manifest`).catch(() => null),
      fetchJSON<any>(`${API_URL}/api/admin/sentiment-ml/drift/stabilizer/status`).catch(() => null),
      fetchJSON<any>(`${API_URL}/api/admin/sentiment-ml/capital/window`).catch(() => null),
      fetchJSON<any>(`${API_URL}/api/admin/sentiment-ml/lifecycle/status`).catch(() => null),
      fetchJSON<any>(`${API_URL}/api/admin/modules/calibration/sentiment/latest`).catch(() => null),
      fetchJSON<any>(`${API_URL}/api/admin/modules/evidence/recent?module=sentiment&limit=20`).catch(() => null),
    ]);

  return normalizeSnapshot({
    reliabilityRaw,
    parserRaw,
    manifestRaw,
    driftRaw,
    capitalRaw,
    lifecycleRaw,
    calibrationRaw,
    evidenceRaw,
  });
}

function normalizeSnapshot(input: {
  reliabilityRaw: any;
  parserRaw: any;
  manifestRaw: any;
  driftRaw: any;
  capitalRaw: any;
  lifecycleRaw: any;
  calibrationRaw: any;
  evidenceRaw: any;
}): SentimentAdminSnapshot {
  const { reliabilityRaw, parserRaw, manifestRaw, driftRaw, capitalRaw, lifecycleRaw, calibrationRaw, evidenceRaw } = input;

  // Extract reliability data
  const rel = reliabilityRaw?.reliability ?? reliabilityRaw ?? {};
  const uriScore = Number(rel?.score ?? 0);
  const uriLevel = (rel?.level ?? scoreToLevel(uriScore)) as ReliabilityLevel;

  // Components
  const compsRaw = rel?.componentsRaw ?? rel?.components ?? {};
  const toComp = (val: any, reasons?: string[]) => ({
    score: typeof val === "number" ? val : Number(val?.score ?? 0),
    level: scoreToLevel(typeof val === "number" ? val : Number(val?.score ?? 0)),
    reasons: reasons ?? [],
  });

  // Actions
  const actions = rel?.actions ?? {};

  // Parser Health
  const parser = parserRaw?.parser ?? parserRaw ?? {};
  const parserMetrics = parser?.details?.metrics ?? parser?.metrics ?? parser ?? {};

  // Manifest
  const manifest = manifestRaw?.manifest ?? manifestRaw ?? {};

  // Drift
  const drift = driftRaw?.drift ?? driftRaw ?? {};

  // Capital
  const cap = capitalRaw?.capital ?? capitalRaw?.window ?? capitalRaw ?? {};

  // Lifecycle
  const life = lifecycleRaw?.lifecycle ?? lifecycleRaw ?? {};

  // Calibration
  const calib = calibrationRaw?.calibration ?? calibrationRaw ?? {};

  // Evidence
  const evList = evidenceRaw?.events ?? evidenceRaw ?? [];

  return {
    manifest: {
      moduleKey: "sentiment",
      version: String(manifest?.version ?? "1.0.0"),
      frozen: Boolean(manifest?.frozen ?? false),
      frozenAt: manifest?.frozenAt,
      featureMode: manifest?.featureMode ?? "CORE_ONLY",
    },
    uri: {
      uriScore,
      uriLevel,
      components: {
        dataHealth: toComp(compsRaw?.dataHealth ?? 0, rel?.reasons?.filter((r: string) => r.includes("DATA") || r.includes("COOKIE") || r.includes("SAFE"))),
        driftHealth: toComp(compsRaw?.driftHealth ?? 0.7),
        capitalHealth: toComp(compsRaw?.capitalHealth ?? 0.7),
        calibrationHealth: toComp(compsRaw?.calibrationHealth ?? 0.7),
      },
      actions: {
        trainingBlocked: Boolean(actions?.trainingBlocked ?? false),
        promotionBlocked: Boolean(actions?.promotionBlocked ?? false),
        workersBlocked: Boolean(actions?.workersBlocked ?? false),
        confidenceMultiplier: Number(actions?.confidenceMultiplier ?? 1),
        sizeMultiplier: Number(actions?.sizeMultiplier ?? 1),
        safeMode: Boolean(actions?.safeMode ?? false),
        safeModeReason: actions?.safeModeReason,
      },
    },
    parserHealth: {
      level: scoreToLevel(compsRaw?.dataHealth ?? 0),
      reasons: rel?.reasons ?? [],
      cookiesSessions: Number(parserMetrics?.activeSessions ?? parserMetrics?.cookiesSessions ?? 0),
      lastIngestAt: parserMetrics?.lastEventAt ?? parserMetrics?.lastIngestAt,
      lastTweetAt: parserMetrics?.lastTweetAt,
      ingestionRatePerHour: parserMetrics?.ingestionRatePerHour ?? parserMetrics?.events6h,
      errorRate: parserMetrics?.errorRate,
    },
    drift: drift ? {
      psiRaw: Number(drift?.psiRaw ?? 0),
      psiEma: Number(drift?.psiEma ?? 0),
      status: (drift?.stabilizedStatus ?? drift?.status ?? "OK") as ReliabilityLevel,
      streakCount: Number(drift?.streaks?.warn ?? drift?.streakCount ?? 0),
      baselineVersion: String(drift?.baselineVersion ?? "N/A"),
      baselineCreatedAt: drift?.baselineCreatedAt,
      baselineAge: drift?.baselineAge,
    } : undefined,
    capital: cap ? {
      trades: Number(cap?.trades ?? 0),
      winRate: Number(cap?.winRate ?? 0),
      expectancy: Number(cap?.expectancy ?? 0),
      maxDD: Number(cap?.maxDD ?? 0),
      sharpe: Number(cap?.sharpe ?? 0),
      equity: Number(cap?.equity ?? 1),
    } : undefined,
    capitalGates: capitalRaw?.gates ? {
      promotionEligible: Boolean(capitalRaw.gates?.promotionEligible ?? false),
      rollbackTriggered: Boolean(capitalRaw.gates?.rollbackTriggered ?? false),
      promotionLockActive: Boolean(capitalRaw.gates?.promotionLockActive ?? false),
      promotionLockUntil: capitalRaw.gates?.promotionLockUntil,
    } : undefined,
    lifecycle: life ? {
      mode: (life?.mode ?? "RULE") as "RULE" | "ML",
      shadowDecisions: Number(life?.shadowDecisions ?? 0),
      edgeDelta: Number(life?.edgeDelta ?? 0),
      cooldownRemainingDays: Number(life?.cooldownRemainingDays ?? 0),
      lastPromotion: life?.lastPromotion,
      lastRollback: life?.lastRollback,
    } : undefined,
    calibration: calib ? {
      ece: Number(calib?.ece ?? 0),
      status: (calib?.status ?? "UNKNOWN") as ReliabilityLevel,
      buckets: calib?.buckets,
    } : undefined,
    evidence: Array.isArray(evList) ? evList.slice(0, 20).map((e: any) => ({
      timestamp: e?.at ?? e?.timestamp ?? new Date().toISOString(),
      module: e?.module ?? "sentiment",
      type: e?.type ?? "unknown",
      severity: e?.severity ?? "INFO",
      message: e?.message ?? "",
      details: e?.payload ?? e?.details ?? {},
    })) : undefined,
  };
}

/**
 * Fetch Sentiment Intelligence Data (for extended admin panels)
 */
export async function getSentimentIntelligenceData(): Promise<SentimentIntelligenceData | null> {
  try {
    const res = await fetchJSON<any>(`${API_URL}/api/market/sentiment/intelligence-v1`);
    if (!res?.ok || !res?.data) return null;
    
    const d = res.data;
    return {
      regime: {
        marketRegime: d.regime?.marketRegime ?? "UNKNOWN",
        trendStrength: Number(d.regime?.trendStrength ?? 0),
      },
      distribution: {
        confidenceHistogram: d.distribution?.confidenceHistogram ?? [],
        biasDistribution: d.distribution?.biasDistribution ?? { longPct: 0, shortPct: 0, neutralPct: 1 },
      },
      performance: {
        mlEquity: d.performance?.mlEquity ?? [],
        ruleEquity: d.performance?.ruleEquity ?? [],
        rollingHitRate: Number(d.performance?.rollingHitRate ?? 0),
        rollingSharpe: Number(d.performance?.rollingSharpe ?? 0),
      },
      stability: {
        uriAdjustmentsPct: Number(d.stability?.uriAdjustmentsPct ?? 0),
        safeModePct: Number(d.stability?.safeModePct ?? 0),
        calibrationAdjustmentsPct: Number(d.stability?.calibrationAdjustmentsPct ?? 0),
        lowDataPct: Number(d.stability?.lowDataPct ?? 0),
      },
    };
  } catch (err) {
    console.error("[getSentimentIntelligenceData] Error:", err);
    return null;
  }
}
