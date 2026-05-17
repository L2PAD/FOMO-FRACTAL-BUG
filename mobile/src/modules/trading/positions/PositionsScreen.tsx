import React, { useMemo } from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppMode } from '../../../stores/app-mode.store';
import { useColors } from '../../../core/useColors';
import { useT } from '../../../core/i18n';

export function PositionsScreen() {
  const { setTradingTab } = useAppMode();
  const colors = useColors();
  const t = useT();
  const styles = useMemo(() => makeStyles(colors), [colors]);

  return (
    <View style={styles.container}>
      <View style={styles.content}>
        <View style={styles.iconContainer}>
          <Ionicons name="layers" size={48} color={colors.textMuted} />
        </View>
        
        <Text style={styles.title}>{t('trade.noPositions')}</Text>
        
        <Text style={styles.description}>
          {t('trade.startTrading')}
        </Text>
        
        <TouchableOpacity 
          style={styles.button}
          onPress={() => setTradingTab('MARKET')}
        >
          <Text style={styles.buttonText}>{t('trade.goMarkets')}</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const makeStyles = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background, justifyContent: 'center', alignItems: 'center', padding: 32 },
  content: { alignItems: 'center' },
  iconContainer: { width: 100, height: 100, borderRadius: 50, backgroundColor: colors.surface, alignItems: 'center', justifyContent: 'center', marginBottom: 24 },
  title: { fontSize: 18, fontWeight: '600', color: colors.textPrimary },
  description: { fontSize: 14, color: colors.textSecondary, textAlign: 'center', marginTop: 8 },
  button: { backgroundColor: colors.surface, paddingHorizontal: 32, paddingVertical: 16, borderRadius: 10, marginTop: 32 },
  buttonText: { fontSize: 14, fontWeight: '600', color: colors.textPrimary },
});
