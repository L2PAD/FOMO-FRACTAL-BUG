/**
 * P1 <GatedBlock> — Web implementation.
 * 
 * Renders real children if the block is visible, or a locked placeholder
 * with a CTA that opens AuthGateModal (guest → auth) or the existing
 * checkout flow (auth_free → pro).
 */
import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, Pressable, StyleSheet } from 'react-native';
import { useAccessBlock, useAccessStore } from '../../stores/access.store';
import AuthGateModal from '../auth/AuthGateModal';

export interface GatedBlockProps {
  blockKey: string;
  children: React.ReactNode;
  fallback?: React.ReactNode;
  ctaOverride?: string;
  surface?: string;
}

export default function GatedBlock({
  blockKey,
  children,
  fallback,
  ctaOverride,
  surface = 'unknown',
}: GatedBlockProps) {
  const block = useAccessBlock(blockKey);
  const trackEvent = useAccessStore((s) => s.trackEvent);
  const [authOpen, setAuthOpen] = useState(false);

  useEffect(() => {
    if (block.locked) {
      trackEvent('web_block_viewed_locked', {
        block_key: blockKey,
        surface,
      });
    }
  }, [block.locked, blockKey, surface, trackEvent]);

  const handleUnlock = useCallback(() => {
    trackEvent('web_cta_click', {
      block_key: blockKey,
      surface,
      cta_label: ctaOverride || block.cta || 'Unlock',
    });
    if (block.unlock_reason === 'auth_required') {
      setAuthOpen(true);
    } else if (block.unlock_reason === 'pro_required') {
      // Hand off to existing checkout flow
      trackEvent('web_paywall_shown', { block_key: blockKey, surface });
      try {
        // Use window.location as fallback — existing checkout usually
        // hooks into a navigation event.
        if (typeof window !== 'undefined') {
          window.dispatchEvent(
            new CustomEvent('open-paywall', {
              detail: { block: blockKey, surface },
            }),
          );
        }
      } catch {}
    }
  }, [block, blockKey, surface, ctaOverride, trackEvent]);

  // Not gated OR guard is pro-only (which existing mobile code already handles via isPro pill).
  // P1 GatedBlock's role on Web is to intercept GUEST → AUTH only.
  if (!block.locked || block.unlock_reason !== 'auth_required') {
    return <>{children}</>;
  }

  // Locked for guest — render fallback or default auth placeholder.
  if (fallback) {
    return <>{fallback}</>;
  }

  const cta = ctaOverride || block.cta || 'Continue';
  return (
    <>
      <View style={styles.card} testID={`gated-${blockKey}`}>
        <View style={styles.iconRow}>
          <Text style={styles.lockIcon}>🔒</Text>
          <Text style={styles.label}>
            {block.unlock_reason === 'pro_required' ? 'PRO feature' : 'Sign in to unlock'}
          </Text>
        </View>
        <Text style={styles.hint}>
          {block.unlock_reason === 'pro_required'
            ? 'This block is part of PRO. One click to unlock.'
            : 'Create your account to see this block — your subscription stays attached to you.'}
        </Text>
        <Pressable onPress={handleUnlock} style={styles.cta}>
          <Text style={styles.ctaText}>{cta} ›</Text>
        </Pressable>
      </View>
      <AuthGateModal
        open={authOpen}
        onClose={() => setAuthOpen(false)}
        surface={surface}
        blockKey={blockKey}
      />
    </>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#0F141B',
    borderColor: '#16202B',
    borderWidth: 1,
    borderRadius: 14,
    padding: 16,
    marginVertical: 8,
  },
  iconRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 8,
  },
  lockIcon: { fontSize: 14 },
  label: {
    fontSize: 11,
    fontWeight: '800',
    color: '#a1a1aa',
    letterSpacing: 1.6,
    textTransform: 'uppercase',
  },
  hint: {
    fontSize: 13,
    color: '#d4d4d8',
    lineHeight: 19,
    marginBottom: 12,
  },
  cta: {
    backgroundColor: '#F5C451',
    paddingVertical: 10,
    paddingHorizontal: 16,
    borderRadius: 10,
    alignItems: 'center',
  },
  ctaText: {
    color: '#0f172a',
    fontSize: 13,
    fontWeight: '800',
    letterSpacing: 0.2,
  },
});
