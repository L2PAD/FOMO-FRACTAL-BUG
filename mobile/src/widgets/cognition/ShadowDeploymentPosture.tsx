/**
 * ShadowDeploymentPosture — Stage A-8 surfaces the Stage A-7 substrate.
 *
 * NOT a trade signal.  NOT a setup.  NOT a recommendation.
 *
 * This is the cognition restraint surface: "what could deployment have
 * looked like, why didn't AI commit?"  The hierarchy reads:
 *
 *     posture       (calm, low-saturation label — never CTA-like)
 *     reasons       (top-3 observational lines)
 *     blockedBy     (attribution chips — which layer vetoed)
 *     counterfactual structure   (only when shadow generated one)
 *
 * Visual language:
 *   • `blocked`     →  suppression token (existing palette — neutral blue-grey)
 *   • `wait`        →  dormant token (silent grey)
 *   • `considered`  →  compression token (subdued amber, NEVER gold/CTA)
 *   • `unresolved`  →  flux token (dusty amber, ambient)
 *
 * Rules:
 *   • If `loading` → render nothing (absence is honest).
 *   • If verdict is null → render nothing (truthful absence).
 *   • If `hypothetical` is null → counterfactual block is OMITTED entirely
 *     (no dashed placeholder, no "no structure available" message).
 *   • Never use "execute" / "buy" / "sell" / "signal" wording.
 */
import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { mbrainApi } from '../../services/api/mbrain-api';
import { tokenFor, SemanticEnergy } from './cognitiveTokens';

type Props = {
  symbol: string;                 // BTC / ETH / SOL
  colors: any;
  marginTop?: number;
  marginBottom?: number;
};

type ShadowVerdict = {
  symbol: string;
  status: 'blocked' | 'wait' | 'considered' | 'unresolved';
  rawAction: string;
  finalAction: string | null;
  shadowAction: string;
  reason: string[];
  deploymentBlockedBy: string[];
  hypothetical: null | {
    entry: number;
    stop: number;
    target: number;
    riskReward: number;
    sizeModel: string;
    source: string;
  };
  createdAt: string;
};

// ─── Status → semantic energy ──────────────────────────────────────────
function energyForStatus(status: string): SemanticEnergy {
  if (status === 'blocked') return 'suppression';
  if (status === 'considered') return 'compression';   // subdued amber
  if (status === 'unresolved') return 'flux';
  return 'dormant';                                     // wait
}

// ─── Posture verbal copy — observational, NEVER agency-language ────────
function postureCopy(status: string, finalAction: string | null): string {
  if (status === 'blocked') return 'restraint held';
  if (status === 'considered') return 'structural consideration';
  if (status === 'unresolved') return 'directional disagreement';
  if (finalAction === 'WAIT') return 'conditions remain neutral';
  return 'conditions remain neutral';
}

// ─── BlockedBy chips — humanize the attribution labels ─────────────────
const BLOCKED_BY_LABEL: Record<string, string> = {
  metaDecision: 'meta',
  fractal: 'fractal',
  technical_alignment: 'technical',
  sentiment_confidence: 'sentiment',
  price_unavailable: 'price',
};

// ─── Number formatter — small, restrained, paper-feel ──────────────────
function fmt(n: number | null | undefined, decimals = 2): string {
  if (n == null || isNaN(Number(n))) return '—';
  const v = Number(n);
  if (v >= 1000) return v.toLocaleString(undefined, { maximumFractionDigits: 0 });
  if (v >= 1) return v.toFixed(decimals);
  return v.toFixed(4);
}

export const ShadowDeploymentPosture: React.FC<Props> = ({
  symbol, colors, marginTop = 8, marginBottom = 8,
}) => {
  const [verdict, setVerdict] = useState<ShadowVerdict | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const res = await mbrainApi.shadowRecent(1, symbol.toUpperCase());
        if (!alive) return;
        const v = res?.ok && Array.isArray(res.items) && res.items.length > 0
          ? (res.items[0] as ShadowVerdict)
          : null;
        setVerdict(v);
      } catch {
        if (alive) setVerdict(null);
      } finally {
        if (alive) setLoaded(true);
      }
    })();
    return () => { alive = false; };
  }, [symbol]);

  // Truthful absence — render nothing until we know, render nothing if null
  if (!loaded || !verdict) return null;

  const token = tokenFor(energyForStatus(verdict.status));
  const accent = colors[token.colorKey] ?? colors.textMuted;
  const posture = postureCopy(verdict.status, verdict.finalAction);
  const reasons = (verdict.reason || []).slice(0, 3);
  const blocked = (verdict.deploymentBlockedBy || [])
    .map((b) => BLOCKED_BY_LABEL[b] || b)
    .slice(0, 4);
  const hyp = verdict.hypothetical;

  return (
    <View style={[
      styles.card,
      {
        backgroundColor: colors.surface,
        borderColor: colors.border,
        marginTop,
        marginBottom,
        opacity: token.opacity,
      },
    ]}>
      {/* Head: symbol + posture phrase + hairline accent */}
      <View style={styles.head}>
        <View style={styles.headLeft}>
          <View style={[styles.dot, { backgroundColor: accent, opacity: 0.65 }]} />
          <Text style={[styles.symbol, { color: colors.text }]}>{verdict.symbol}</Text>
          <View style={[styles.divider, { backgroundColor: colors.border }]} />
          <Text style={[styles.posture, { color: colors.textMuted }]}>{posture}</Text>
        </View>
        <Text style={[styles.shadowTag, { color: colors.textMuted }]}>SHADOW</Text>
      </View>

      {/* Flow line: raw → final → shadow (textual, NOT pipeline) */}
      <Text style={[styles.flow, { color: colors.textMuted }]}>
        raw <Text style={{ color: colors.text }}>{verdict.rawAction.toLowerCase().replace('_', ' ')}</Text>
        {'   ·   '}
        canonical <Text style={{ color: colors.text }}>{(verdict.finalAction || 'unknown').toLowerCase()}</Text>
        {'   ·   '}
        shadow <Text style={{ color: accent }}>{verdict.shadowAction.toLowerCase().replace('_', ' ')}</Text>
      </Text>

      {/* Reason lines */}
      {reasons.length > 0 && (
        <View style={styles.reasons}>
          {reasons.map((r, i) => (
            <Text key={i} style={[styles.reasonText, { color: colors.textMuted }]}>
              · {r}
            </Text>
          ))}
        </View>
      )}

      {/* deploymentBlockedBy attribution chips */}
      {blocked.length > 0 && (
        <View style={styles.chipsRow}>
          {blocked.map((b, i) => (
            <View
              key={i}
              style={[
                styles.chip,
                { borderColor: colors.border, opacity: 0.7 },
              ]}
            >
              <Text style={[styles.chipText, { color: colors.textMuted }]}>{b}</Text>
            </View>
          ))}
        </View>
      )}

      {/* Counterfactual structure — only when hypothetical exists.
          Truthful absence rule: if null, render nothing here. */}
      {hyp && (
        <View style={[styles.counterCard, { borderColor: colors.border }]}>
          <Text style={[styles.counterTag, { color: colors.textMuted }]}>
            counterfactual structure · not a recommendation
          </Text>
          <View style={styles.counterRow}>
            <CounterField label="entry"  value={`$${fmt(hyp.entry)}`}  colors={colors} />
            <CounterField label="stop"   value={`$${fmt(hyp.stop)}`}   colors={colors} />
            <CounterField label="target" value={`$${fmt(hyp.target)}`} colors={colors} />
            <CounterField label="rr"     value={`${fmt(hyp.riskReward, 2)}×`} colors={colors} />
          </View>
          <Text style={[styles.counterFootnote, { color: colors.textMuted }]}>
            size · disabled (shadow has no sizing authority)
          </Text>
        </View>
      )}
    </View>
  );
};

// ─── CounterField helper ──────────────────────────────────────────────
const CounterField: React.FC<{ label: string; value: string; colors: any }> = ({
  label, value, colors,
}) => (
  <View style={styles.counterField}>
    <Text style={[styles.counterLabel, { color: colors.textMuted }]}>{label}</Text>
    <Text style={[styles.counterValue, { color: colors.text }]}>{value}</Text>
  </View>
);

const styles = StyleSheet.create({
  card: {
    borderRadius: 12,
    borderWidth: 1,
    paddingVertical: 14,
    paddingHorizontal: 14,
  },
  head: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 10,
  },
  headLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    flexShrink: 1,
  },
  dot: {
    width: 7, height: 7, borderRadius: 4, marginRight: 8,
  },
  symbol: {
    fontSize: 14, fontWeight: '800', letterSpacing: 0.4,
  },
  divider: {
    width: 1, height: 11, marginHorizontal: 9, opacity: 0.6,
  },
  posture: {
    fontSize: 12, fontStyle: 'italic',
  },
  shadowTag: {
    fontSize: 9, fontWeight: '700', letterSpacing: 1.3,
  },
  flow: {
    fontSize: 11, marginBottom: 10, letterSpacing: 0.2,
  },
  reasons: {
    marginBottom: 10,
  },
  reasonText: {
    fontSize: 12, lineHeight: 17, marginBottom: 1,
  },
  chipsRow: {
    flexDirection: 'row', flexWrap: 'wrap', gap: 6,
  },
  chip: {
    borderRadius: 10, borderWidth: 0.7, paddingVertical: 3, paddingHorizontal: 8,
  },
  chipText: {
    fontSize: 10, fontWeight: '600', letterSpacing: 0.8,
  },
  counterCard: {
    marginTop: 12, paddingTop: 10, borderTopWidth: 0.5,
  },
  counterTag: {
    fontSize: 10, letterSpacing: 0.9, marginBottom: 8, fontStyle: 'italic',
  },
  counterRow: {
    flexDirection: 'row', justifyContent: 'space-between',
  },
  counterField: {
    alignItems: 'flex-start', flex: 1,
  },
  counterLabel: {
    fontSize: 10, letterSpacing: 1, marginBottom: 3,
  },
  counterValue: {
    fontSize: 13, fontWeight: '700',
  },
  counterFootnote: {
    fontSize: 10, marginTop: 8, fontStyle: 'italic', opacity: 0.7,
  },
});
