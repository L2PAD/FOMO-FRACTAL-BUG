import React, { useMemo } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useColors } from '../../../core/useColors';
import { useT } from '../../../core/i18n';

const mockMarkets = {
  watchlist: [
    { symbol: 'BTCUSDT', price: 84500, change: 2.3 },
    { symbol: 'ETHUSDT', price: 3250, change: 1.8 },
    { symbol: 'SOLUSDT', price: 142, change: 4.2 },
  ],
  topMovers: [
    { symbol: 'PEPE', price: 0.000012, change: 15.2 },
    { symbol: 'ARBUSDT', price: 1.42, change: 8.5 },
    { symbol: 'OPUSDT', price: 2.85, change: -3.2 },
  ],
  allMarkets: [
    { symbol: 'DOGEUSDT', price: 0.145, change: 1.2 },
    { symbol: 'XRPUSDT', price: 0.62, change: -0.5 },
    { symbol: 'ADAUSDT', price: 0.58, change: 0.8 },
    { symbol: 'AVAXUSDT', price: 42.5, change: 2.1 },
    { symbol: 'DOTUSDT', price: 8.2, change: -1.1 },
    { symbol: 'LINKUSDT', price: 18.5, change: 3.4 },
  ],
};

const formatPrice = (price: number) => {
  if (price < 0.01) return price.toFixed(6);
  if (price < 1) return price.toFixed(4);
  if (price < 1000) return price.toFixed(2);
  return price.toLocaleString();
};

function MarketItem({ symbol, price, change, colors }: { symbol: string; price: number; change: number; colors: any }) {
  const isPositive = change >= 0;
  return (
    <TouchableOpacity style={[mItemStyles.item, { borderBottomColor: colors.border }]}>
      <View style={mItemStyles.left}>
        <Text style={[mItemStyles.symbol, { color: colors.textPrimary }]}>{symbol.replace('USDT', '')}</Text>
        <Text style={[mItemStyles.pair, { color: colors.textMuted }]}>/USDT</Text>
      </View>
      <View style={mItemStyles.right}>
        <Text style={[mItemStyles.price, { color: colors.textPrimary }]}>${formatPrice(price)}</Text>
        <Text style={[mItemStyles.change, { color: isPositive ? colors.buy : colors.sell }]}>
          {isPositive ? '+' : ''}{change.toFixed(1)}%
        </Text>
      </View>
    </TouchableOpacity>
  );
}

const mItemStyles = StyleSheet.create({
  item: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', padding: 16, borderBottomWidth: 1 },
  left: { flexDirection: 'row', alignItems: 'baseline' },
  symbol: { fontSize: 14, fontWeight: '600' },
  pair: { fontSize: 12 },
  right: { alignItems: 'flex-end' },
  price: { fontSize: 14, fontWeight: '600' },
  change: { fontSize: 12, fontWeight: '600' },
});

export function MarketsScreen() {
  const colors = useColors();
  const t = useT();
  const styles = useMemo(() => makeStyles(colors), [colors]);

  return (
    <ScrollView style={styles.container}>
      <View style={styles.searchContainer}>
        <Ionicons name="search" size={18} color={colors.textMuted} />
        <TextInput
          style={styles.searchInput}
          placeholder={t('trade.searchMarkets')}
          placeholderTextColor={colors.textMuted}
        />
      </View>

      <Text style={styles.sectionTitle}>WATCHLIST</Text>
      <View style={styles.section}>
        {mockMarkets.watchlist.map((m) => (
          <MarketItem key={m.symbol} {...m} colors={colors} />
        ))}
      </View>

      <Text style={styles.sectionTitle}>{t('tradeMarkets.topMovers')}</Text>
      <View style={styles.section}>
        {mockMarkets.topMovers.map((m) => (
          <MarketItem key={m.symbol} {...m} colors={colors} />
        ))}
      </View>

      <Text style={styles.sectionTitle}>{t('tradeMarkets.allMarkets')}</Text>
      <View style={styles.section}>
        {mockMarkets.allMarkets.map((m) => (
          <MarketItem key={m.symbol} {...m} colors={colors} />
        ))}
      </View>
      
      <View style={{ height: 20 }} />
    </ScrollView>
  );
}

const makeStyles = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background, padding: 16 },
  searchContainer: { flexDirection: 'row', alignItems: 'center', backgroundColor: colors.surface, borderRadius: 10, paddingHorizontal: 16, marginBottom: 24 },
  searchInput: { flex: 1, paddingVertical: 16, paddingHorizontal: 8, fontSize: 14, color: colors.textPrimary },
  sectionTitle: { fontSize: 10, fontWeight: '700', color: colors.textMuted, letterSpacing: 1, marginBottom: 8, marginTop: 16 },
  section: { backgroundColor: colors.surface, borderRadius: 10 },
});
