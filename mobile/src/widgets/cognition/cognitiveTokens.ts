/**
 * COGNITIVE TOKENS  ·  Iteration 4·α
 *
 * The semantic operating system layer of Trading OS.
 *
 * NOT a color palette.  NOT a style guide.
 * A semantic energy taxonomy with precedence rules, density rules,
 * border energy, motion behaviour, and icon cadence — all expressed as
 * tokens, not hex.
 *
 *
 *   Rule 1.  No component may pick its own color.
 *            It composes a SemanticToken via `tokenFor(category, state)`.
 *
 *   Rule 2.  When several semantic energies stack on the same surface,
 *            the dominant one wins (suppression > readiness > … >
 *            dormant).  Use `selectDominant(states)` for this.
 *
 *   Rule 3.  Differentiation between states with the SAME hue
 *            (e.g. WAIT vs OBSERVING) happens through density / opacity
 *            / border energy / motion — never through new colors.
 *            Stability of language > richness of language.
 *
 *
 *   The 7 semantic energies are mapped onto only 4 hues from the theme
 *   (suppression / compression / expansion / dormant) — the user reads
 *   intent through the AGGREGATE of color + density + opacity + border,
 *   not the color alone.
 */

// ─── 7 SEMANTIC ENERGIES ────────────────────────────────────────────
// 5 core + 2 transitional.
export type SemanticEnergy =
  // ── 5 core ──
  | 'suppression'   // capital protected · denial · highest priority
  | 'readiness'     // gates clearing · deployment imminent
  | 'expansion'     // active flow · momentum opening
  | 'compression'   // energy storing · waiting · constrained
  | 'dormant'       // quiet · low engagement · ambient
  // ── 2 transitional ──
  | 'flux'          // mid-state · evolving · alignment forming
  | 'caution';      // mild risk · early warning;

/** Precedence rules — capital safety has the highest semantic priority. */
const PRIORITY: Record<SemanticEnergy, number> = {
  suppression: 100,
  readiness:    80,
  caution:      70,
  expansion:    60,
  compression:  50,
  flux:         30,
  dormant:      10,
};

/** Theme color key for the energy.  4 hues across 7 energies. */
const HUE_KEY: Record<SemanticEnergy, string> = {
  suppression: 'sell',     // red — denial energy
  readiness:   'accent',   // mint — invitation to act
  expansion:   'buy',      // mint family — flow
  compression: 'warning',  // amber — energy storing
  caution:     'warning',  // amber — early warning
  flux:        'warning',  // amber subdued — mid-state
  dormant:     'textMuted',// grey — quiet
};

/** Border firmness — encodes how committed the AI is to this state. */
type BorderEnergy = 'firm' | 'soft' | 'minimal';
const BORDER: Record<SemanticEnergy, BorderEnergy> = {
  suppression: 'firm',
  readiness:   'firm',
  caution:     'soft',
  expansion:   'soft',
  compression: 'soft',
  flux:        'minimal',
  dormant:     'minimal',
};

/** Base opacity — encodes how loudly this state should speak. */
const OPACITY: Record<SemanticEnergy, number> = {
  suppression: 1.0,
  readiness:   0.96,
  caution:     0.9,
  expansion:   0.85,
  compression: 0.8,
  flux:        0.65,
  dormant:     0.55,
};

/** Density — how compressed/airy the rendered surface is. */
type Density = 'compressed' | 'normal' | 'airy';
const DENSITY: Record<SemanticEnergy, Density> = {
  suppression: 'normal',
  readiness:   'airy',     // invites action — needs breathing room
  caution:     'normal',
  expansion:   'normal',
  compression: 'compressed',
  flux:        'compressed',
  dormant:     'airy',     // quiet but breathing
};

/** Motion behaviour on entry. */
type MotionToken = 'static' | 'slow-fade-emerge' | 'breathe';
const MOTION: Record<SemanticEnergy, MotionToken> = {
  suppression: 'slow-fade-emerge',
  readiness:   'slow-fade-emerge',
  caution:     'static',
  expansion:   'slow-fade-emerge',
  compression: 'static',
  flux:        'static',
  dormant:     'breathe',
};

/** Whether the state warrants an icon. */
type IconCadence = 'present' | 'subdued' | 'absent';
const ICON: Record<SemanticEnergy, IconCadence> = {
  suppression: 'present',
  readiness:   'present',
  caution:     'subdued',
  expansion:   'subdued',
  compression: 'absent',
  flux:        'absent',
  dormant:     'absent',
};

export type SemanticToken = {
  energy: SemanticEnergy;
  colorKey: string;
  border: BorderEnergy;
  opacity: number;
  density: Density;
  motion: MotionToken;
  icon: IconCadence;
  priority: number;
};

export function tokenFor(energy: SemanticEnergy): SemanticToken {
  return {
    energy,
    colorKey:  HUE_KEY[energy],
    border:    BORDER[energy],
    opacity:   OPACITY[energy],
    density:   DENSITY[energy],
    motion:    MOTION[energy],
    icon:      ICON[energy],
    priority:  PRIORITY[energy],
  };
}

// ─── 4 TAXONOMIES ───────────────────────────────────────────────────
// Each known state name maps to one semantic energy.  This is the
// canonical alignment between Trading OS labels and the OS-layer.

const COGNITION_MAP: Record<string, SemanticEnergy> = {
  OBSERVING:           'dormant',
  STRUCTURING:         'flux',
  BUILDING:            'flux',
  ALIGNING:            'flux',
  READY:               'readiness',
  BECOMING_ACTIONABLE: 'readiness',
  BECOMING:            'readiness',
  DEPLOYED:            'expansion',
  COLLAPSING:          'suppression',
  SUPPRESSED:          'suppression',
  COOLING:             'dormant',
  DORMANT:             'dormant',
  WAIT:                'compression',
  ALIGN:               'expansion',
  BLOCK:               'suppression',
  'N/A':               'dormant',
  NEUTRAL:             'dormant',
  // Iteration 4·γ — intelligence-layer cognition modes (linguistic dialect,
  // not structural reuse).  Each lives in 'dormant' energy because the
  // intelligence layer is observation, not commitment.
  NOTICING:            'dormant',
  DETECTING:           'dormant',
  INTROSPECTING:       'dormant',
};

const CAPITAL_MAP: Record<string, SemanticEnergy> = {
  RISK_OFF:     'suppression',
  'RISK OFF':   'suppression',
  DEFENSIVE:    'suppression',
  ROTATING:     'flux',
  ENGAGED:      'expansion',
  ACCUMULATION: 'compression',
  CONCENTRATED: 'caution',
  AGGRESSIVE:   'caution',
  DORMANT:      'dormant',
  OBSERVING:    'dormant',
  PROTECTIVE:   'suppression',
  DESTRUCTIVE:  'suppression',
};

const CONVICTION_MAP: Record<string, SemanticEnergy> = {
  STRENGTHENING: 'expansion',
  ACCELERATING:  'expansion',
  STABILIZING:   'dormant',
  STABLE:        'dormant',
  HOLDING:       'dormant',
  WEAKENING:     'compression',
  COLLAPSED:     'suppression',
  COLLAPSING:    'suppression',
  FLIPPED:       'suppression',
};

const REGIME_MAP: Record<string, SemanticEnergy> = {
  COMPRESSING:  'compression',
  COMPRESSED:   'compression',
  EXPANDING:    'expansion',
  EXPANSION:    'expansion',
  CHAOTIC:      'suppression',
  INSTABILITY:  'suppression',
  EXHAUSTION:   'caution',
  THIN:         'compression',
  QUIET:        'dormant',
  CONTINUATION: 'flux',
  DRIFT:        'dormant',
  NORMAL:       'dormant',
  ABSENT:       'dormant',
  STRONG:       'expansion',
  WEAK:         'compression',
  EUPHORIC:     'caution',
  FEARFUL:      'compression',
  BULLISH:      'expansion',
  BEARISH:      'compression',
  DEEP:         'expansion',
  UNKNOWN:      'dormant',
};

export type CognitiveCategory = 'cognition' | 'capital' | 'conviction' | 'regime';

const CATEGORY_MAP: Record<CognitiveCategory, Record<string, SemanticEnergy>> = {
  cognition:  COGNITION_MAP,
  capital:    CAPITAL_MAP,
  conviction: CONVICTION_MAP,
  regime:     REGIME_MAP,
};

/**
 * Resolve a category-bound state label to a SemanticToken.
 * Falls back to dormant for unknown labels — never crashes.
 */
export function tokenForState(
  category: CognitiveCategory,
  state: string | null | undefined,
): SemanticToken {
  const key = String(state || '').toUpperCase().replace(/-/g, '_');
  const energy = CATEGORY_MAP[category][key] ?? 'dormant';
  return tokenFor(energy);
}

// ─── PRECEDENCE — selectDominant ────────────────────────────────────
/**
 * When multiple semantic energies stack on the same surface, the
 * highest-priority one wins.  Returns the dominant token.  Useful for
 * stickies and section heroes where several states could compete.
 */
export function selectDominant(
  pairs: { category: CognitiveCategory; state: string | null | undefined }[],
): SemanticToken {
  if (pairs.length === 0) return tokenFor('dormant');
  const tokens = pairs.map((p) => tokenForState(p.category, p.state));
  tokens.sort((a, b) => b.priority - a.priority);
  return tokens[0];
}

// ─── DENSITY → padding numbers ─────────────────────────────────────
export function paddingFor(density: Density): { v: number; h: number } {
  if (density === 'compressed') return { v: 3, h: 7 };
  if (density === 'airy')       return { v: 6, h: 12 };
  return { v: 5, h: 10 };
}

export function borderWidthFor(border: BorderEnergy): number {
  if (border === 'firm')    return 1.4;
  if (border === 'soft')    return 1;
  return 0.5; // minimal — hairline
}
