import React, { useMemo } from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppMode } from '../../../stores/app-mode.store';
import { useColors } from '../../../core/useColors';
import { useT } from '../../../core/i18n';

export function FomoReturnScreen() {
  const switchToIntelligence = useAppMode((s) => s.switchToIntelligence);
  const colors = useColors();
  const t = useT();
  const styles = useMemo(() => makeStyles(colors), [colors]);

  return (
    <View style={styles.container}>
      <View style={styles.card}>
        <View style={styles.header}>
          <Ionicons name="flash" size={32} color={colors.accent} />
          <Text style={styles.title}>{t('trade.fomoIntelligence')}</Text>
        </View>
        
        <View style={styles.verdict}>
          <Text style={styles.verdictLabel}>{t('trade.currentVerdict')}</Text>
          <Text style={[styles.verdictValue, { color: colors.buy }]}>BUY</Text>
          <Text style={styles.confidence}>72% {t('trade.confidence')}</Text>
        </View>
        
        <View style={styles.priceRow}>
          <Text style={styles.priceLabel}>BTC</Text>
          <Text style={styles.priceValue}>$84,500</Text>
        </View>
        
        <TouchableOpacity style={[styles.button, { backgroundColor: colors.accent }]} onPress={switchToIntelligence}>
          <Text style={[styles.buttonText, { color: colors.background }]}>{t('trade.openIntel')}</Text>
          <Ionicons name="arrow-forward" size={18} color={colors.background} />
        </TouchableOpacity>
      </View>
      
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>{t('trade.quickSignals')}</Text>
        <View style={styles.signalsRow}>
          <View style={styles.signalChip}>
            <Text style={styles.signalLabel}>Exchange</Text>
            <Text style={[styles.signalValue, { color: colors.bullish }]}>BULLISH</Text>
          </View>
          <View style={styles.signalChip}>
            <Text style={styles.signalLabel}>Sentiment</Text>
            <Text style={[styles.signalValue, { color: colors.neutral }]}>NEUTRAL</Text>
          </View>
          <View style={styles.signalChip}>
            <Text style={styles.signalLabel}>On-chain</Text>
            <Text style={[styles.signalValue, { color: colors.bullish }]}>BULLISH</Text>
          </View>
        </View>
      </View>
    </View>
  );
}

const makeStyles = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background, padding: 16 },
  card: { backgroundColor: colors.surface, borderRadius: 16, padding: 24, borderWidth: 1, borderColor: colors.accent + '40' },
  header: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 24 },
  title: { fontSize: 18, fontWeight: '700', color: colors.textPrimary },
  verdict: { alignItems: 'center', marginBottom: 24 },
  verdictLabel: { fontSize: 12, color: colors.textMuted },
  verdictValue: { fontSize: 36, fontWeight: '900', marginTop: 4 },
  confidence: { fontSize: 14, color: colors.textSecondary, marginTop: 4 },
  priceRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 16, borderTopWidth: 1, borderTopColor: colors.border },
  priceLabel: { fontSize: 16, fontWeight: '600', color: colors.textPrimary },
  priceValue: { fontSize: 18, fontWeight: '700', color: colors.textPrimary },
  button: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', padding: 16, borderRadius: 10, marginTop: 16, gap: 8 },
  buttonText: { fontSize: 14, fontWeight: '700' },
  section: { marginTop: 32 },
  sectionTitle: { fontSize: 10, fontWeight: '700', color: colors.textMuted, letterSpacing: 1, marginBottom: 16 },
  signalsRow: { flexDirection: 'row', gap: 8 },
  signalChip: { flex: 1, backgroundColor: colors.surface, borderRadius: 10, padding: 16, alignItems: 'center' },
  signalLabel: { fontSize: 10, color: colors.textMuted },
  signalValue: { fontSize: 12, fontWeight: '700', marginTop: 4 },
});
