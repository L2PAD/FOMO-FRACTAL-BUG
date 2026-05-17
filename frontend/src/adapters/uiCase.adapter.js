/**
 * UI Case Adapter — View Model Factory
 * Decides everything for the UI. UI only draws.
 * Labels have color classes (text color only, no backgrounds/borders).
 */

const STATUS = {
  ENTRY:  { key: 'entry',  label: 'Entry',   color: 'text-emerald-600' },
  MOVING: { key: 'moving', label: 'Moving',  color: 'text-blue-600' },
  WATCH:  { key: 'watch',  label: 'Watch',   color: 'text-gray-500' },
  AVOID:  { key: 'avoid',  label: 'Avoid',   color: 'text-red-500' },
};

function resolveStatus(c) {
  const action = c.recommendation?.action;
  const repr = c.repricing?.repricing_state;
  const entry = c.entry_timing?.entry_action;
  const sizing = c.sizing?.allowed;

  if (action === 'AVOID' || c.portfolio?.blocked) return STATUS.AVOID;
  if (entry === 'do_not_enter' && action === 'AVOID') return STATUS.AVOID;
  if (action === 'NO_NOW' || action === 'NO_SMALL') return STATUS.AVOID;
  if ((action === 'YES_NOW' || action === 'YES_SMALL') && entry !== 'too_late') return STATUS.ENTRY;
  if (
    repr === 'active_repricing' || repr === 'late_repricing' ||
    entry === 'too_late' ||
    (c.repricing?.speed_score > 0.4 && c.repricing?.volume_confirmation > 0.5)
  ) return STATUS.MOVING;
  if (
    (action === 'YES_NOW' || action === 'YES_SMALL' || action === 'GOOD_IDEA_BAD_PRICE') &&
    sizing !== false
  ) return STATUS.ENTRY;
  if (action === 'WATCH' || action === 'WAIT') return STATUS.WATCH;
  if (c.analysis?.net_edge > 0.05) return STATUS.WATCH;
  return STATUS.AVOID;
}

// Color: green=high, amber=medium, red=low
function edgeLabel(netEdge) {
  const pct = Math.abs(netEdge || 0) * 100;
  if (pct >= 12) return { text: 'High', color: 'text-emerald-600' };
  if (pct >= 5)  return { text: 'Medium', color: 'text-amber-600' };
  return { text: 'Low', color: 'text-red-500' };
}

function confidenceLabel(conf) {
  const pct = (conf || 0) * 100;
  if (pct >= 60) return { text: 'High', color: 'text-emerald-600' };
  if (pct >= 35) return { text: 'Medium', color: 'text-amber-600' };
  return { text: 'Low', color: 'text-red-500' };
}

function entryTypeLabel(c) {
  const style = (c.executionLayer || {}).entryStyle;
  const map = {
    ENTER_MARKET: 'Market', ENTER_LIMIT: 'Limit', STAGGER_LIMIT: 'Stagger',
    WAIT_RETRACE: 'Retrace', WAIT_CONFIRMATION: 'Wait Confirm', DO_NOT_CHASE: 'Do Not Chase',
  };
  return map[style] || null;
}

function buildSummary(c) {
  const edge = (c.analysis?.net_edge || 0) * 100;
  const conf = (c.analysis?.model_confidence || 0) * 100;
  const repr = c.repricing || {};
  const entry = c.entry_timing || {};
  const exec = c.executionLayer || {};
  const pricing = c.pricing?.market_state;

  if (repr.repricing_state === 'active_repricing' && edge > 5)
    return 'Market started moving, but potential not yet realized';
  if (repr.repricing_state === 'fresh_mispricing' && edge > 8)
    return 'Strong divergence — market hasn\'t started reacting';
  if (edge > 10 && conf > 55)
    return 'Strong signal, market underpricing the move';
  if (edge > 8 && conf < 40)
    return 'Divergence exists, but not enough confirmations';
  if (entry.entry_action === 'too_late' || repr.repricing_state === 'late_repricing')
    return 'Main move already happened, entry window missed';
  if (pricing === 'overheated' || repr.repricing_state === 'overheated')
    return 'Market overheated — high reversal risk';
  if (c.recommendation?.action === 'GOOD_IDEA_BAD_PRICE')
    return 'Good idea, but entry price is currently unfavorable';
  if (exec.entryQualityScore < 0.4 && edge > 5)
    return 'Signal exists, but entry is technically poor right now';
  if (conf < 35)
    return 'Weak signal, not enough confirmations';
  if (edge > 5 && conf >= 35)
    return 'Moderate signal — market hasn\'t fully priced the event';
  if (edge > 3)
    return 'Signal forming, needs additional confirmations';
  if (edge <= 2)
    return 'Minimal divergence, not worth the wait';
  return 'Uncertain situation, monitoring';
}

function buildActionLabel(c, status) {
  const entryType = entryTypeLabel(c);
  if (status.key === 'entry') return entryType ? `Enter (${entryType})` : 'Enter';
  if (status.key === 'moving') return 'Cautious Entry';
  if (status.key === 'watch') return 'Watch';
  return 'Skip';
}

// "Hot" score: higher = more attention-worthy
function computeHeatScore(c) {
  const edge = Math.abs(c.analysis?.net_edge || 0) * 100;
  const conf = (c.analysis?.model_confidence || 0) * 100;
  const repr = c.repricing || {};
  let heat = 0;
  if (edge > 12) heat += 3;
  else if (edge > 8) heat += 2;
  else if (edge > 5) heat += 1;
  if (conf > 60) heat += 2;
  else if (conf > 40) heat += 1;
  if (repr.repricing_state === 'fresh_mispricing') heat += 2;
  if (repr.repricing_state === 'active_repricing') heat += 1;
  return heat;
}

function buildDecisionBlock(c) {
  return { whyNow: (c.why_now || []).slice(0, 3), whyNot: (c.why_not || []).slice(0, 3) };
}

function buildPictureBlock(c) {
  const intel = c.intelligence || {};
  const thesis = intel.thesis || {};
  const memo = intel.memo || {};
  return {
    bull: thesis.bullCase?.arguments?.slice(0, 3) || c.projectIntel?.bullCase?.slice(0, 3) || [],
    bear: thesis.bearCase?.arguments?.slice(0, 3) || c.projectIntel?.bearCase?.slice(0, 3) || [],
    marketGap: (memo.whatMarketMisses || []).filter(m => m !== 'No obvious mispricing detected').slice(0, 2),
  };
}

function buildExecutionBlock(c) {
  const el = c.executionLayer || {};
  const es = c.executionScore || {};
  const sizing = c.sizing || {};
  const qPct = el.entryQualityScore ? Math.round(el.entryQualityScore * 100) : null;
  let qualityLabel = { text: 'Unknown', color: 'text-gray-500' };
  if (qPct !== null) {
    if (qPct >= 70) qualityLabel = { text: 'Good', color: 'text-emerald-600' };
    else if (qPct >= 45) qualityLabel = { text: 'Average', color: 'text-amber-600' };
    else qualityLabel = { text: 'Weak', color: 'text-red-500' };
  }
  let slippageLabel = { text: 'Low', color: 'text-emerald-600' };
  if (el.slippageRisk > 0.5) slippageLabel = { text: 'High', color: 'text-red-500' };
  else if (el.slippageRisk > 0.25) slippageLabel = { text: 'Medium', color: 'text-amber-600' };
  const scalingMap = {
    ADD: { text: 'Add', color: 'text-emerald-600' },
    HOLD: { text: 'Hold', color: 'text-blue-600' },
    NO_ADD: { text: 'No Add', color: 'text-red-500' },
  };
  const scalingLabel = scalingMap[el.scalingBias] || null;
  // Grade color
  let gradeColor = 'text-gray-500';
  if (es.grade === 'A' || es.grade === 'A+') gradeColor = 'text-emerald-600';
  else if (es.grade === 'B' || es.grade === 'B+') gradeColor = 'text-blue-600';
  else if (es.grade === 'C') gradeColor = 'text-amber-600';
  else if (es.grade === 'D' || es.grade === 'F') gradeColor = 'text-red-500';

  return {
    entryType: entryTypeLabel(c), qualityLabel, qualityPct: qPct, slippageLabel,
    scalingLabel,
    riskFlags: (sizing.risk_flags || []).slice(0, 3),
    grade: es.grade || null, gradeColor,
    raw: { entryQualityScore: el.entryQualityScore, chaseRisk: el.chaseRisk, missRisk: el.missRisk,
      spreadRegime: el.spreadRegime, depthQuality: el.depthQuality, slippageRisk: el.slippageRisk,
      edgeCompression: el.edgeCompression, maxSlippageBps: el.maxSlippageBps,
      exitAction: el.exitAction, exitReasons: el.exitReasons }
  };
}

function buildProjectBlock(c) {
  const pi = c.projectIntel || {};
  if (!pi.verdict) return null;
  const map = {
    STRONG: { text: 'Strong', color: 'text-emerald-600' },
    WEAK: { text: 'Weak', color: 'text-red-500' },
    NEUTRAL: { text: 'Neutral', color: 'text-gray-500' },
    MODERATE: { text: 'Moderate', color: 'text-amber-600' },
  };
  const verdict = map[pi.verdict] || { text: pi.verdict, color: 'text-gray-500' };
  return {
    verdict, verdictRaw: pi.verdict,
    bullCase: pi.bullCase?.slice(0, 3) || [], bearCase: pi.bearCase?.slice(0, 3) || [],
    keyRisks: pi.keyRisks?.slice(0, 3) || [],
  };
}

function buildTechLayer(c) {
  const a = c.analysis || {};
  const p = c.pricing || {};
  return {
    fairProb: a.fair_prob, marketProb: a.market_prob, rawEdge: a.raw_edge, netEdge: a.net_edge,
    modelConfidence: a.model_confidence, alignmentScore: a.alignment_score, regime: a.regime,
    components: a.components, biases: a.biases, repricing: c.repricing || {}, entryTiming: c.entry_timing || {},
    risk: a.structural_risk || {}, pricing: p, resolution: c.resolution,
    socialIntel: c.socialIntel, portfolio: c.portfolio, volume: c.volume, liquidity: c.liquidity,
  };
}

export function mapCaseToUICase(c) {
  const status = resolveStatus(c);
  const heat = computeHeatScore(c);
  return {
    id: c.market_id, question: c.question, asset: c.asset,
    status, statusKey: status.key, statusLabel: status.label, statusColor: status.color,
    edge: edgeLabel(c.analysis?.net_edge),
    confidence: confidenceLabel(c.analysis?.model_confidence),
    summary: buildSummary(c),
    actionLabel: buildActionLabel(c, status),
    entryType: entryTypeLabel(c),
    heat, // 0-7, higher = hotter signal
    isHot: heat >= 4, // worth paying attention to
    decision: buildDecisionBlock(c), picture: buildPictureBlock(c),
    execution: buildExecutionBlock(c), project: buildProjectBlock(c),
    tech: buildTechLayer(c), _raw: c,
  };
}

export function mapAllCases(sections) {
  const all = [];
  const keys = ['best_opportunities', 'emerging_opportunities', 'entry_windows_open',
    'new_mispricings', 'repricing_now', 'state_changes', 'watchlist', 'late_moves', 'avoid_zone'];
  for (const key of keys) { for (const c of (sections[key] || [])) { all.push(mapCaseToUICase(c)); } }
  return all;
}

export function groupByStatus(uiCases) {
  const g = { entry: [], moving: [], watch: [], avoid: [] };
  for (const c of uiCases) g[c.statusKey].push(c);
  const ev = (c) => Math.abs(c.tech?.netEdge || 0);
  for (const k of Object.keys(g)) g[k].sort((a, b) => ev(b) - ev(a));
  return g;
}

export function getTopOpportunities(uiCases, limit = 3) {
  return uiCases
    .filter(c => c.statusKey === 'entry' || c.statusKey === 'moving')
    .sort((a, b) => Math.abs(b.tech?.netEdge || 0) - Math.abs(a.tech?.netEdge || 0))
    .slice(0, limit);
}

export function getTopRisks(uiCases) {
  return uiCases
    .filter(c => c.statusKey === 'avoid' && (c.tech?.risk?.combined_risk || 0) > 0.3)
    .slice(0, 3)
    .map(c => ({ asset: c.asset, reason: c.summary, case: c }));
}

export function fillIfEmpty(primary, fallback, minCount = 3) {
  if (primary.length >= minCount) return primary;
  const ids = new Set(primary.map(c => c.id));
  return [...primary, ...fallback.filter(c => !ids.has(c.id)).slice(0, minCount - primary.length)];
}
