/**
 * COMPOSE FRAGMENT  ·  PHASE X · P6·α
 *
 *   Cognitive condensation.  NOT a template formatter.
 *
 *   This function takes a cognitive event (from the bus event log) plus
 *   the current residue snapshot and the most recently surfaced fragment.
 *   It MAY return a fragment.  Most of the time it returns null.
 *
 *
 *   The contract is the opposite of a renderer:
 *
 *     · An event ≠ a fragment.  Many events produce nothing.
 *     · A high-peak event may STILL produce nothing if a similar
 *       fragment was recently surfaced (coalescence).
 *     · A subtle event may produce a fragment IF the residue around it
 *       has the right semantic pressure.
 *     · The lead/tail text is composed from small word banks, not
 *       template strings, so the same archetype reads differently each
 *       time without becoming repetitive scaffolding.
 *
 *
 *   ARCHETYPES (these are NOT UI categories — they're the SHAPE of the
 *   leftover thought):
 *
 *     echo            an energy intensified · still present
 *     transition      one energy gave way to another
 *     residue         what was preserved · capital-side aftermath
 *     counterfactual  what was within reach but did not happen
 *
 *
 *   ASYMMETRY:
 *
 *     Each fragment carries an `indentSeed` ∈ [0,1].  The renderer uses
 *     this to vary horizontal indent, line wrap and tail offset — so
 *     two fragments side by side never feel like list rows.
 *
 *
 *   FORBIDDEN PATTERNS:
 *
 *     · No "AI remembered...", "the system noticed...".
 *       Memory must surface, not narrate itself.
 *     · No fixed sentence scaffolding ("AI almost deployed X here").
 *     · No timestamps, no "ago", no chrono markers.
 */
import { CognitiveEvent } from './cognitiveBus';
import { SemanticEnergy } from '../cognitiveTokens';
import { governCandidate, semanticExhaustion, maybeHauntedTail, recordHaunting } from './fragmentLanguage';

export type FragmentArchetype = 'echo' | 'transition' | 'residue' | 'counterfactual';
export type FragmentPressure  = 'authority' | 'institutional' | 'ambient';
export type FragmentScope     = 'portfolio' | 'command' | 'any';

export type CognitiveFragment = {
  id: string;
  at: number;
  archetype: FragmentArchetype;
  /** first text that surfaces — may be subjectless ('—') */
  lead: string;
  /** resolved continuation; null = thought trails off */
  tail: string | null;
  tone: SemanticEnergy;
  pressure: FragmentPressure;
  /** 0..1 → renderer maps to horizontal indent / line offset */
  indentSeed: number;
  /** which screen-temperament this fragment naturally suits */
  scope: FragmentScope;
};

// ─── deterministic seed from event id ──────────────────────────────
// Same event → same sentence shape forever.  No flicker on re-mount.
function hashSeed(s: string): number {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619) >>> 0;
  }
  return h;
}
function pick<T>(seed: number, arr: readonly T[]): T {
  if (arr.length === 0) throw new Error('pick from empty');
  return arr[seed % arr.length];
}
function nextSeed(s: number): number { return Math.imul(s, 1103515245) + 12345 >>> 0; }

// ─── classification ────────────────────────────────────────────────
type Classification = {
  archetype: FragmentArchetype;
  pressure: FragmentPressure;
  scope: FragmentScope;
  /** [0..1] — emission probability after coalescence checks */
  weight: number;
  /** the energy that was displaced/protected, if any */
  counterEnergy: SemanticEnergy | null;
};

function classify(event: CognitiveEvent): Classification {
  const isSuppression = event.energy === 'suppression';
  const isReadiness   = event.energy === 'readiness';
  const isExpansion   = event.energy === 'expansion';
  const isCaution     = event.energy === 'caution';

  // Find the most strongly dampened neighbour from coupling trace.
  let dampenedReadiness: number | null = null;
  let strongestDampening: { e: SemanticEnergy; depth: number } | null = null;
  for (const c of event.coupling) {
    if (c.delta < 0 && c.otherPrev > 0.2) {
      const depth = -c.delta * c.otherPrev;
      if (!strongestDampening || depth > strongestDampening.depth) {
        strongestDampening = { e: c.other, depth };
      }
      if (c.other === 'readiness') dampenedReadiness = depth;
    }
  }

  let archetype: FragmentArchetype = 'echo';
  let weight = 0;

  // Strong cancellation of readiness while suppression amplifies →
  // counterfactual.  Something was reaching for deployment and folded.
  if (isSuppression && dampenedReadiness != null && dampenedReadiness > 0.05) {
    archetype = 'counterfactual';
    weight   += 0.55 + Math.min(0.25, dampenedReadiness);
  }
  // Any meaningful displacement of a neighbour → transition.
  else if (strongestDampening && strongestDampening.depth > 0.03) {
    archetype = 'transition';
    weight   += 0.45 + Math.min(0.25, strongestDampening.depth * 2);
  }
  // Suppression intensifying without cancellation → residue (capital
  // protected, posture firmed without a near-miss).
  else if (isSuppression) {
    archetype = 'residue';
    weight   += 0.35 + Math.min(0.25, (event.peak - 0.55) * 1.5);
  }
  // Caution settling → quiet echo.
  else if (isCaution || isExpansion) {
    archetype = 'echo';
    weight   += 0.20 + Math.min(0.2, (event.peak - 0.55) * 1.2);
  }
  // Bare readiness amplification → faint echo, rarely worth surfacing.
  else if (isReadiness) {
    archetype = 'echo';
    weight   += 0.12 + Math.min(0.18, (event.peak - 0.55) * 1.0);
  }
  else {
    archetype = 'echo';
    weight   += 0.05;
  }

  // Peak depth bonus.
  if (event.peak >= 0.78) weight += 0.15;
  if (event.peak >= 0.9)  weight += 0.10;

  // Scope: suppression / cancellation reads as portfolio-native consequence.
  // Pure readiness or expansion are command-native presence.
  let scope: FragmentScope = 'any';
  if (archetype === 'residue' || archetype === 'counterfactual') scope = 'portfolio';
  else if (isReadiness || (isExpansion && archetype === 'echo')) scope = 'command';
  else if (archetype === 'transition' && (isSuppression || isCaution)) scope = 'portfolio';

  // Pressure: capital-level suppression reads institutional; active
  // displacement reads authority; quiet echoes read ambient.
  let pressure: FragmentPressure = 'ambient';
  if (archetype === 'counterfactual')          pressure = 'authority';
  else if (archetype === 'residue')            pressure = 'institutional';
  else if (archetype === 'transition')         pressure = 'institutional';
  else                                          pressure = 'ambient';

  return { archetype, pressure, scope, weight, counterEnergy: strongestDampening?.e ?? null };
}

// ─── word banks ────────────────────────────────────────────────────
//
// Banks are deliberately small and overlap across archetypes so each
// fragment is a remix, not a template fill.  Subjectless leads ('—')
// are mixed in so framing doesn't feel uniform.

const SUBJECT_SUPPRESSION = ['suppression', 'denial', 'the refusal', 'the hold'];
const SUBJECT_RESIDUE     = ['capital', 'the position', 'exposure', '—'];
const SUBJECT_READINESS   = ['readiness', 'alignment', 'the lift', '—'];
const SUBJECT_POSTURE     = ['the posture', 'conviction', 'the stance', '—'];

const VERB_HOLD       = ['held', 'thickened', 'lingered', 'settled in', 'firmed', 'stayed'];
const VERB_PROTECTED  = ['remained protected', 'never opened', 'was preserved', 'stayed dark'];
const VERB_FOLDED     = ['folded back', 'thinned', 'never resolved', 'dissolved before settling', 'gave way'];
const VERB_DISPLACED  = ['gave way', 'was absorbed', 'shifted', 'eased aside'];

const CONNECT_BEFORE  = ['before', 'as'];
const CONNECT_AFTER   = ['after', 'where', 'as'];
const CONNECT_WHILE   = ['while', 'as', 'where'];

// ─── tail composers ───────────────────────────────────────────────

function composeResidueTail(seed: number, counter: SemanticEnergy | null): string | null {
  if (counter === 'readiness') {
    const verb = pick(seed, VERB_FOLDED);
    return `${pick(nextSeed(seed), CONNECT_AFTER)} alignment ${verb}`;
  }
  if (counter === 'expansion') {
    return `${pick(seed, CONNECT_AFTER)} momentum faded out of reach`;
  }
  // No clear counter → about half the time leave the thought open.
  if (seed % 2 === 0) return null;
  return pick(seed, ['no deployment followed', 'the gates never cleared', 'pressure passed without action']);
}

function composeCounterfactualTail(seed: number): string | null {
  // Non-agentive variants only.  No pursuit-style verbs.  Primary
  // phrases are duplicated to weight them higher than the fallbacks
  // (denial returned, pressure absorbed it) which carry a small
  // closure / agency residue and should appear less often.
  return pick(seed, [
    'suppression held',         // primary
    'suppression held',
    'the gate stayed closed',   // primary
    'the gate stayed closed',
    'the moment passed',        // primary
    'left untested',            // primary — strongest incompletion
    'left untested',
    'pressure absorbed it',     // rare fallback (mild agency)
    'denial returned',          // rare fallback (mild closure)
  ]);
}

function composeTransitionTail(seed: number, from: SemanticEnergy | null, to: SemanticEnergy): string | null {
  const fromWord = from === 'readiness' ? 'alignment'
                : from === 'expansion'  ? 'momentum'
                : from === 'caution'    ? 'caution'
                : from === 'dormant'    ? 'the quiet'
                : 'the prior pressure';
  const toWord   = to === 'suppression' ? 'denial took the room'
                : to === 'readiness'    ? 'alignment surfaced'
                : to === 'expansion'    ? 'flow opened'
                : to === 'caution'      ? 'caution thickened'
                : 'the new pressure settled';
  // Sometimes drop the explicit "from", sometimes keep it.
  if (seed % 3 === 0) return toWord;
  return `${pick(seed, CONNECT_BEFORE)} ${fromWord} ${pick(nextSeed(seed), VERB_DISPLACED)}`;
}

function composeEchoTail(seed: number, energy: SemanticEnergy): string | null {
  if (energy === 'suppression') {
    if (seed % 3 === 0) return null;
    return pick(seed, ['the room stayed closed', 'nothing opened beneath it']);
  }
  if (energy === 'caution') {
    return pick(seed, ['the edge sharpened', 'the room narrowed slightly']);
  }
  if (energy === 'readiness') {
    return pick(seed, ['no setup confirmed', 'the lift held under threshold']);
  }
  if (seed % 2 === 0) return null;
  return pick(seed, ['it passed through without committing']);
}

// ─── COMMAND-SCOPE SYNTHESIZERS  ·  PHASE X · P6·γ ────────────────
//
//   Command lives in the PRESENT.  Its fragments describe what
//   pressure is doing now — not aftermath, not consequence, not
//   regret.  Word banks here are deliberately tight:
//
//     SUBJECTS: only abstract pressure-bearing nouns.  No metaphor
//     space ("the room", "the floor") — those leak authored mood.
//
//     VERBS: present-state pressure verbs.  No emotional distance
//     ("stayed distant"), no closure verbs ("resolved", "settled
//     finally"), no aftermath verbs ("preserved", "remained
//     protected").
//
//   The contract:
//
//     Portfolio writes residue → Command may carry it forward.
//     Command emits → no haunting is recorded.  Present does not
//     accumulate long-tail memory.

const CMD_SUBJECTS = ['readiness', 'alignment', 'pressure', 'deployment', '—'] as const;

// Present-pressure echo verbs.  Each leaves the thought open — no
// concluding cadence, no closure.
const CMD_ECHO_VERBS = [
  'thinned',
  'stayed partial',
  'stayed low',
  'held back',
  'did not settle',
] as const;

// Present-state echo tails.  Short, dissolving.
const CMD_ECHO_TAILS = [
  'nothing surfaced',
  'no setup confirmed',
  'still held under',
] as const;

// Pressure-shift transition verbs — short, no chronology.
const CMD_TRANSITION_VERBS = [
  'eased',
  'stepped back',
  'thinned',
  'settled flatter',
] as const;

const CMD_TRANSITION_TAILS = [
  'no expansion arrived',
  'pressure stayed even',
  'nothing moved',
] as const;

function leadForEchoCommand(seed: number, _energy: SemanticEnergy): string {
  const s = pick(seed, CMD_SUBJECTS);
  const v = pick(nextSeed(seed), CMD_ECHO_VERBS);
  if (s === '—') return v.charAt(0).toUpperCase() + v.slice(1);
  return `${s} ${v}`;
}

function composeEchoTailCommand(seed: number, _energy: SemanticEnergy): string | null {
  if (seed % 3 === 0) return null;  // ~33% trail off without tail
  return pick(seed, CMD_ECHO_TAILS);
}

function leadForTransitionCommand(seed: number, _energy: SemanticEnergy): string {
  const s = pick(seed, CMD_SUBJECTS);
  const v = pick(nextSeed(seed), CMD_TRANSITION_VERBS);
  if (s === '—') return v.charAt(0).toUpperCase() + v.slice(1);
  return `${s} ${v}`;
}

function composeTransitionTailCommand(seed: number, _from: SemanticEnergy | null, _to: SemanticEnergy): string | null {
  if (seed % 4 === 0) return null;
  return pick(seed, CMD_TRANSITION_TAILS);
}

// ─── lead composers ───────────────────────────────────────────────

function leadForResidue(seed: number): string {
  const s = pick(seed, SUBJECT_RESIDUE);
  const v = pick(nextSeed(seed), VERB_PROTECTED);
  if (s === '—') return '—';
  return `${s} ${v}`;
}

function leadForCounterfactual(seed: number, energy: SemanticEnergy): string {
  // We want to convey "something was reaching for action and folded".
  // All verb phrases here must keep the lead ≤ 4 content words once a
  // subject is prepended — governance rejects longer leads outright.
  const subjectChoices = energy === 'suppression' ? SUBJECT_READINESS : SUBJECT_POSTURE;
  const s = pick(seed, subjectChoices);
  const v = pick(nextSeed(seed), ['lifted briefly', 'almost surfaced', 'never settled', 'almost reached']);
  if (s === '—') return v.charAt(0).toUpperCase() + v.slice(1);
  return `${s} ${v}`;
}

function leadForTransition(seed: number, energy: SemanticEnergy): string {
  if (energy === 'suppression') {
    const s = pick(seed, SUBJECT_SUPPRESSION);
    return `${s} ${pick(nextSeed(seed), VERB_HOLD)}`;
  }
  const s = pick(seed, SUBJECT_POSTURE);
  if (s === '—') return pick(seed, ['the room shifted', 'pressure rearranged']);
  return `${s} shifted`;
}

function leadForEcho(seed: number, energy: SemanticEnergy): string {
  if (energy === 'suppression') {
    const s = pick(seed, SUBJECT_SUPPRESSION);
    return `${s} ${pick(nextSeed(seed), VERB_HOLD)}`;
  }
  if (energy === 'caution') {
    const s = pick(seed, ['caution', '—']);
    return s === '—' ? 'a quiet warning settled' : 'caution thickened';
  }
  if (energy === 'readiness') {
    return pick(seed, ['alignment surfaced briefly', 'a partial lift']);
  }
  return pick(seed, ['the room held', 'pressure registered']);
}

// ─── main composer ────────────────────────────────────────────────

/**
 * Coalescence policy.  An event that arrives within `coalesceWindowMs`
 * of a structurally similar prior fragment is absorbed into the prior
 * (i.e. nothing new is emitted).  This is what keeps fragments rare.
 */
const COALESCE_WINDOW_MS = 90 * 1000;
const MIN_WEIGHT_TO_EMIT  = 0.50;
const MIN_GLOBAL_GAP_MS   = 60 * 1000;

export type ComposeContext = {
  /** Most recently emitted fragment of any scope, anywhere in the app. */
  lastEmitted: CognitiveFragment | null;
  /** Most recent fragment of the SAME archetype, for similarity merging. */
  lastSameArchetype: CognitiveFragment | null;
  /**
   * Recent emissions (newest first) — passed to language governance for
   * Jaccard redundancy detection and semantic-exhaustion calculation.
   * Up to ~6 entries is enough.
   */
  recentEmissions?: CognitiveFragment[];
};

// ─── lead/tail synthesis (seed-driven, no governance) ────────────

function synthesize(
  archetype: FragmentArchetype,
  event: CognitiveEvent,
  counterEnergy: SemanticEnergy | null,
  seed: number,
  hauntedTail: string | null = null,
  scope: 'portfolio' | 'command' | 'any' = 'any',
): { lead: string; tail: string | null } {
  let lead: string;
  let tail: string | null;

  // Command domain uses present-pressure synthesizers — strictly
  // separate banks (no aftermath / no closure / no metaphor space).
  // Counterfactual + residue archetypes are blocked at classify level
  // for command scope, so we only have to handle echo / transition here.
  if (scope === 'command') {
    switch (archetype) {
      case 'transition':
        lead = leadForTransitionCommand(seed, event.energy);
        tail = composeTransitionTailCommand(nextSeed(seed), counterEnergy, event.energy);
        break;
      case 'echo':
      default:
        lead = leadForEchoCommand(seed, event.energy);
        tail = composeEchoTailCommand(nextSeed(seed), event.energy);
        break;
    }
  } else {
    switch (archetype) {
      case 'residue':
        lead = leadForResidue(seed);
        tail = composeResidueTail(nextSeed(seed), counterEnergy);
        break;
      case 'counterfactual':
        lead = leadForCounterfactual(seed, event.energy);
        tail = composeCounterfactualTail(nextSeed(seed));
        break;
      case 'transition':
        lead = leadForTransition(seed, event.energy);
        tail = composeTransitionTail(nextSeed(seed), counterEnergy, event.energy);
        break;
      case 'echo':
      default:
        lead = leadForEcho(seed, event.energy);
        tail = composeEchoTail(nextSeed(seed), event.energy);
        break;
    }
  }

  // Apply haunting tail override AFTER synthesis but BEFORE governance.
  // Haunting only ever replaces the tail — never the lead, never the
  // subject.  Governance still gates it, so a haunted tail can be
  // rejected exactly like any other tail.
  if (hauntedTail) {
    tail = hauntedTail;
  }

  return { lead, tail };
}

export function composeFragment(
  event: CognitiveEvent,
  ctx: ComposeContext,
): CognitiveFragment | null {
  const cls = classify(event);

  // NOTE: We deliberately do NOT short-circuit on cls.weight here.
  // The effective-threshold gate below composes base + exhaustion -
  // hauntingPermission - commandPermission, so Command echoes and
  // haunting-permitted readiness events can surface at lower weights.
  // An early `if (cls.weight < MIN_WEIGHT_TO_EMIT) return null;` would
  // strangle those paths.

  // Global rarity: no two surface-emissions inside MIN_GLOBAL_GAP_MS.
  if (ctx.lastEmitted && (event.at - ctx.lastEmitted.at) < MIN_GLOBAL_GAP_MS) {
    return null;
  }

  // Structural coalescence: same archetype + same tone too recently →
  // absorb silently.
  if (
    ctx.lastSameArchetype
    && ctx.lastSameArchetype.tone === event.energy
    && (event.at - ctx.lastSameArchetype.at) < COALESCE_WINDOW_MS
  ) {
    return null;
  }

  // Semantic exhaustion → silence drift.  We raise the effective
  // weight threshold (NOT the rejection probability — system gets
  // QUIETER, it does not get more diverse).
  const exhaustion = semanticExhaustion(ctx.recentEmissions ?? [], event.at);

  const seed = hashSeed(event.id);
  const indentSeed = (seed >>> 8) % 1000 / 1000;

  // P6·β · counterfactual haunting.  Maybe inject an incompletion tail
  // from active haunting residue.  Returns null if no haunting, or if
  // topology / probability declines.  Deterministic given seed.
  // We compute this BEFORE the weight gate so haunting can apply a
  // small "permission" — letting a weaker event surface specifically
  // because unresolved pressure wants out.
  //
  // P6·γ — for command scope we pass the scope hint so haunted tail
  // synthesis can use the present-pressure incompletion bank.
  const hauntedTail = maybeHauntedTail(event.energy, seed, event.at, cls.scope);
  const isHauntedAttempt = hauntedTail !== null;

  // Threshold composition:
  //   base = MIN_WEIGHT_TO_EMIT
  //   + exhaustion penalty (system gets quieter as residue clusters)
  //   - haunting permission (only when exhaustion is low, and only
  //     enough to surface a sub-threshold echo carrying incompletion)
  //   - command permission (P6·γ — Command echo/transition emit ambient
  //     present pressure, so threshold relaxes slightly without need
  //     for haunting).
  const baseThreshold = MIN_WEIGHT_TO_EMIT + exhaustion * 0.45;
  const hauntingPermission = (isHauntedAttempt && exhaustion < 0.40)
    ? Math.min(0.25, (1 - exhaustion / 0.40) * 0.25)
    : 0;
  const commandPermission = (cls.scope === 'command' && (cls.archetype === 'echo' || cls.archetype === 'transition') && exhaustion < 0.40)
    ? Math.min(0.22, (1 - exhaustion / 0.40) * 0.22)
    : 0;
  const effectiveThreshold = Math.max(0.22, baseThreshold - hauntingPermission - commandPermission);
  if (cls.weight < effectiveThreshold) return null;

  // Synthesize candidate.  Run governance.  Single passive variation
  // allowed: if governance rejects, retry ONCE with an alternate seed.
  // If the alternate also fails → silence.  No recursive rephrasing.
  // The PASSIVE VARIATION drops the haunting override — it's the
  // "step back" attempt, not a retry that doubles down on the haunt.
  const candidate1 = synthesize(cls.archetype, event, cls.counterEnergy, seed, hauntedTail, cls.scope);
  let governed = governCandidate(
    { lead: candidate1.lead, tail: candidate1.tail, archetype: cls.archetype, tone: event.energy },
    { now: event.at, recentEmissions: ctx.recentEmissions ?? [], exhaustion },
  );

  if (!governed.ok) {
    // ONE passive variation — alternate seed, NO haunting injection.
    const altSeed = nextSeed(nextSeed(seed));
    const candidate2 = synthesize(cls.archetype, event, cls.counterEnergy, altSeed, null, cls.scope);
    governed = governCandidate(
      { lead: candidate2.lead, tail: candidate2.tail, archetype: cls.archetype, tone: event.energy },
      { now: event.at, recentEmissions: ctx.recentEmissions ?? [], exhaustion },
    );
    if (!governed.ok) return null;  // silence
  }

  // P6·γ asymmetry — Command does NOT write haunting.
  //
  //   Portfolio writes residue → Command may carry it forward.
  //   Command emits → no haunting is recorded.  Present does not
  //   accumulate long-tail memory.
  //
  // This keeps the cognition asymmetric: aftermath drives future
  // pressure, but present does not accumulate residue beyond its
  // moment.
  if (cls.scope !== 'command') {
    recordHaunting(cls.archetype, event.energy, event.at);
  }

  return {
    id: `frag-${event.id}`,
    at: event.at,
    archetype: cls.archetype,
    lead: governed.lead,
    tail: governed.tail,
    tone: event.energy,
    pressure: cls.pressure,
    indentSeed,
    scope: cls.scope,
  };
}

// ─── batch derivation for hooks ───────────────────────────────────

/**
 * Walk a list of events (newest first) and emit up to `max` fragments.
 * Applies global rarity, structural coalescence and scope filtering.
 *
 *   composeFragments(events, { scope: 'portfolio', max: 2 })
 */
export function composeFragments(
  eventsNewestFirst: CognitiveEvent[],
  opts: { scope?: FragmentScope; max?: number; maxAgeMs?: number },
): CognitiveFragment[] {
  const max      = opts.max ?? 2;
  const scope    = opts.scope ?? 'any';
  const maxAgeMs = opts.maxAgeMs ?? 12 * 60 * 1000;
  const now      = Date.now();

  // Walk OLDEST → NEWEST so coalescence sees prior fragments as it
  // would have at the time.
  const ordered = eventsNewestFirst
    .filter((e) => (now - e.at) <= maxAgeMs)
    .slice()
    .reverse();

  const emitted: CognitiveFragment[] = [];

  for (const e of ordered) {
    const lastEmitted        = emitted[emitted.length - 1] ?? null;
    const lastSameArchetype  = (() => {
      const cls = classify(e);
      for (let i = emitted.length - 1; i >= 0; i--) {
        if (emitted[i].archetype === cls.archetype) return emitted[i];
      }
      return null;
    })();
    // Provide governance with the recent emissions (newest first).
    // Capped at 6 — anything older than that has decayed enough at the
    // word-pressure layer that it stops mattering.
    const recentEmissions = emitted.slice().reverse().slice(0, 6);
    const frag = composeFragment(e, { lastEmitted, lastSameArchetype, recentEmissions });
    if (!frag) continue;
    if (scope !== 'any' && frag.scope !== 'any' && frag.scope !== scope) continue;
    emitted.push(frag);
  }

  // Return newest first, capped.
  return emitted.reverse().slice(0, max);
}
