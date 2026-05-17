/**
 * FRAGMENT LANGUAGE GOVERNANCE  ·  PHASE X · P6·α stabilization
 *
 *   This module does NOT improve writing.
 *   It REDUCES emergence.
 *
 *
 *   Core principles (these are load-bearing — do not soften):
 *
 *     · silence > weak fragment
 *     · reject > rephrase
 *     · scarcity > richness
 *     · withdraw > diversify
 *
 *
 *   Subsystems:
 *
 *     1.  FORBIDDEN PHRASES         hard reject — never emit
 *           · memory narration ("AI remembered", "we observed", ...)
 *           · LLM prose tells (echoes, whispers, journey, dance of ...)
 *           · chronology markers (then, after that, following)
 *           · UI/system leakage (signal, data, history, loading)
 *           · resolution / closure (understood, resolved, realized,
 *             learned, became clear, identified, concluded)
 *           · anthropomorphic emotion (hesitation, fear, doubt, relief,
 *             confidence returning, conviction shattered, felt, ...)
 *           · metaphor families (weather / temperature / light /
 *             water flow / body & pulse)
 *
 *     2.  DECAY-PRESSURE MEMORY     word-level usage pressure with
 *           exponential half-life.  Frequently-used distinctive words
 *           ("briefly", "lifted", "folded") gain pressure and are
 *           rejected until their pressure decays.  Connectors and
 *           function words are NOT tracked (they may repeat freely).
 *
 *     3.  REDUNDANCY DETECTION      Jaccard similarity between
 *           candidate and the 3 most recent emissions.  > 0.4 → reject.
 *
 *     4.  TAIL CLOSURE PRESSURE     terminal-pressure scoring.  Tails
 *           that conclude (rather than dissolve) are rejected.  Word
 *           count is a weak signal; closure tokens and declarative
 *           cadence are stronger.
 *
 *     5.  SEMANTIC EXHAUSTION       NOT entropy floor.  When the recent
 *           residue field clusters in suppression-family / contraction
 *           archetypes / high volume, the system becomes QUIETER by
 *           raising the emission threshold — it withdraws, it does not
 *           diversify.
 *
 *     6.  SINGLE PASSIVE VARIATION  governance allows ONE retry with
 *           an alternate seed.  Recursive rephrasing is FORBIDDEN.
 *           If the second attempt also fails → silence.
 */
import { CognitiveFragment, FragmentArchetype } from './composeFragment';
import { SemanticEnergy } from '../cognitiveTokens';

// Local pick helper — duplicated from composeFragment to avoid circular
// imports.  Same behaviour: deterministic pick by seed.
function pick<T>(seed: number, arr: readonly T[]): T {
  if (arr.length === 0) throw new Error('pick from empty');
  return arr[seed % arr.length];
}

/**
 * Load-bearing constant.  Do not remove.
 * Silence is a valid emission outcome — preferable to a weak fragment.
 */
export const SILENCE_IS_VALID = true;

// ─── 1. FORBIDDEN PHRASES ──────────────────────────────────────────

const FORBIDDEN_RE: RegExp[] = [
  // memory narration — system must not declare its own memory
  /\bai\s+(remembered|remembers|noticed|notices|observed|observes|recalled|recalls|knew|knows|sees|saw)\b/i,
  /\bthe\s+system\s+(noticed|observed|saw|understood|knows|sees)\b/i,
  /\bwe\s+(observed|noticed|saw|remember|knew|see|sense)\b/i,

  // LLM prose tells
  /\bin\s+the\s+realm\s+of\b/i,
  /\bechoes?\s+(of|through)\b/i,
  /\bwhispers?\s+of\b/i,
  /\bdance\s+of\b/i,
  /\bjourney\b/i,
  /\bdelicately\s+balanced\b/i,
  /\btapestry\b/i,
  /\bweaving\b/i,
  /\bunfurl(ed|ing)?\b/i,

  // chronology — fragments must NOT sequence
  /\bthen\b/i,
  /\bafter\s+that\b/i,
  /\bfollowing\b/i,
  /\bfirst\s+\w+\s+then\b/i,
  /\beventually\b/i,
  /\bsubsequently\b/i,

  // UI / system leakage
  /\bsignal\b/i,
  /\bdata\b/i,
  /\bhistory\b/i,
  /\bloading\b/i,
  /\blog\b/i,
  /\bevent\b/i,

  // resolution / cognitive closure — residue must NOT close
  /\b(understood|understands|understanding)\b/i,
  /\b(resolved|resolves|resolution)\b/i,
  /\b(realized|realizes|realization)\b/i,
  /\b(learned|learns|learning)\b/i,
  /\b(identified|identifies|identification)\b/i,
  /\b(concluded|concludes)\b/i,
  /\b(decided|decides|determined|determines)\b/i,
  /\bbecame\s+clear\b/i,
  /\bmade\s+sense\b/i,

  // anthropomorphic emotional leakage
  /\b(hesitation|hesitated|hesitant)\b/i,
  /\b(fear|fearful|afraid)\b/i,
  /\b(doubt|doubted|doubting|doubts)\b/i,
  /\b(relief|relieved)\b/i,
  /\bconfidence\s+returning\b/i,
  /\bconfidence\s+returned\b/i,
  /\bconviction\s+shattered\b/i,
  /\bconviction\s+broken\b/i,
  /\b(shaken|shaking)\b/i,
  /\b(feels?|felt|feeling)\b/i,
  /\b(anxious|anxiety|nervous|panic)\b/i,
  /\b(comfortable|uncomfortable)\b/i,

  // metaphor families — anthropomorphic / poetic leakage
  /\b(storm|fog|mist|cloud|thunder|rain|drizzle)\b/i,
  /\b(cold|warm|frozen|thaw|heat|chill)\b/i,
  /\b(shadow|shadows|gleam|shines?|darkness|dim)\b/i,
  /\b(tide|current|wave|waves|flowing|streaming|rippling|river)\b/i,
  /\b(heart|pulse|breath|breathing|lung)\b/i,
];

function violatesForbidden(text: string): boolean {
  if (!text) return false;
  for (const re of FORBIDDEN_RE) {
    if (re.test(text)) return true;
  }
  return false;
}

// ─── 2. DECAY-PRESSURE MEMORY ──────────────────────────────────────
//
// Per-word usage pressure with exponential decay.  Connectors and stop
// words are NOT tracked.

const WORD_HALF_LIFE_MS: Record<string, number> = {
  // Distinctive adverbs / adjectives — these stand out the most on repeat.
  briefly:      210_000,
  almost:       210_000,
  partial:      180_000,
  partially:    180_000,
  intentionally: 180_000,

  // Distinctive verbs (the "stretch" verbs — readiness/lift family)
  lifted:       180_000,
  surfaced:     180_000,
  folded:       180_000,
  dissolved:    180_000,
  thinned:      180_000,
  collapsed:    180_000,

  // Common verbs (the "hold" family)
  held:         110_000,
  thickened:    110_000,
  lingered:     110_000,
  settled:      110_000,
  gathered:     110_000,
  firmed:       110_000,

  // Subjects (these carry archetype identity)
  capital:      150_000,
  denial:       180_000,
  suppression:  120_000,  // shorter — it's the dominant residue, must rotate
  refusal:      180_000,
  hold:         150_000,
  alignment:    150_000,
  readiness:    150_000,
  conviction:   150_000,
  posture:      150_000,
  stance:       150_000,
  exposure:     150_000,
  caution:      150_000,
  position:     120_000,

  // Object/closing nouns
  moment:       180_000,
  room:         180_000,
  gate:         180_000,
  gates:        180_000,
  deployment:   180_000,
  pressure:     90_000,   // common — short HL so it can recur
};

const STOP_WORDS = new Set([
  // articles + determiners
  'the','a','an','this','that','these','those','its','it','his','her','their',
  // be / aux verbs
  'is','was','were','are','be','been','being','am','do','does','did','done',
  // pronouns / minor
  'we','i','you','he','she','they','them','us',
  // prepositions
  'of','in','to','for','with','on','by','at','from','into','over','under',
  // connectives (allowed to repeat — they're scaffolding, not meaning)
  'before','after','where','while','as','until','and','or','but','then',
  // negators (we want to permit "never", "no", "not")
  // pronouns of action
  'so','if','because',
  // punctuation tokens we may strip
  '·','—','-',
]);

type WordState = {
  lastUsedAt: number;
  amplitude: number;   // 0..1
  halfLifeMs: number;
};

// Singleton in-memory map.  Survives across navigation, dies on reload.
// That's correct: residue ecology is session-scoped, not persistent.
const wordPressure: Map<string, WordState> = new Map();

function lemmatize(w: string): string {
  let x = w.toLowerCase().replace(/[^a-z]/g, '');
  if (x.length < 4) return x;
  if (x.endsWith('ing'))      x = x.slice(0, -3);
  else if (x.endsWith('ed'))  x = x.slice(0, -2);
  else if (x.endsWith('ly'))  x = x.slice(0, -2);
  else if (x.endsWith('s'))   x = x.slice(0, -1);
  return x;
}

function tokenize(text: string): string[] {
  if (!text) return [];
  return text
    .split(/\s+/)
    .map((t) => lemmatize(t))
    .filter((t) => t.length >= 3 && !STOP_WORDS.has(t));
}

function pressureOf(word: string, now: number): number {
  const s = wordPressure.get(word);
  if (!s) return 0;
  const dt = Math.max(0, now - s.lastUsedAt);
  return s.amplitude * Math.exp(-Math.LN2 * dt / s.halfLifeMs);
}

function recordWordUsage(words: string[], now: number): void {
  for (const w of words) {
    const cur = wordPressure.get(w);
    const decayed = cur ? pressureOf(w, now) : 0;
    const hl = cur?.halfLifeMs ?? WORD_HALF_LIFE_MS[w] ?? 90_000;
    wordPressure.set(w, {
      lastUsedAt: now,
      amplitude: Math.min(1, decayed + 0.55),
      halfLifeMs: hl,
    });
  }
}

const EXHAUSTED_AT = 0.55;

function fragmentHasExhaustedWord(text: string, now: number): boolean {
  for (const w of tokenize(text)) {
    if (pressureOf(w, now) > EXHAUSTED_AT) return true;
  }
  return false;
}

// ─── 3. REDUNDANCY DETECTION (Jaccard) ────────────────────────────

function jaccard(a: Set<string>, b: Set<string>): number {
  if (a.size === 0 && b.size === 0) return 0;
  let inter = 0;
  for (const x of a) if (b.has(x)) inter++;
  const uni = a.size + b.size - inter;
  return uni === 0 ? 0 : inter / uni;
}

function similarityViolation(
  candidateTokens: Set<string>,
  recent: CognitiveFragment[],
): boolean {
  // Check against the 3 most recent emissions only.
  const slice = recent.slice(0, 3);
  for (const f of slice) {
    const txt = `${f.lead} ${f.tail ?? ''}`;
    const tokens = new Set(tokenize(txt));
    if (jaccard(candidateTokens, tokens) > 0.4) return true;
  }
  return false;
}

// ─── 4. TAIL CLOSURE PRESSURE ─────────────────────────────────────

const CLOSURE_RE: RegExp[] = [
  /\b(complete|completed|finished|finalized|done|set|sealed|over)\b/i,
  /\bfully\s+\w+/i,
  /\b(will|shall|must)\b/i,
  /\bnever\s+(again|returned|came|stabilized|confirmed)\b/i,
  /^the\s+\w+\s+(was|is|will|did|did\s+not)\b/i,
];

function tailClosurePressure(text: string | null): number {
  if (!text) return 0;
  const t = text.trim();
  if (!t) return 0;
  let score = 0;
  for (const re of CLOSURE_RE) if (re.test(t)) score += 0.4;

  // cadence: declarative weight grows past ~5 content words.
  const content = tokenize(t);
  if (content.length >= 6) score += 0.5;
  else if (content.length >= 4) score += 0.2;

  // ends with period or definitive punctuation = closure
  if (/[.!]$/.test(t)) score += 0.25;
  return Math.min(1, score);
}

const TAIL_CLOSURE_REJECT_AT = 0.55;

// ─── 5. SEMANTIC EXHAUSTION ───────────────────────────────────────
//
// When the residue field is clustered (suppression-heavy, contraction-
// heavy, or just dense in volume), the system becomes QUIETER.
// We return an exhaustion score in [0,1].  composeFragment uses this
// to RAISE the emission threshold — i.e. fewer fragments, not different
// fragments.
//
// This is silence drift, not diversity forcing.

const EXHAUSTION_WINDOW_MS = 6 * 60 * 1000;

export function semanticExhaustion(recent: CognitiveFragment[], now: number): number {
  if (recent.length === 0) return 0;
  const fresh = recent.filter((f) => (now - f.at) <= EXHAUSTION_WINDOW_MS);
  if (fresh.length === 0) return 0;

  const suppression = fresh.filter((f) => f.tone === 'suppression' || f.tone === 'caution').length;
  const suppressionRatio = suppression / fresh.length;

  const contraction = fresh.filter((f) =>
    f.archetype === 'counterfactual' || f.archetype === 'residue').length;
  const contractionRatio = contraction / fresh.length;

  // Volume: 4+ recent fragments inside the window already feels dense.
  const volume = Math.min(1, fresh.length / 4);

  // Combined — bias toward suppression clustering, since residue field
  // collapsing into one tone is the strongest exhaustion signal.
  const e =
      suppressionRatio  * 0.45
    + contractionRatio  * 0.30
    + volume            * 0.25;

  return Math.min(1, e);
}

// ─── 6. GOVERNANCE ENTRY POINT ────────────────────────────────────

export type GovernanceResult =
  | { ok: true; lead: string; tail: string | null }
  | { ok: false; reason: GovernanceReason };

export type GovernanceReason =
  | 'forbidden'
  | 'tail-closure'
  | 'word-exhausted'
  | 'redundant'
  | 'silence-drift';

export type GovernanceContext = {
  now: number;
  recentEmissions: CognitiveFragment[];
  /**
   * Caller-provided exhaustion adjustment.  composeFragment already
   * applies exhaustion at the weight-threshold layer, but governance
   * also rolls it into hard rejection when very high (≥ 0.75).
   */
  exhaustion?: number;
};

/**
 * Govern a candidate lead/tail pair.  Returns either:
 *   { ok: true, lead, tail }  → emit
 *   { ok: false, reason }     → SILENCE.  Caller may retry ONCE with
 *                                an alternate seed.  No recursive
 *                                rephrasing.
 *
 * Side effect: on ok===true, records word usage so future candidates
 * see decayed pressure.  Rejected candidates do NOT record usage.
 */
export function governCandidate(
  candidate: { lead: string; tail: string | null; archetype: FragmentArchetype; tone: SemanticEnergy },
  ctx: GovernanceContext,
): GovernanceResult {
  const { lead, tail } = candidate;
  const combined = `${lead} ${tail ?? ''}`;
  const now = ctx.now;

  // 1. Forbidden phrases (hard reject on either part).
  if (violatesForbidden(lead) || violatesForbidden(tail ?? '')) {
    return { ok: false, reason: 'forbidden' };
  }

  // 1b. Lead cap — lead must be ≤ 4 raw words (incl. articles).  We
  //     do NOT truncate; truncation breaks grammar.  Reject and let
  //     passive variation try a shorter synthesis.
  const leadRawWords = lead.trim().split(/\s+/).filter(Boolean).length;
  if (leadRawWords > 4) {
    return { ok: false, reason: 'tail-closure' };
  }

  // 2. Tail closure pressure — tail must dissolve, not conclude.
  if (tail && tailClosurePressure(tail) >= TAIL_CLOSURE_REJECT_AT) {
    return { ok: false, reason: 'tail-closure' };
  }

  // 3. Word-level decay pressure exhaustion (any distinctive content
  //    word over threshold → reject).
  if (fragmentHasExhaustedWord(combined, now)) {
    return { ok: false, reason: 'word-exhausted' };
  }

  // 4. Redundancy vs recent emissions (Jaccard).
  const tokens = new Set(tokenize(combined));
  if (similarityViolation(tokens, ctx.recentEmissions)) {
    return { ok: false, reason: 'redundant' };
  }

  // 5. Silence drift — when exhaustion is very high we additionally
  //    withdraw at the governance layer.
  if ((ctx.exhaustion ?? 0) >= 0.75) {
    return { ok: false, reason: 'silence-drift' };
  }

  // Passed.  Record word usage and return.
  recordWordUsage(Array.from(tokens), now);
  return { ok: true, lead, tail };
}

// ─── audit hooks (debugging / introspection — read-only) ─────────

export function wordPressureSnapshot(now: number): Array<{ word: string; pressure: number; halfLifeMs: number }> {
  const out: Array<{ word: string; pressure: number; halfLifeMs: number }> = [];
  for (const [w, s] of wordPressure.entries()) {
    out.push({ word: w, pressure: pressureOf(w, now), halfLifeMs: s.halfLifeMs });
  }
  return out.sort((a, b) => b.pressure - a.pressure);
}

/** Dev/test only.  Clears word pressure memory. */
export function _resetLanguageMemory(): void {
  wordPressure.clear();
  hauntingResidue = null;
}

/** Dev/test only.  Clears word pressure but PRESERVES haunting residue. */
export function _resetWordsOnly(): void {
  wordPressure.clear();
}

/** Dev/test only.  Probe maybeHauntedTail for verification. */
export function _probeMaybeHauntedTail(eventEnergy: SemanticEnergy, seed: number, now: number, scope: 'portfolio' | 'command' | 'any' = 'any'): string | null {
  return maybeHauntedTail(eventEnergy, seed, now, scope);
}

// ─── P6·β · COUNTERFACTUAL HAUNTING ────────────────────────────────
//
//   Continuity exists ONLY semantically.  Never visually.  Never
//   chronologically.  Never topically.
//
//   When a counterfactual fragment is emitted, a small invisible
//   "pressure signature" is recorded.  Future syntheses may inherit
//   that pressure — never the subject, never the verb, never the text.
//   Only an INCOMPLETION CADENCE in the tail.
//
//   Half-life: 12 minutes.  Long enough to persist through a screen
//   cycle.  Short enough that it never feels like a persistent mood.
//
//   Bias is probabilistic:
//     fresh weight 0.70  →  ~42% chance of biased tail
//     fresh weight 0.35  →  ~18% chance
//     fresh weight <0.20 →  never (signature has dissipated)
//
//   The user must NEVER be able to say "this fragment continues the
//   previous one".  The connection must feel like ambient persistence,
//   not explicit reference.

export type HauntingType =
  | 'unresolved-counterfactual'   // the strongest — by nature unresolved
  | 'sustained-contraction'        // residue archetypes piling up
  | 'persistent-suppression';      // suppression bleed across cycles

type HauntingResidueState = {
  type: HauntingType;
  bornAt: number;
  amplitude: number;     // 0..1 — gets bumped on each new haunting event
  halfLifeMs: number;    // 12 min
  energyFamily: SemanticEnergy;
};

const HAUNTING_HALF_LIFE_MS = 12 * 60 * 1000;

// Singleton signature.  Lives in module scope, session-bound.
let hauntingResidue: HauntingResidueState | null = null;

/** Record a haunting signature.  Called AFTER a fragment is emitted. */
export function recordHaunting(
  archetype: FragmentArchetype,
  tone: SemanticEnergy,
  now: number,
): void {
  // Only certain archetypes ever produce haunting.  Echo of readiness
  // produces nothing — it dissipates immediately.
  let type: HauntingType | null = null;
  if (archetype === 'counterfactual') type = 'unresolved-counterfactual';
  else if (archetype === 'residue' && (tone === 'suppression' || tone === 'caution')) type = 'persistent-suppression';
  else if (archetype === 'transition' && (tone === 'suppression' || tone === 'caution')) type = 'sustained-contraction';

  if (!type) {
    return;
  }

  // Compute the decayed weight of any existing residue and add this
  // event on top (cap at 1).
  const decayed = hauntingResidue
    ? hauntingResidue.amplitude * Math.exp(-Math.LN2 * (now - hauntingResidue.bornAt) / hauntingResidue.halfLifeMs)
    : 0;
  const amplitude = Math.min(1, decayed + 0.55);

  hauntingResidue = {
    type,
    bornAt: now,
    amplitude,
    halfLifeMs: HAUNTING_HALF_LIFE_MS,
    energyFamily: tone,
  };
}

/** Current haunting weight ∈ [0,1], decayed to now.  0 = no haunting. */
function hauntingWeightAt(now: number): number {
  if (!hauntingResidue) return 0;
  const dt = Math.max(0, now - hauntingResidue.bornAt);
  return hauntingResidue.amplitude * Math.exp(-Math.LN2 * dt / hauntingResidue.halfLifeMs);
}

/**
 * Energy topology check.  Haunting biases ONLY when the new event sits
 * inside an allowed family relative to the haunting type.
 *
 *   unresolved-counterfactual  →  readiness / expansion (echo path)
 *                                  i.e. "alignment never quite formed"
 *                                  after an earlier counterfactual
 *   persistent-suppression     →  suppression / caution (same-family)
 *   sustained-contraction      →  suppression / caution (same-family)
 *
 * Anything else returns false — no cross-pollination across the field.
 */
function topologyAllows(eventEnergy: SemanticEnergy): boolean {
  if (!hauntingResidue) return false;
  switch (hauntingResidue.type) {
    case 'unresolved-counterfactual':
      return eventEnergy === 'readiness' || eventEnergy === 'expansion';
    case 'persistent-suppression':
    case 'sustained-contraction':
      return eventEnergy === 'suppression' || eventEnergy === 'caution';
    default:
      return false;
  }
}

/**
 * Probability of biased tail given current haunting weight.
 *
 *   weight 0.70  →  ~42%
 *   weight 0.35  →  ~18%
 *   weight 0.20  →  ~8% (still present but barely)
 *   weight 0.00  →   0%
 *
 * Curve: probability = 0.6 * weight^1.1.  Subtle, sub-linear at the
 * top so even strong residue rarely overrides synthesis.
 */
function hauntingProbability(weight: number): number {
  if (weight <= 0.05) return 0;
  return Math.min(0.45, 0.6 * Math.pow(weight, 1.1));
}

/**
 * Returns either a haunted tail string or null (no haunting this time).
 * The decision is deterministic given the seed.
 *
 * P6·γ — incompletion bank is scope-aware:
 *   · portfolio: aftermath-shaped (remained closed, failed to settle)
 *   · command:   present-pressure shaped (not yet held, pressure stayed low)
 *
 * Phrases that read as both aftermath AND present (e.g. "not yet held")
 * appear in both banks.  Phrases that smell of closure (e.g. "remained
 * closed", "failed to settle") are Portfolio-only and would feel wrong
 * surfacing on a Command screen.
 */
export function maybeHauntedTail(
  eventEnergy: SemanticEnergy,
  seed: number,
  now: number,
  scope: 'portfolio' | 'command' | 'any' = 'any',
): string | null {
  const w = hauntingWeightAt(now);
  if (w < 0.05) return null;
  if (!topologyAllows(eventEnergy)) return null;

  const probability = hauntingProbability(w);
  // Deterministic roll from seed.
  const roll = (seed % 1000) / 1000;
  if (roll >= probability) return null;

  // Scope-specific banks.  Phrases that smell of closure/aftermath go
  // ONLY in the portfolio bank.  Phrases that read as present pressure
  // appear in both — but the Command bank is strictly smaller.
  const portfolioBank = [
    'not yet held',
    'left untested',
    'remained closed',
    'failed to settle',
    'pressure stayed low',
  ];
  const commandBank = [
    'not yet held',
    'left untested',
    'pressure stayed low',
  ];
  const bank = scope === 'command' ? commandBank : portfolioBank;
  return pick(seed, bank);
}

/** Inspection helper. */
export function hauntingSnapshot(now: number): { type: HauntingType; weight: number; energyFamily: SemanticEnergy } | null {
  if (!hauntingResidue) return null;
  const w = hauntingWeightAt(now);
  if (w < 0.02) return null;
  return { type: hauntingResidue.type, weight: w, energyFamily: hauntingResidue.energyFamily };
}

// ─── dev surface — read-only introspection on window ──────────────
if (typeof window !== 'undefined' && !(window as any).__cogLang) {
  (window as any).__cogLang = {
    wordPressureSnapshot,
    hauntingSnapshot,
    _resetLanguageMemory,
    _resetWordsOnly,
    _probeMaybeHauntedTail,
  };
}
