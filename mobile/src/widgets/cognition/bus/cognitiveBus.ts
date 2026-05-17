/**
 * COGNITIVE BUS  ·  Iteration P5
 *
 *   Persistent ambient intelligence state — NOT a global UI store.
 *
 *   This is a "cognitive residue graph": a weighted, decaying, coupled
 *   collection of the AI's overlapping mental energies.  States are not
 *   "active" or "inactive" — they have AMPLITUDE that decays over time
 *   based on their half-life, and they BLEED into / SUPPRESS each
 *   other through coupling.
 *
 *   The user reads no list of states.  They feel:
 *     · cognition lingering across screens after suppression
 *     · ambient tension carrying into Feed after capital protection
 *     · readiness fading slowly when no setups appear
 *     · suppression dampening engagement
 *
 *
 *   ARCHITECTURE RULES (read me before touching this file)
 *
 *     · NEVER expose a single "currentState" string.  The whole point
 *       is overlap.
 *     · NEVER force a state by writing `weight = 1`.  Use `pulse()`
 *       which respects coupling and prior residue.
 *     · NEVER set up component-level timers.  Decay is computed at
 *       READ TIME from `lastAmplifiedAt` + half-life.
 *     · A single module-level ticker forces re-renders so the UI sees
 *       the decay.  No more tickers.  Adding tickers will desync.
 *
 *
 *   COUPLING TABLE
 *
 *     suppression amplifies → defensive bleed
 *     suppression  dampens → readiness, expansion
 *     readiness    amplifies → expansion (engagement bleed)
 *     expansion    lifts     → caution (volatility risk acknowledgment)
 *
 *
 *   HALF-LIFE TABLE  (calm-set; tune by feel, not by tests)
 *
 *     suppression  4m   capital safety lingers
 *     dormant      8m   ambient baseline
 *     compression  3m
 *     readiness    2m
 *     expansion    2.5m
 *     caution      2m
 *     flux         1.5m mid-state · fast decay
 */
import { useEffect } from 'react';
import { create } from 'zustand';
import { CognitiveCategory, SemanticEnergy, tokenFor, tokenForState } from '../cognitiveTokens';
import { CognitiveFragment, FragmentScope, composeFragments } from './composeFragment';

// ─── half-life table (ms) ───────────────────────────────────────────
const HALF_LIFE: Record<SemanticEnergy, number> = {
  suppression: 4 * 60 * 1000,
  readiness:   2 * 60 * 1000,
  expansion:   2.5 * 60 * 1000,
  compression: 3 * 60 * 1000,
  caution:     2 * 60 * 1000,
  flux:        90 * 1000,
  dormant:     8 * 60 * 1000,
};

// ─── coupling: how one energy bleeds into another on amplification ──
// values are immediate weight transfers in the range [-0.2, +0.2].
const COUPLING: Partial<Record<SemanticEnergy, Partial<Record<SemanticEnergy, number>>>> = {
  suppression: { readiness: -0.15, expansion: -0.10, caution: +0.06 },
  readiness:   { expansion: +0.05, dormant: -0.10 },
  expansion:   { caution: +0.04, dormant: -0.05 },
  caution:     { readiness: -0.04 },
};

// ─── residue node ───────────────────────────────────────────────────
type ResidueNode = {
  amplitude: number;       // last set peak (0..1)
  lastAmplifiedAt: number; // ms epoch
  halfLifeMs: number;
};

function decayedWeight(n: ResidueNode, now: number): number {
  const dt = Math.max(0, now - n.lastAmplifiedAt);
  return n.amplitude * Math.exp(-Math.LN2 * dt / n.halfLifeMs);
}

// ─── store ──────────────────────────────────────────────────────────
type Residue = Partial<Record<SemanticEnergy, ResidueNode>>;

// ─── COGNITIVE EVENTS · P6·α ────────────────────────────────────────
//
// Auto-recorded reflective events.  NOT every pulse.  ONLY significant
// transitions:
//   · suppression amplified from quiet → loud
//   · readiness reached >0.55 then was dampened by coupling
//   · dominant energy flipped priority class (e.g. expansion → suppression)
//
// These are the substrate for P6·α reflective fragments.
export type CognitiveEventKind = 'amplified' | 'cancelled' | 'flipped';

export type CognitiveEvent = {
  id: string;
  at: number;
  kind: CognitiveEventKind;
  energy: SemanticEnergy;
  peak: number;
  prevWeight: number;
  /** Coupling effects this event caused on other energies. */
  coupling: Array<{ other: SemanticEnergy; delta: number; otherPrev: number }>;
  /** Optional caller-supplied narrative seed. */
  hint?: string;
};

const MAX_EVENTS = 30;
const SIG_PEAK = 0.55;
const SIG_PREV = 0.35;

type Bus = {
  residue: Residue;
  events: CognitiveEvent[];
  tickCounter: number;
  pulse: (energy: SemanticEnergy, amount: number, hint?: string) => void;
  weightOf: (energy: SemanticEnergy) => number;
  dominant: () => { energy: SemanticEnergy; weight: number; score: number } | null;
  snapshot: () => Array<{ energy: SemanticEnergy; weight: number }>;
  recentEvents: (max?: number, maxAgeMs?: number) => CognitiveEvent[];
  _tick: () => void;
};

export const useCognitiveBus = create<Bus>((set, get) => ({
  residue: {},
  events: [],
  tickCounter: 0,

  pulse: (energy, amount, hint) => {
    if (amount <= 0) return;
    const now = Date.now();
    let recordedEvent: CognitiveEvent | null = null;
    const couplingTrace: CognitiveEvent['coupling'] = [];

    set((s) => {
      const next: Residue = { ...s.residue };

      // decay-then-amplify on the target node
      const cur = next[energy];
      const decayed = cur ? decayedWeight(cur, now) : 0;
      const newAmp = Math.min(1, decayed + amount);
      next[energy] = {
        amplitude: newAmp,
        lastAmplifiedAt: now,
        halfLifeMs: HALF_LIFE[energy],
      };

      // apply coupling — bleed / suppress neighbouring states
      const c = COUPLING[energy] || {};
      for (const otherK in c) {
        const other = otherK as SemanticEnergy;
        const dW = c[other] ?? 0;
        if (dW === 0) continue;
        const o = next[other];
        const od = o ? decayedWeight(o, now) : 0;
        const oNew = Math.max(0, Math.min(1, od + dW));
        next[other] = {
          amplitude: oNew,
          lastAmplifiedAt: now,
          halfLifeMs: HALF_LIFE[other],
        };
        couplingTrace.push({ other, delta: dW, otherPrev: od });
      }

      // ── P6·α — record significant cognitive event
      // Only suppression / readiness / expansion / caution worth remembering.
      // dormant / flux are baseline noise.
      const isMeaningful =
        energy !== 'dormant' && energy !== 'flux' &&
        newAmp >= SIG_PEAK && decayed < SIG_PREV;
      if (isMeaningful) {
        // detect kind:
        //   cancelled — coupling dampened another energy meaningfully
        //   flipped   — priority class shifted vs previous dominant
        //   amplified — default
        let kind: CognitiveEventKind = 'amplified';
        const dampened = couplingTrace.find((c2) => c2.delta < -0.05 && c2.otherPrev > 0.25);
        if (dampened) kind = 'cancelled';

        recordedEvent = {
          id: `${now}-${energy}`,
          at: now,
          kind,
          energy,
          peak: newAmp,
          prevWeight: decayed,
          coupling: couplingTrace.slice(),
          hint,
        };
      }

      return { residue: next };
    });

    if (recordedEvent) {
      set((s) => ({
        events: [recordedEvent!, ...s.events].slice(0, MAX_EVENTS),
      }));
    }
  },

  weightOf: (energy) => {
    const r = get().residue[energy];
    return r ? decayedWeight(r, Date.now()) : 0;
  },

  dominant: () => {
    const r = get().residue;
    const now = Date.now();
    let best: { energy: SemanticEnergy; weight: number; score: number } | null = null;
    for (const k in r) {
      const energy = k as SemanticEnergy;
      const w = decayedWeight(r[energy]!, now);
      if (w < 0.06) continue; // ignore noise
      const score = w * tokenFor(energy).priority;
      if (!best || score > best.score) best = { energy, weight: w, score };
    }
    return best;
  },

  snapshot: () => {
    const r = get().residue;
    const now = Date.now();
    const out: Array<{ energy: SemanticEnergy; weight: number }> = [];
    for (const k in r) {
      const energy = k as SemanticEnergy;
      const w = decayedWeight(r[energy]!, now);
      out.push({ energy, weight: w });
    }
    return out.sort((a, b) => b.weight - a.weight);
  },

  recentEvents: (max = 5, maxAgeMs = 15 * 60 * 1000) => {
    const now = Date.now();
    return get().events.filter((e) => (now - e.at) <= maxAgeMs).slice(0, max);
  },

  _tick: () => set((s) => ({ tickCounter: s.tickCounter + 1 })),
}));

// ─── single module-level ticker ─────────────────────────────────────
// Forces consumers to re-render every 5s so decay becomes visible.
// One ticker per app lifecycle — DO NOT register more.
let TICKER_REGISTERED = false;
function ensureTicker(): void {
  if (TICKER_REGISTERED) return;
  TICKER_REGISTERED = true;
  setInterval(() => useCognitiveBus.getState()._tick(), 5000);
}

// ─── dev-only inspection handle ────────────────────────────────────
// Exposes the bus on window for ad-hoc debugging and screenshot
// validation of P6 fragment emergence.  Production builds may keep
// this; it is read-only and side-effect-free at import time.
if (typeof window !== 'undefined' && !(window as any).__cogBus) {
  (window as any).__cogBus = useCognitiveBus;
  // Also expose composeFragments for verification — re-imported lazily
  // to avoid circular import.
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  import('./composeFragment').then((mod) => {
    (window as any).__cogCompose = mod.composeFragments;
  }).catch(() => {});
}

// ─── hooks ──────────────────────────────────────────────────────────

/** Get the pulse function.  Stable reference. */
export function useCognitionPulse(): (e: SemanticEnergy, n: number, hint?: string) => void {
  ensureTicker();
  return useCognitiveBus((s) => s.pulse);
}

/** Re-render-bound dominant state.  Subscribes to ticks. */
export function useDominantCognition(): { energy: SemanticEnergy; weight: number; score: number } | null {
  ensureTicker();
  // subscribe to both residue mutations and tick increments
  useCognitiveBus((s) => s.tickCounter);
  useCognitiveBus((s) => s.residue);
  return useCognitiveBus.getState().dominant();
}

/** Bulk residue read.  Useful for debug / inspector. */
export function useResidueSnapshot(): Array<{ energy: SemanticEnergy; weight: number }> {
  ensureTicker();
  useCognitiveBus((s) => s.tickCounter);
  useCognitiveBus((s) => s.residue);
  return useCognitiveBus.getState().snapshot();
}

/**
 * Fire one or more pulses when a dep changes.  Use sparingly — every
 * screen mount should only call this once with stable deps.
 */
export function useCognitionEffect(
  pulses: Array<[SemanticEnergy, number]>,
  deps: any[],
): void {
  const pulse = useCognitionPulse();
  useEffect(() => {
    for (const [e, n] of pulses) {
      if (n > 0) pulse(e, n);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}

/**
 * Screen helper — pulse the bus from a screen's local cognitive state.
 * Maps (category, state) → energy via the canonical taxonomy.  Safe to
 * call on every render: internally guards with a deps array.
 */
export function useCognitionFromState(
  category: CognitiveCategory,
  state: string | null | undefined,
  amount = 0.4,
): void {
  const pulse = useCognitionPulse();
  useEffect(() => {
    if (!state) return;
    const tok = tokenForState(category, state);
    pulse(tok.energy, amount);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [category, state, amount]);
}

/**
 * P6·α — Recent reflective events for cognitive fragments.
 * Returns the most recent meaningful events (filtered for narrative weight).
 */
export function useRecentCognitiveEvents(
  max = 3,
  maxAgeMs = 15 * 60 * 1000,
): CognitiveEvent[] {
  ensureTicker();
  useCognitiveBus((s) => s.tickCounter);
  useCognitiveBus((s) => s.events);
  return useCognitiveBus.getState().recentEvents(max, maxAgeMs);
}

/**
 * P6·α — Surfacing layer.  Reads the event log and condenses it into
 * fragments via `composeFragment` (cognitive condensation — most events
 * return null).
 *
 * Fragments are RARE by design:
 *   · global gap ≥ 60s between emissions
 *   · structural coalescence within 90s for same archetype + tone
 *   · scope filtering so portfolio sees consequence-shaped fragments
 *     and command sees presence-shaped ones
 *
 * Callers should treat an empty array as the NORMAL state — fragments
 * appear only when the residue graph has produced a meaningful event.
 */
export function useCognitiveFragments(
  opts: { scope?: FragmentScope; max?: number; maxAgeMs?: number } = {},
): CognitiveFragment[] {
  ensureTicker();
  useCognitiveBus((s) => s.tickCounter);
  useCognitiveBus((s) => s.events);
  const events = useCognitiveBus.getState().events;
  return composeFragments(events, {
    scope: opts.scope ?? 'any',
    max: opts.max ?? 2,
    maxAgeMs: opts.maxAgeMs ?? 12 * 60 * 1000,
  });
}

/**
 * Tiny render-component variant for screens that prefer JSX placement
 * over hook calls.  Renders nothing — fires a single pulse on mount.
 *
 *   <BusPulse energy="dormant" amount={0.3} />
 */
export function BusPulse(props: { energy: SemanticEnergy; amount?: number; hint?: string }): null {
  const pulse = useCognitionPulse();
  useEffect(() => {
    pulse(props.energy, props.amount ?? 0.3, props.hint);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return null;
}

/**
 * Render-component variant that reads a category+state and pulses
 * accordingly.  Re-pulses when state changes.
 *
 *   <BusPulseFromState category="cognition" state={readiness.state} amount={0.5} />
 */
export function BusPulseFromState(props: {
  category: CognitiveCategory;
  state: string | null | undefined;
  amount?: number;
}): null {
  useCognitionFromState(props.category, props.state, props.amount ?? 0.4);
  return null;
}
