/**
 * OperatorObservatoryScreen — Phase B · Step 2.
 *
 * Reflective interpretive surface for operators.
 *
 * NOT an admin dashboard.  NOT Grafana.  NOT telemetry wall.  NOT KPI center.
 *
 * Strictly manual refresh.  Pull-to-refresh + explicit "Refresh
 * Interpretation" button.  NO websocket.  NO polling.  NO animated
 * counters.  NO flashing deltas.  NO charts / heatmaps / gauges.
 *
 * Sections (textual topology only):
 *   1. DEPLOYMENT CLIMATE
 *   2. ALIGNMENT DRIFT
 *   3. COGNITIVE MEMORY
 *   4. SHADOW STRUCTURES
 *   5. REGIME CONTINUITY
 *
 * Truthful absence: if substrate is empty, render an honest
 *   "Insufficient continuity for interpretive surface" panel —
 * no skeletons, no fake placeholders, no synthetic commentary.
 *
 * Operator-gated through frontend capability check; if not operator,
 * mounts the restricted environment view (we do NOT silently degrade
 * to a public-safe variant — observatory is intentionally operator-only).
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  RefreshControl, ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useColors } from '../../core/useColors';
import { useCapabilities } from '../../stores/capabilities.store';
import { mbrainApi } from '../../services/api/mbrain-api';
import { tokenFor } from '../../widgets/cognition/cognitiveTokens';
import { RestrictedEnvironmentScreen } from '../trading/_restricted/RestrictedEnvironmentScreen';

import { t } from '../../core/i18n';
type ObservatoryState = {
  ok: boolean;
  reason?: string;
  phrase?: string;
  asOf?: string;
  universe?: string[];
  deploymentClimate?: any;
  alignmentDrift?: any;
  cognitiveMemory?: any;
  shadowStructures?: any;
  regimeContinuity?: any;
};

// ─── Time-since formatter ──────────────────────────────────────────────
function timeAgo(iso?: string): string {
  if (!iso) return '—';
  const ts = new Date(iso).getTime();
  if (!ts) return '—';
  const dt = Math.floor((Date.now() - ts) / 1000);
  if (dt < 60) return `${dt}s ago`;
  if (dt < 3600) return `${Math.floor(dt / 60)}m ago`;
  if (dt < 86400) return `${Math.floor(dt / 3600)}h ago`;
  return `${Math.floor(dt / 86400)}d ago`;
}

// ─── Coherence → energy token ──────────────────────────────────────────
function energyForCoherence(coh: string): any {
  if (coh === 'aligned') return 'compression';      // subdued amber
  if (coh === 'divergent') return 'flux';           // dusty amber
  if (coh === 'partial') return 'suppression';      // neutral blue-grey
  return 'dormant';                                  // silent
}

export default function OperatorObservatoryScreen() {
  const colors = useColors();
  const { capabilities, loaded: capsLoaded } = useCapabilities();
  const [state, setState] = useState<ObservatoryState | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await mbrainApi.observatoryState();
      setState(res as ObservatoryState);
    } catch (e) {
      setState({ ok: false, reason: 'fetch_failed' } as any);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    load();
  }, [load]);

  // Operator capability check — restricted view when not authorized
  if (capsLoaded && !capabilities.executionConsole) {
    return <RestrictedEnvironmentScreen />;
  }

  if (loading) {
    return (
      <SafeAreaView style={[styles.root, { backgroundColor: colors.background }]} edges={['top']}>
        <ActivityIndicator style={{ marginTop: 60 }} color={colors.text} />
      </SafeAreaView>
    );
  }

  // Truthful absence
  if (!state || !state.ok) {
    return (
      <SafeAreaView style={[styles.root, { backgroundColor: colors.background }]} edges={['top']}>
        <ObservatoryHeader colors={colors} asOf={state?.asOf} onRefresh={onRefresh} />
        <ScrollView
          contentContainerStyle={{ padding: 18 }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.text} />}
        >
          <View style={[styles.emptyCard, { borderColor: colors.border, backgroundColor: colors.surface }]}>
            <Text style={[styles.emptyTitle, { color: colors.text }]}>
              Insufficient continuity
            </Text>
            <Text style={[styles.emptyBody, { color: colors.textMuted }]}>
              {state?.phrase || 'Insufficient continuity for interpretive surface.'}
            </Text>
          </View>
        </ScrollView>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={[styles.root, { backgroundColor: colors.background }]} edges={['top']}>
      <ObservatoryHeader colors={colors} asOf={state.asOf} onRefresh={onRefresh} />
      <ScrollView
        contentContainerStyle={{ padding: 18, paddingBottom: 60 }}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.text} />}
      >
        <DeploymentClimateSection data={state.deploymentClimate} colors={colors} />
        <AlignmentDriftSection data={state.alignmentDrift} colors={colors} />
        <CognitiveMemorySection data={state.cognitiveMemory} colors={colors} />
        <ShadowStructuresSection data={state.shadowStructures} colors={colors} />
        <RegimeContinuitySection data={state.regimeContinuity} colors={colors} />
      </ScrollView>
    </SafeAreaView>
  );
}

// ─── Subheader (subtitle + manual refresh) ─────────────────────────────
//
// The big "OPERATOR OBSERVATORY" page-title has moved to the route
// header in /operator/observatory.tsx — this row only carries the
// contextual subtitle and the refresh action so the layout no longer
// breaks at narrow widths.
const ObservatoryHeader: React.FC<{ colors: any; asOf?: string; onRefresh: () => void }> = ({
  colors, asOf, onRefresh,
}) => (
  <View style={[styles.head, { borderBottomColor: colors.border }]}>
    <View style={{ flex: 1, paddingRight: 12 }}>
      <Text style={[styles.headSub, { color: colors.textMuted }]} numberOfLines={2}>
        interpretive continuity surface · last interpreted {timeAgo(asOf)}
      </Text>
    </View>
    <TouchableOpacity
      style={[styles.refreshBtn, { borderColor: colors.border }]}
      activeOpacity={0.7}
      onPress={onRefresh}
    >
      <Ionicons name="refresh-outline" size={14} color={colors.textMuted} />
      <Text style={[styles.refreshBtnText, { color: colors.textMuted }]}>refresh</Text>
    </TouchableOpacity>
  </View>
);

// ─── Section wrapper ───────────────────────────────────────────────────
const Section: React.FC<{ title: string; subtitle?: string; colors: any; children: React.ReactNode }> = ({
  title, subtitle, colors, children,
}) => (
  <View style={styles.section}>
    <View style={styles.sectionHead}>
      <Text style={[styles.sectionTitle, { color: colors.text }]}>{title}</Text>
      {subtitle ? (
        <Text style={[styles.sectionSubtitle, { color: colors.textMuted }]}>{subtitle}</Text>
      ) : null}
    </View>
    <View style={[styles.sectionBody, { backgroundColor: colors.surface, borderColor: colors.border }]}>
      {children}
    </View>
  </View>
);

const KeyLine: React.FC<{ label: string; value?: string | null; colors: any; emphasis?: boolean }> = ({
  label, value, colors, emphasis,
}) => (
  <View style={styles.keyLine}>
    <Text style={[styles.keyLabel, { color: colors.textMuted }]}>{label}</Text>
    <Text style={[
      styles.keyValue,
      { color: colors.text, fontWeight: emphasis ? '800' : '600' },
    ]}>
      {value ?? '—'}
    </Text>
  </View>
);

// ─── Section 1 · Deployment Climate ────────────────────────────────────
const DeploymentClimateSection: React.FC<{ data: any; colors: any }> = ({ data, colors }) => {
  if (!data?.ok) {
    return (
      <Section title={t('observatory.deploymentClimate')} subtitle="current restraint field" colors={colors}>
        <Text style={[styles.degraded, { color: colors.textMuted }]}>
          {data?.phrase || 'climate not yet observed'}
        </Text>
      </Section>
    );
  }
  return (
    <Section title={t('observatory.deploymentClimate')} subtitle="current restraint field" colors={colors}>
      <Text style={[styles.phrase, { color: colors.text }]}>{data.phrase}</Text>
      <View style={[styles.divider, { backgroundColor: colors.border }]} />
      <KeyLine label="restraint integrity" value={data.restraintIntegrity} colors={colors} emphasis />
      {data.primaryVetoPhrase && (
        <KeyLine label="primary veto" value={data.primaryVetoPhrase} colors={colors} />
      )}
      <KeyLine label="observed verdicts" value={String(data.totalVerdicts ?? 0)} colors={colors} />
    </Section>
  );
};

// ─── Section 2 · Alignment Drift ───────────────────────────────────────
const AlignmentDriftSection: React.FC<{ data: any; colors: any }> = ({ data, colors }) => {
  if (!data?.ok) {
    return (
      <Section title={t('observatory.alignmentDrift')} subtitle="cross-module coherence" colors={colors}>
        <Text style={[styles.degraded, { color: colors.textMuted }]}>
          cognition runtimes not available for coherence reading
        </Text>
      </Section>
    );
  }
  return (
    <Section title={t('observatory.alignmentDrift')} subtitle="cross-module coherence" colors={colors}>
      <Text style={[styles.phrase, { color: colors.text }]}>{data.driftPhrase}</Text>
      <View style={[styles.divider, { backgroundColor: colors.border }]} />
      {Object.entries(data.perSymbol || {}).map(([sym, info]: any) => {
        const token = tokenFor(energyForCoherence(info.coherence));
        const accent = colors[token.colorKey] ?? colors.textMuted;
        return (
          <View key={sym} style={styles.coherenceRow}>
            <View style={styles.coherenceHead}>
              <View style={[styles.coherenceDot, { backgroundColor: accent, opacity: 0.65 }]} />
              <Text style={[styles.coherenceSym, { color: colors.text }]}>{sym}</Text>
              <Text style={[styles.coherenceLabel, { color: accent }]}>{info.coherence}</Text>
            </View>
            <Text style={[styles.coherencePhrase, { color: colors.textMuted, opacity: token.opacity }]}>
              {info.phrase}
            </Text>
            <Text style={[styles.coherenceLayers, { color: colors.textMuted }]}>
              technical · {info.layers.technical}   sentiment · {info.layers.sentiment}   fractal · {info.layers.fractal}
            </Text>
          </View>
        );
      })}
    </Section>
  );
};

// ─── Section 3 · Cognitive Memory ──────────────────────────────────────
const CognitiveMemorySection: React.FC<{ data: any; colors: any }> = ({ data, colors }) => {
  if (!data?.ok) {
    return (
      <Section title={t('observatory.cognitiveMemory')} subtitle="outcome accumulation" colors={colors}>
        <Text style={[styles.degraded, { color: colors.textMuted }]}>
          memory substrate not yet alive
        </Text>
      </Section>
    );
  }
  const coveragePct = Math.round((data.coverage || 0) * 100);
  return (
    <Section title={t('observatory.cognitiveMemory')} subtitle="outcome accumulation · not performance" colors={colors}>
      <Text style={[styles.phrase, { color: colors.text }]}>{data.phrase}</Text>
      <View style={[styles.divider, { backgroundColor: colors.border }]} />
      <KeyLine label="pending"        value={String(data.pending)}        colors={colors} />
      <KeyLine label="resolved"       value={String(data.resolved)}       colors={colors} />
      <KeyLine label="expired"        value={String(data.expired)}        colors={colors} />
      <KeyLine label="mature pending" value={String(data.maturePending)}  colors={colors} />
      <KeyLine label="coverage"       value={`${data.totalOutcomes}/${data.totalDecisions} · ${coveragePct}%`} colors={colors} />
      {data.classifications?.length > 0 && (
        <View style={{ marginTop: 6 }}>
          <Text style={[styles.subhead, { color: colors.textMuted }]}>classification topology</Text>
          {data.classifications.map((c: any, i: number) => (
            <View key={i} style={styles.distRow}>
              <Text style={[styles.distLabel, { color: colors.textMuted }]}>{c.classification}</Text>
              <Text style={[styles.distCount, { color: colors.text }]}>{c.count}</Text>
            </View>
          ))}
        </View>
      )}
    </Section>
  );
};

// ─── Section 4 · Shadow Structures ─────────────────────────────────────
const ShadowStructuresSection: React.FC<{ data: any; colors: any }> = ({ data, colors }) => {
  if (!data?.ok) {
    return (
      <Section title={t('observatory.shadowStructures')} subtitle="shadow verdict topology" colors={colors}>
        <Text style={[styles.degraded, { color: colors.textMuted }]}>
          {data?.phrase || 'topology not yet observed'}
        </Text>
      </Section>
    );
  }
  const dist = data.distribution || {};
  return (
    <Section title={t('observatory.shadowStructures')} subtitle="shadow verdict topology" colors={colors}>
      <Text style={[styles.phrase, { color: colors.text }]}>{data.phrase}</Text>
      <View style={[styles.divider, { backgroundColor: colors.border }]} />
      <KeyLine label="blocked"     value={String(dist.blocked ?? 0)}     colors={colors} />
      <KeyLine label="wait"        value={String(dist.wait ?? 0)}        colors={colors} />
      <KeyLine label="considered"  value={String(dist.considered ?? 0)}  colors={colors} />
      <KeyLine label="unresolved"  value={String(dist.unresolved ?? 0)}  colors={colors} />
      {data.topBlockedBy?.length > 0 && (
        <View style={{ marginTop: 6 }}>
          <Text style={[styles.subhead, { color: colors.textMuted }]}>veto attribution</Text>
          {data.topBlockedBy.slice(0, 5).map((b: any, i: number) => (
            <View key={i} style={styles.distRow}>
              <Text style={[styles.distLabel, { color: colors.textMuted }]}>{b.layer}</Text>
              <Text style={[styles.distCount, { color: colors.text }]}>{b.count}</Text>
            </View>
          ))}
        </View>
      )}
      {data.topReasons?.length > 0 && (
        <View style={{ marginTop: 6 }}>
          <Text style={[styles.subhead, { color: colors.textMuted }]}>recurring reasons</Text>
          {data.topReasons.slice(0, 5).map((r: any, i: number) => (
            <View key={i} style={styles.distRow}>
              <Text style={[styles.distLabel, { color: colors.textMuted, flex: 1 }]} numberOfLines={2}>· {r.reason}</Text>
              <Text style={[styles.distCount, { color: colors.text, marginLeft: 8 }]}>{r.count}</Text>
            </View>
          ))}
        </View>
      )}
    </Section>
  );
};

// ─── Section 5 · Regime Continuity ─────────────────────────────────────
const RegimeContinuitySection: React.FC<{ data: any; colors: any }> = ({ data, colors }) => {
  if (!data?.ok) {
    return (
      <Section title={t('observatory.regimeContinuity')} subtitle="structural phase persistence" colors={colors}>
        <Text style={[styles.degraded, { color: colors.textMuted }]}>
          structural substrate insufficient
        </Text>
      </Section>
    );
  }
  return (
    <Section title={t('observatory.regimeContinuity')} subtitle="structural phase persistence" colors={colors}>
      <Text style={[styles.phrase, { color: colors.text }]}>{data.phrase}</Text>
      <View style={[styles.divider, { backgroundColor: colors.border }]} />
      {Object.entries(data.perSymbol || {}).map(([sym, info]: any) => (
        <View key={sym} style={styles.regimeRow}>
          <Text style={[styles.regimeSym, { color: colors.text }]}>{sym}</Text>
          <Text style={[styles.regimeLabel, { color: colors.textMuted }]}>{info.label}</Text>
        </View>
      ))}
    </Section>
  );
};

// ─── Styles ────────────────────────────────────────────────────────────
const styles = StyleSheet.create({
  root: { flex: 1 },
  head: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 18, paddingVertical: 14, borderBottomWidth: 0.5,
  },
  headTitle: { fontSize: 13, fontWeight: '800', letterSpacing: 1.7 },
  headSub: { fontSize: 11, marginTop: 3, fontStyle: 'italic' },
  refreshBtn: {
    flexDirection: 'row', alignItems: 'center',
    borderWidth: 0.7, borderRadius: 14,
    paddingVertical: 6, paddingHorizontal: 10,
  },
  refreshBtnText: { fontSize: 10, letterSpacing: 0.9, marginLeft: 5 },

  section: { marginBottom: 22 },
  sectionHead: { marginBottom: 8, paddingHorizontal: 2 },
  sectionTitle: { fontSize: 11, fontWeight: '800', letterSpacing: 1.6 },
  sectionSubtitle: { fontSize: 10, marginTop: 2, fontStyle: 'italic' },
  sectionBody: { borderRadius: 12, borderWidth: 1, paddingVertical: 12, paddingHorizontal: 14 },

  phrase: { fontSize: 14, fontWeight: '600', lineHeight: 20, marginBottom: 8 },
  degraded: { fontSize: 12, fontStyle: 'italic' },
  divider: { height: 0.5, marginVertical: 8, opacity: 0.5 },
  subhead: { fontSize: 9, letterSpacing: 1.3, textTransform: 'uppercase', marginTop: 8, marginBottom: 4 },

  keyLine: {
    flexDirection: 'row', alignItems: 'baseline', justifyContent: 'space-between',
    paddingVertical: 4,
  },
  keyLabel: { fontSize: 11, letterSpacing: 0.4 },
  keyValue: { fontSize: 13, letterSpacing: 0.2 },

  coherenceRow: { paddingVertical: 7 },
  coherenceHead: { flexDirection: 'row', alignItems: 'center', marginBottom: 3 },
  coherenceDot: { width: 6, height: 6, borderRadius: 3, marginRight: 7 },
  coherenceSym: { fontSize: 13, fontWeight: '800', letterSpacing: 0.5, marginRight: 10 },
  coherenceLabel: { fontSize: 10, fontWeight: '700', letterSpacing: 1, textTransform: 'lowercase' },
  coherencePhrase: { fontSize: 12, fontStyle: 'italic', marginBottom: 2, marginLeft: 13 },
  coherenceLayers: { fontSize: 10, marginLeft: 13, letterSpacing: 0.3 },

  regimeRow: { flexDirection: 'row', alignItems: 'baseline', justifyContent: 'space-between', paddingVertical: 5 },
  regimeSym: { fontSize: 13, fontWeight: '800', letterSpacing: 0.6 },
  regimeLabel: { fontSize: 12, fontStyle: 'italic' },

  distRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 3 },
  distLabel: { fontSize: 12 },
  distCount: { fontSize: 13, fontWeight: '700' },

  emptyCard: { borderRadius: 12, borderWidth: 1, padding: 22, alignItems: 'flex-start' },
  emptyTitle: { fontSize: 14, fontWeight: '800', letterSpacing: 0.5, marginBottom: 6 },
  emptyBody: { fontSize: 13, lineHeight: 19, fontStyle: 'italic' },
});
