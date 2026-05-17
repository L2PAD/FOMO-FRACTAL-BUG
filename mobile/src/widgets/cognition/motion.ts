/**
 * COGNITIVE MOTION VOCABULARY  ·  Iteration 4·δ
 *
 *   Named motion semantics — not animation configs.
 *
 *   Rule of thumb:
 *     · A motion's NAME is part of cognition language.
 *     · A duration / easing pair is only an implementation detail.
 *     · Callers must NEVER reach for raw `FadeIn.duration(900)` — they
 *       must call the named verb so the meaning travels with the motion.
 *
 *
 *   Vocabulary
 *   ──────────
 *
 *   Entering (Layout / Reanimated entering builders):
 *
 *     softEntry           a single element appearing once, soft & quick
 *     slowEmergence       cognition appearing for the first time, deliberate
 *     subtleExpansion     a small label softly breathing into existence
 *     softCompression     a thought tightening / conviction weakening
 *     hesitationReveal    a reasoning chain unfolding after a pause
 *     suppressionHold     suppression entering with deliberate weight
 *     ambientDrift        background sensing / temperature shift
 *     readinessSurfacing  invitation to act surfacing into view
 *     sequencedReveal     items in a list unfolding one after another
 *
 *   Exiting:
 *
 *     fadeCollapse        suppression / withdrawal exiting (quick)
 *     thoughtRetreat      a thought retreating, slower & dignified
 *
 *   withTiming presets (for sharedValue motion — not Layout):
 *
 *     lateralDrift        cursor gliding across a continuum (DriftBand)
 *     intentionStep       intention marker progressing across a track
 *     pulseFadeIn         ambient observation fading in
 *     pulseFadeOut        ambient observation fading out
 *
 *
 *   Call-site shape:
 *
 *     <Animated.View entering={slowEmergence()} />
 *     <Animated.View entering={sequencedReveal(i, 250)} />
 *     sharedValue.value = withTiming(target, lateralDrift);
 *
 *   Adjusting duration / curve in one place changes the meaning of the
 *   verb everywhere — that's the point.
 */
import { FadeIn, FadeOut, Easing } from 'react-native-reanimated';

// ─── Easing palette (reused across both Layout and withTiming) ─────────
export const EASING = {
  /** ambient lateral drift — calm, even, no urgency */
  drift:    Easing.inOut(Easing.cubic),
  /** something surfacing into perception — exp out (most common) */
  surface:  Easing.out(Easing.exp),
  /** something receding into latency — exp in */
  recede:   Easing.in(Easing.exp),
  /** suppression / weight entering — cubic in */
  compress: Easing.in(Easing.cubic),
  /** intention progressing across a track — cubic out */
  intent:   Easing.out(Easing.cubic),
  /** soft expansion of a small label — cubic out (gentler than exp) */
  expand:   Easing.out(Easing.cubic),
  /** readiness invitation — quad out */
  invite:   Easing.out(Easing.quad),
};

// ─── Timing palette (durations are named, not magic numbers) ───────────
export const TIMING = {
  /** soft, single-element entry — the most common cognition appearance */
  softEntry:     900,
  /** deliberate first-appearance of a primary cognition block */
  slowEmergence: 1100,
  /** small label softly breathing into existence */
  subtleExpansion: 1300,
  /** thought tightening / compression entry */
  softCompression: 700,
  /** reasoning chain unfolding after a pause */
  hesitation:    900,
  /** suppression entering with weight */
  suppression:   1500,
  /** ambient drift / temperature shift */
  ambient:       2000,
  /** readiness invitation surfacing */
  readiness:     950,
  /** sequenced item entry inside a list */
  sequenced:     700,

  /** DriftBand cursor — lateral glide between regimes */
  driftCursor:   2400,
  /** IntentionTrack marker — progression across phases */
  intentionStep: 2000,

  /** CognitivePulse — observation hold before cross-fade */
  pulseHold:     6000,
  /** CognitivePulse — observation cross-fade duration */
  pulseFade:     1600,

  /** Quick exit fade — suppression collapsing */
  collapseExit:  250,
  /** Slower exit fade — thought receding with dignity */
  retreatExit:   550,
};

// ─── ENTERING — Layout builders ────────────────────────────────────────

/** a single element appearing once — soft, quick, the default cognition entry */
export const softEntry = (delay = 0) =>
  FadeIn.duration(TIMING.softEntry).delay(delay).easing(EASING.surface);

/** cognition appearing for the first time — soft, deliberate, exp ease */
export const slowEmergence = (delay = 0) =>
  FadeIn.duration(TIMING.slowEmergence).delay(delay).easing(EASING.surface);

/** a small label softly breathing into existence — slower, cubic out */
export const subtleExpansion = (delay = 0) =>
  FadeIn.duration(TIMING.subtleExpansion).delay(delay).easing(EASING.expand);

/** a thought tightening (conviction weakening, alignment narrowing) */
export const softCompression = (delay = 0) =>
  FadeIn.duration(TIMING.softCompression).delay(150 + delay).easing(EASING.expand);

/** reasoning chain unfolding after a perceptible pause */
export const hesitationReveal = (delay = 0) =>
  FadeIn.duration(TIMING.hesitation).delay(800 + delay).easing(EASING.surface);

/** suppression entering with deliberate weight — slower, in-curve */
export const suppressionHold = (delay = 0) =>
  FadeIn.duration(TIMING.suppression).delay(delay).easing(EASING.compress);

/** ambient sensing — temperature shift, no urgency */
export const ambientDrift = (delay = 0) =>
  FadeIn.duration(TIMING.ambient).delay(delay).easing(EASING.drift);

/** readiness surfacing — invitation to act, soft acceleration */
export const readinessSurfacing = (delay = 0) =>
  FadeIn.duration(TIMING.readiness).delay(delay).easing(EASING.invite);

/**
 * items in a list unfolding one after another — same-shape soft entries
 * with a deterministic stagger (default 450ms between items).
 */
export const sequencedReveal = (index: number, baseDelay = 0, stepMs = 450) =>
  FadeIn
    .duration(TIMING.sequenced)
    .delay(baseDelay + index * stepMs)
    .easing(EASING.surface);

// ─── EXITING ───────────────────────────────────────────────────────────

/** suppression / withdrawal exiting — quick fade */
export const fadeCollapse = () => FadeOut.duration(TIMING.collapseExit);

/** thought retreating — slower, dignified */
export const thoughtRetreat = () =>
  FadeOut.duration(TIMING.retreatExit).easing(EASING.compress);

// ─── withTiming PRESETS (for sharedValue.value = withTiming(target, X)) ─

/** cursor gliding across a continuum — DriftBand */
export const lateralDrift = {
  duration: TIMING.driftCursor,
  easing:   EASING.drift,
} as const;

/** intention marker progressing across a track — IntentionTrack */
export const intentionStep = {
  duration: TIMING.intentionStep,
  easing:   EASING.intent,
} as const;

/** ambient observation fading in — CognitivePulse */
export const pulseFadeIn = {
  duration: TIMING.pulseFade,
  easing:   EASING.surface,
} as const;

/** ambient observation fading out — CognitivePulse */
export const pulseFadeOut = {
  duration: TIMING.pulseFade,
  easing:   EASING.recede,
} as const;
