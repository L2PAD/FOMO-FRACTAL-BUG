/**
 * AssetLogo — drop-in component for real crypto logos.
 *
 * Usage:
 *   <AssetLogo symbol="BTC" size={32} />
 *   <AssetLogo symbol="ETH" size={24} fallback="ETH" />  // text fallback while loading
 *
 * Backed by /api/assets/logo/{symbol}?size=small|thumb|large which
 * redirects to CoinGecko CDN. Image is cached by the browser/RN Image.
 *
 * Zero external deps. Works across iOS, Android, and web.
 */
import React, { memo, useMemo } from 'react';
import { Image, View, Text, StyleSheet } from 'react-native';

type ImgSize = 'thumb' | 'small' | 'large';

interface AssetLogoProps {
  symbol: string;
  size?: number;              // px, defaults 24
  variant?: ImgSize;          // thumb | small | large (backend img variant)
  rounded?: boolean;          // true = circle (default)
  fallback?: string;          // text fallback (e.g. symbol) while image loading / failed
  style?: object;
  testID?: string;
}

const BACKEND_URL =
  process.env.EXPO_PUBLIC_BACKEND_URL ||
  process.env.EXPO_PUBLIC_API_URL ||
  '';

function pickVariant(size: number): ImgSize {
  if (size <= 24) return 'thumb';
  if (size <= 64) return 'small';
  return 'large';
}

export const AssetLogo = memo(function AssetLogo({
  symbol,
  size = 24,
  variant,
  rounded = true,
  fallback,
  style,
  testID,
}: AssetLogoProps) {
  const uri = useMemo(() => {
    if (!symbol) return '';
    const v = variant || pickVariant(size);
    const base = BACKEND_URL.replace(/\/$/, '');
    // If BACKEND_URL empty — use relative path (works on web).
    return `${base}/api/assets/logo/${encodeURIComponent(symbol.toUpperCase())}?size=${v}`;
  }, [symbol, size, variant]);

  const radius = rounded ? size / 2 : Math.max(4, size / 8);

  if (!uri) {
    return (
      <View
        style={[styles.placeholder, { width: size, height: size, borderRadius: radius }, style]}
        testID={testID}
      >
        {fallback ? <Text style={[styles.placeholderText, { fontSize: size * 0.4 }]}>{fallback}</Text> : null}
      </View>
    );
  }

  return (
    <View
      style={[
        styles.wrap,
        { width: size, height: size, borderRadius: radius },
        style,
      ]}
      testID={testID ?? `asset-logo-${symbol}`}
    >
      <Image
        source={{ uri }}
        style={{ width: size, height: size, borderRadius: radius }}
        // @ts-ignore RN web cachePolicy noop
        resizeMode="cover"
        accessibilityLabel={`${symbol} logo`}
      />
    </View>
  );
});

const styles = StyleSheet.create({
  wrap: {
    overflow: 'hidden',
    backgroundColor: '#0F141B',
  },
  placeholder: {
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#16202B',
  },
  placeholderText: {
    color: '#a1a1aa',
    fontWeight: '600',
    letterSpacing: 0.5,
  },
});

export default AssetLogo;
