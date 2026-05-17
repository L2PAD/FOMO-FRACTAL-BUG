/**
 * CoinIcon — Compact inline crypto icon.
 * Same height as text, doesn't take extra space.
 */
import React from 'react';
import { Image, StyleSheet } from 'react-native';
import { getCryptoIconUrl } from '../utils/crypto-icons';

interface Props {
  symbol: string;
  size?: number;
}

export function CoinIcon({ symbol, size = 16 }: Props) {
  return (
    <Image
      source={{ uri: getCryptoIconUrl(symbol) }}
      style={[styles.icon, { width: size, height: size, borderRadius: size / 2 }]}
    />
  );
}

const styles = StyleSheet.create({
  icon: { resizeMode: 'cover' },
});
