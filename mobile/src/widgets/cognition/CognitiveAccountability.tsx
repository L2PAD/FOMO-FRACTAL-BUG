/**
 * CognitiveAccountability — Stage A-8 surfaces the Stage A-6 substrate.
 *
 * NOT an analytics dashboard.  NOT pie charts.  NOT win-rate.
 * NOT PnL.  NOT "AI is profitable".
 *
 * This is the memory-continuity layer: pending vs resolved counts,
 * coverage of decisions captured into outcome memory, and the textual
 * distribution of classifications when they begin to resolve.
 *
 *   Classification semantics (per Stage A-6):
 *     avoided_loss       suppression preserved capital
 *     missed_gain        suppression skipped an asymmetric move
 *     neutral_wait       remembered non-event (capital preserved at low cost)
 *     realized_gain      executed verdict resolved favorably
 *     realized_loss      executed verdict resolved adversely
 *     neutral_realized   executed verdict resolved within ±1.5% (noise)
 *
 * Rules:
 *   • If health.ok=false → render with degraded note (`memory insufficient`).
 *   • If totalDecisions=0 → render nothing (truthful absence).
 *   • Never use PnL/winrate visual language.
 *   • Coverage shown as a hairline progress bar, not a 0–100 chart.
 */
import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { mbrainApi } from '../../services/api/mbrain-api';
import { tokenFor } from './cognitiveTokens';

type Props = {
  colors: any;
  marginTop?: number;
  marginBottom?: number;
};

type Health = {
  ok: boolean;
  pending?: number;
  resolved?: number;
  expired?: number;
  totalOutcomes?: number;
  totalDecisions?: number;
  coveragePct?: number;
  maturePending?: number;
  classifications?: Record<string, number>;
  reason?: string;
};

// ─── Classification label + tone (no agency colors) ────────────────────
const CLASSIFICATION_ORDER = [
  'avoided_loss',
  'missed_gain',
  'neutral_wait',
  'realized_gain',
  'realized_loss',
  'neutral_realized',
];

const CLASSIFICATION_LABEL: Record<string, string> = {
  avoided_loss: 'avoided loss',
  missed_gain: 'missed gain',
  neutral_wait: 'neutral wait',
  realized_gain: 'realized gain',
  realized_loss: 'realized loss',
  neutral_realized: 'neutral realized',
};

const CLASSIFICATION_ENERGY: Record<string, 'suppression' | 'compression' | 'dormant'> = {
  avoided_loss: 'suppression',
  missed_gain: 'compression',
  neutral_wait: 'dormant',
  realized_gain: 'dormant',
  realized_loss: 'suppression',
  neutral_realized: 'dormant',
};

export const CognitiveAccountability: React.FC<Props> = ({
  colors, marginTop = 8, marginBottom = 8,
}) => {
  const [health, setHealth] = useState<Health | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const res = await mbrainApi.outcomesHealth();
        if (!alive) return;
        setHealth(res as Health);
      } catch {
        if (alive) setHealth(null);
      } finally {
        if (alive) setLoaded(true);
      }
    })();
    return () => { alive = false; };
  }, []);

  if (!loaded) return null;
  if (!health) return null;

  // Truthful degradation — substrate not yet alive
  const insufficient = health.ok === false || (health.totalDecisions ?? 0) === 0;
  if (insufficient && !health.totalDecisions) return null;

  const pending = health.pending ?? 0;
  const resolved = health.resolved ?? 0;
  const expired = health.expired ?? 0;
  const totalOutcomes = health.totalOutcomes ?? (pending + resolved + expired);
  const totalDecisions = health.totalDecisions ?? 0;
  const coverage = Math.max(0, Math.min(1, health.coveragePct ?? 0));
  const maturePending = health.maturePending ?? 0;
  const classifications = health.classifications ?? {};

  return (
    <View style={[styles.wrap, { marginTop, marginBottom }]}>
      <View style={styles.headRow}>
        <Text style={[styles.headTitle, { color: colors.text }]}>
          COGNITIVE ACCOUNTABILITY
        </Text>
        <Text style={[styles.headSub, { color: colors.textMuted }]}>
          memory continuity · not analytics
        </Text>
      </View>

      <View style={[styles.card, { backgroundColor: colors.surface, borderColor: colors.border }]}>
        {/* Counters row — restrained, paper-feel */}
        <View style={styles.counterRow}>
          <Counter label="pending"  value={pending}  colors={colors} />
          <CountDivider colors={colors} />
          <Counter label="resolved" value={resolved} colors={colors} />
          <CountDivider colors={colors} />
          <Counter label="expired"  value={expired}  colors={colors} />
          <CountDivider colors={colors} />
          <Counter label="mature pending" value={maturePending} colors={colors} dim />
        </View>

        {/* Coverage hairline — never a chart, never a percentage gauge */}
        <View style={styles.coverageRow}>
          <Text style={[styles.coverageLabel, { color: colors.textMuted }]}>
            coverage · {totalOutcomes}/{totalDecisions} decisions captured
          </Text>
          <View style={[styles.coverageTrack, { backgroundColor: colors.border }]}>
            <View style={[
              styles.coverageFill,
              { width: `${Math.round(coverage * 100)}%`, backgroundColor: colors.textMuted, opacity: 0.55 },
            ]} />
          </View>
        </View>

        {/* Classification distribution — textual, not chart */}
        {resolved > 0 ? (
          <View style={styles.distList}>
            {CLASSIFICATION_ORDER
              .filter((k) => (classifications[k] ?? 0) > 0)
              .map((k) => {
                const count = classifications[k] ?? 0;
                const energy = CLASSIFICATION_ENERGY[k] ?? 'dormant';
                const tok = tokenFor(energy);
                const accent = colors[tok.colorKey] ?? colors.textMuted;
                return (
                  <View key={k} style={styles.distRow}>
                    <View style={[styles.distDot, { backgroundColor: accent, opacity: 0.55 }]} />
                    <Text style={[styles.distLabel, { color: colors.textMuted }]}>
                      {CLASSIFICATION_LABEL[k] || k}
                    </Text>
                    <Text style={[styles.distCount, { color: colors.text, opacity: tok.opacity }]}>
                      {count}
                    </Text>
                  </View>
                );
              })}
          </View>
        ) : (
          <Text style={[styles.empty, { color: colors.textMuted }]}>
            memory accumulating · no resolved verdicts yet
          </Text>
        )}
      </View>
    </View>
  );
};

// ─── Sub-components ────────────────────────────────────────────────────
const Counter: React.FC<{ label: string; value: number; colors: any; dim?: boolean }> = ({
  label, value, colors, dim,
}) => (
  <View style={styles.counterCell}>
    <Text style={[
      styles.counterValue,
      { color: colors.text, opacity: dim ? 0.55 : 1 },
    ]}>
      {value}
    </Text>
    <Text style={[styles.counterLabel, { color: colors.textMuted }]}>{label}</Text>
  </View>
);

const CountDivider: React.FC<{ colors: any }> = ({ colors }) => (
  <View style={[styles.counterDivider, { backgroundColor: colors.border }]} />
);

const styles = StyleSheet.create({
  wrap: {},
  headRow: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline',
    marginBottom: 8, paddingHorizontal: 2,
  },
  headTitle: {
    fontSize: 11, fontWeight: '800', letterSpacing: 1.6,
  },
  headSub: {
    fontSize: 10, fontStyle: 'italic',
  },
  card: {
    borderRadius: 12, borderWidth: 1, padding: 14,
  },
  counterRow: {
    flexDirection: 'row', alignItems: 'center', marginBottom: 14,
  },
  counterCell: {
    flex: 1, alignItems: 'flex-start',
  },
  counterDivider: {
    width: 1, height: 28, marginHorizontal: 6, opacity: 0.6,
  },
  counterValue: {
    fontSize: 18, fontWeight: '800', letterSpacing: -0.3, marginBottom: 1,
  },
  counterLabel: {
    fontSize: 9, letterSpacing: 1, textTransform: 'lowercase',
  },
  coverageRow: {
    marginBottom: 12,
  },
  coverageLabel: {
    fontSize: 11, marginBottom: 5,
  },
  coverageTrack: {
    height: 2, borderRadius: 1, overflow: 'hidden', opacity: 0.6,
  },
  coverageFill: {
    height: 2,
  },
  distList: {
    marginTop: 4,
  },
  distRow: {
    flexDirection: 'row', alignItems: 'center', paddingVertical: 4,
  },
  distDot: {
    width: 5, height: 5, borderRadius: 3, marginRight: 8,
  },
  distLabel: {
    flex: 1, fontSize: 12,
  },
  distCount: {
    fontSize: 13, fontWeight: '700', letterSpacing: 0.3,
  },
  empty: {
    fontSize: 11, fontStyle: 'italic', marginTop: 4,
  },
});
