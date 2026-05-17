/**
 * SourceLogo — news/platform/exchange logo (CoinDesk, X, Binance, Telegram, …).
 *
 * Usage:
 *   <SourceLogo slug="coindesk" size={20} />
 *   <SourceLogo slug="twitter"  size={16} rounded={false} />
 *
 * Backed by GET /api/assets/source/{slug} which redirects to the right
 * brand asset (or transparent-generic fallback for unknown sources).
 */
import React, { memo, useMemo } from 'react';
import { Image, View, StyleSheet } from 'react-native';

interface SourceLogoProps {
  slug: string;
  size?: number;
  rounded?: boolean;
  style?: object;
  testID?: string;
}

const BACKEND_URL =
  process.env.EXPO_PUBLIC_BACKEND_URL ||
  process.env.EXPO_PUBLIC_API_URL ||
  '';

export const SourceLogo = memo(function SourceLogo({
  slug,
  size = 20,
  rounded = true,
  style,
  testID,
}: SourceLogoProps) {
  const uri = useMemo(() => {
    if (!slug) return '';
    const base = BACKEND_URL.replace(/\/$/, '');
    return `${base}/api/assets/source/${encodeURIComponent(slug.toLowerCase())}`;
  }, [slug]);

  const radius = rounded ? size / 2 : Math.max(3, size / 8);

  if (!uri) {
    return <View style={[styles.placeholder, { width: size, height: size, borderRadius: radius }, style]} />;
  }

  return (
    <View
      style={[styles.wrap, { width: size, height: size, borderRadius: radius }, style]}
      testID={testID ?? `source-logo-${slug}`}
    >
      <Image
        source={{ uri }}
        style={{ width: size, height: size, borderRadius: radius }}
        resizeMode="cover"
        accessibilityLabel={`${slug} logo`}
      />
    </View>
  );
});

const styles = StyleSheet.create({
  wrap: { overflow: 'hidden', backgroundColor: '#0F141B' },
  placeholder: { backgroundColor: '#16202B' },
});

export default SourceLogo;
