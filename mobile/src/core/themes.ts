// ============================================================
// FOMO Design System — Production tokens
// Principle: roles, not colors. Semantic, not decorative.
// Dark and Light are two systems, not an inversion.
// ============================================================

export interface AppThemeColors {
  // Surfaces (Level 0 → 2)
  background: string;          // Level 0 — app background
  bgSecondary: string;         // Level 2 — highlighted blocks (tinted surface)
  surface: string;             // Level 1 — cards
  surfaceHover: string;        // Level 1 pressed / hover

  // Text (3 tiers)
  textPrimary: string;
  textSecondary: string;
  textMuted: string;
  textTertiary: string;        // alias of textMuted for new semantic naming
  text: string;                // alias of textPrimary — legacy field used widely
                               // across Portfolio/Trade/Intelligence/Observatory
                               // screens. Both themes resolve it to textPrimary
                               // so the same code path reads correctly under
                               // both dark and light without per-screen edits.

  // Borders
  border: string;
  borderActive: string;

  // Accent (brand CTA) — different between themes on purpose
  accent: string;              // fintech-blue in light, purple in dark
  accentHover: string;
  accentText: string;          // text color readable on accent bg (always white)
  accentTint: string;          // soft tinted block background
  accentTintBorder: string;

  // Semantic states
  buy: string;
  sell: string;
  wait: string;
  bullish: string;
  bearish: string;
  neutral: string;
  info: string;                // informational blue (same family as accent in light)
  high: string;
  medium: string;
  low: string;
  success: string;
  danger: string;
  warning: string;

  // Badges — soft pill backgrounds (high-medium-low risk / impact)
  badgeHighBg: string;
  badgeHighText: string;
  badgeMedBg: string;
  badgeMedText: string;
  badgeLowBg: string;
  badgeLowText: string;

  // Polychromatic accents — extended palette borrowed from MiniApp Lite.
  // Use these for contextual surfaces (PRO/gold, info/cyan, primary CTA/indigo,
  // insights/purple). Optional: screens may rely on `accent` only.
  indigo?: string;
  cyan?: string;
  gold?: string;
  purple?: string;
}

export interface AppThemeShadows {
  none: object;                // cleared shadow
  card: object;                // soft lift on Level-1 cards
  cardHover: object;           // deeper on hover/press
  modal: object;               // modals / overlays
}

export interface AppTheme {
  mode: 'dark' | 'light';
  colors: AppThemeColors;
  shadows: AppThemeShadows;
  spacing: { xs: number; sm: number; md: number; lg: number; xl: number };
  radius: { sm: number; md: number; lg: number; full: number };
  fontSize: {
    xs: number; sm: number; base: number; lg: number; xl: number;
    '2xl': number; '3xl': number; '4xl': number; '5xl': number; decision: number;
  };
  fontWeight: {
    regular: '400'; medium: '500'; semibold: '600'; bold: '700'; heavy: '900';
  };
}

const shared = {
  spacing: { xs: 4, sm: 8, md: 16, lg: 24, xl: 32 },
  radius: { sm: 8, md: 12, lg: 16, full: 9999 },
  fontSize: {
    xs: 10, sm: 12, base: 14, lg: 16, xl: 18,
    '2xl': 22, '3xl': 28, '4xl': 36, '5xl': 48, decision: 64,
  },
  fontWeight: {
    regular: '400' as const, medium: '500' as const, semibold: '600' as const,
    bold: '700' as const, heavy: '900' as const,
  },
};

// ============================================================
// DARK — EVA-X inspired palette (mint-brand, cool near-black)
// Canonical tokens: T.bg / T.surface1-3 / T.primary(mint)
// ============================================================
export const darkTheme: AppTheme = {
  mode: 'dark',
  colors: {
    // Surfaces — cool near-black with subtle blue undertone
    background: '#0B0F14',       // T.bg
    surface: '#0F141B',          // T.surface1 (cards)
    bgSecondary: '#121A23',      // T.surface2 (modals / tinted)
    surfaceHover: '#16202B',     // T.surface3 (inputs / pressed)

    // Text — off-white with cool undertone
    textPrimary: '#E6EDF3',      // T.text
    textSecondary: '#9FB0C0',    // T.textSecondary
    textMuted: '#6B7C8F',        // T.textMuted
    textTertiary: '#6B7C8F',     // alias of textMuted (semantic name)
    text: '#E6EDF3',             // legacy alias of textPrimary — dark mode value
    textTertiary: '#6B7C8F',

    // Borders — subtle white overlays
    border: 'rgba(255,255,255,0.06)',
    borderActive: 'rgba(255,255,255,0.10)',

    // Accent — MINT canonical brand (was purple)
    accent: '#2FE6A6',           // T.primary (mint)
    accentHover: '#3FF0B4',
    accentText: '#0B0F14',       // dark on mint (WCAG AA)
    accentTint: 'rgba(47,230,166,0.10)',
    accentTintBorder: 'rgba(47,230,166,0.28)',

    // Semantic — EVA-X mapping
    buy: '#2FE6A6',              // mint (bullish = success = brand)
    sell: '#FF6B6B',             // coral (danger)
    wait: '#F5C451',             // golden (risk)
    bullish: '#2FE6A6',
    bearish: '#FF6B6B',
    neutral: '#F5C451',
    info: '#4DA3FF',             // sky (T.info)
    high: '#FF6B6B',
    medium: '#F5C451',
    low: '#2FE6A6',
    success: '#2FE6A6',
    danger: '#FF6B6B',
    warning: '#F5C451',

    // Badges — tinted soft pills (alpha on dark)
    badgeHighBg: 'rgba(255,107,107,0.14)',
    badgeHighText: '#FF6B6B',
    badgeMedBg: 'rgba(245,196,81,0.14)',
    badgeMedText: '#F5C451',
    badgeLowBg: 'rgba(159,176,192,0.12)',
    badgeLowText: '#9FB0C0',

    // Polychromatic accents — remapped to EVA-X semantics
    indigo: '#4DA3FF',           // info-blue (CTAs that need "action" feel)
    cyan: '#4DA3FF',             // info (same family)
    gold: '#F5C451',             // PRO / premium highlights
    purple: '#2FE6A6',           // brand alias (mint)
  },
  shadows: {
    none: {},
    card: {},
    cardHover: {},
    modal: {
      shadowColor: '#000', shadowOffset: { width: 0, height: 8 },
      shadowOpacity: 0.45, shadowRadius: 24, elevation: 12,
    },
  },
  ...shared,
};

// ============================================================
// LIGHT — structure theme (fintech, trustworthy)
// ============================================================
export const lightTheme: AppTheme = {
  mode: 'light',
  colors: {
    // Surfaces — 3 distinct levels, cards SHOULD lift
    background: '#F7F8FA',
    bgSecondary: '#EEF2FF',      // subtle tinted highlight (light-blue haze)
    surface: '#FFFFFF',
    surfaceHover: '#F9FAFB',

    // Text
    textPrimary: '#0B0F14',
    textSecondary: '#5B6676',
    textMuted: '#9AA3AF',
    textTertiary: '#9AA3AF',
    text: '#0B0F14',             // legacy alias of textPrimary — light mode value

    // Borders
    border: '#E6EAF0',
    borderActive: '#CBD5E1',

    // Accent — fintech BLUE, not purple (trust, money)
    accent: '#2563EB',
    accentHover: '#1D4ED8',
    accentText: '#FFFFFF',
    accentTint: '#EEF2FF',       // solid readable soft-blue, not alpha
    accentTintBorder: '#C7D2FE',

    // Semantic — flat finance-grade
    buy: '#16A34A',
    sell: '#DC2626',
    wait: '#F59E0B',
    bullish: '#16A34A',
    bearish: '#DC2626',
    neutral: '#F59E0B',
    info: '#2563EB',
    high: '#DC2626',
    medium: '#F59E0B',
    low: '#16A34A',
    success: '#16A34A',
    danger: '#DC2626',
    warning: '#F59E0B',

    // Badges — solid soft pills (WCAG AA on light bg)
    badgeHighBg: '#FEE2E2',
    badgeHighText: '#DC2626',
    badgeMedBg: '#FEF3C7',
    badgeMedText: '#B45309',
    badgeLowBg: '#F3F4F6',
    badgeLowText: '#6B7280',
  },
  shadows: {
    none: {},
    card: {
      shadowColor: '#0B0F14', shadowOffset: { width: 0, height: 2 },
      shadowOpacity: 0.05, shadowRadius: 8, elevation: 2,
    },
    cardHover: {
      shadowColor: '#0B0F14', shadowOffset: { width: 0, height: 6 },
      shadowOpacity: 0.08, shadowRadius: 16, elevation: 5,
    },
    modal: {
      shadowColor: '#0B0F14', shadowOffset: { width: 0, height: 12 },
      shadowOpacity: 0.15, shadowRadius: 28, elevation: 14,
    },
  },
  ...shared,
};

export function getTheme(resolved: 'dark' | 'light'): AppTheme {
  return resolved === 'light' ? lightTheme : darkTheme;
}
