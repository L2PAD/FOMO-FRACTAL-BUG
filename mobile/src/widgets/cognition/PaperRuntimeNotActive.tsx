/**
 * PaperRuntimeNotActive — Phase C surface placeholder.
 *
 * NOT a CTA.  NOT an "Execute" button.  NOT a teaser.
 *
 * A quiet observational panel that surfaces the paper runtime gate
 * state when it is closed (the current default).  When the gate opens
 * (mature outcomes + validated shadow + operator paper mode + healthy
 * market prices), the component renders nothing — UI silently steps
 * aside and lets the future paper surface take over.
 *
 * Rules:
 *   • If gate.open=true → render nothing (truthful absence)
 *   • If gate is closed → quiet panel with `requires` chips
 *   • If API fails → render nothing (no skeleton, no fake state)
 *   • No countdown timers.  No progress bars.  No animated dots.
 */
import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { paperApi } from '../../services/api/paper-api';
import { tokenFor } from './cognitiveTokens';

type Props = {
  colors: any;
  marginTop?: number;
  marginBottom?: number;
};

type GateState = {
  open: boolean;
  passing: string[];
  requires: string[];
};

// ─── Humanize gate requirement labels ─────────────────────────────────
const REQUIRES_LABEL: Record<string, string> = {
  mature_outcomes: 'mature outcomes',
  validated_shadow_runtime: 'validated shadow runtime',
  operator_mode_paper: 'operator mode · paper',
  market_prices_healthy: 'live market prices',
};

export const PaperRuntimeNotActive: React.FC<Props> = ({
  colors, marginTop = 8, marginBottom = 8,
}) => {
  const [gate, setGate] = useState<GateState | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const res = await paperApi.health();
        if (!alive) return;
        if (res?.ok && res.gate) {
          setGate({
            open: !!res.gate.open,
            passing: res.gate.passing || [],
            requires: res.gate.requires || [],
          });
        } else {
          setGate(null);
        }
      } catch {
        if (alive) setGate(null);
      } finally {
        if (alive) setLoaded(true);
      }
    })();
    return () => { alive = false; };
  }, []);

  if (!loaded) return null;
  if (!gate || gate.open) return null;  // truthful absence when active

  const token = tokenFor('suppression');
  const accent = colors[token.colorKey] ?? colors.textMuted;

  return (
    <View style={[styles.wrap, { marginTop, marginBottom }]}>
      <View style={styles.headRow}>
        <Text style={[styles.headTitle, { color: colors.text }]}>PAPER RUNTIME</Text>
        <Text style={[styles.headSub, { color: colors.textMuted }]}>not yet active</Text>
      </View>
      <View style={[
        styles.card,
        { backgroundColor: colors.surface, borderColor: colors.border, opacity: token.opacity },
      ]}>
        <View style={styles.headLine}>
          <View style={[styles.dot, { backgroundColor: accent, opacity: 0.55 }]} />
          <Text style={[styles.phrase, { color: colors.text }]}>
            Paper runtime is not active. Shadow memory is still forming.
          </Text>
        </View>

        {gate.requires.length > 0 && (
          <View style={styles.requiresRow}>
            <Text style={[styles.requiresLabel, { color: colors.textMuted }]}>requires</Text>
            <View style={styles.chips}>
              {gate.requires.map((r) => (
                <View key={r} style={[styles.chip, { borderColor: colors.border }]}>
                  <Text style={[styles.chipText, { color: colors.textMuted }]}>
                    {REQUIRES_LABEL[r] || r}
                  </Text>
                </View>
              ))}
            </View>
          </View>
        )}

        {gate.passing.length > 0 && (
          <Text style={[styles.passingHint, { color: colors.textMuted }]}>
            satisfied · {gate.passing.map((p) => REQUIRES_LABEL[p] || p).join(', ')}
          </Text>
        )}
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  wrap: {},
  headRow: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline',
    marginBottom: 8, paddingHorizontal: 2,
  },
  headTitle: { fontSize: 11, fontWeight: '800', letterSpacing: 1.6 },
  headSub: { fontSize: 10, fontStyle: 'italic' },
  card: { borderRadius: 12, borderWidth: 1, padding: 14 },
  headLine: { flexDirection: 'row', alignItems: 'center', marginBottom: 10 },
  dot: { width: 7, height: 7, borderRadius: 4, marginRight: 9 },
  phrase: { fontSize: 13, fontWeight: '600', flex: 1 },
  requiresRow: { marginBottom: 6 },
  requiresLabel: {
    fontSize: 9, letterSpacing: 1.3, textTransform: 'uppercase', marginBottom: 5,
  },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  chip: { borderRadius: 10, borderWidth: 0.7, paddingVertical: 3, paddingHorizontal: 9 },
  chipText: { fontSize: 11, letterSpacing: 0.3 },
  passingHint: {
    fontSize: 10, fontStyle: 'italic', marginTop: 4, opacity: 0.75,
  },
});
