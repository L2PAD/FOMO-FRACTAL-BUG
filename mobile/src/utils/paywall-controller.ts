/**
 * Paywall controller — avoids circular dependency
 * Import this instead of IntelligenceShell for openPaywall
 */
export type PaywallReason = 'expired' | 'default' | 'contextual';

let _showPaywall: ((reason?: PaywallReason) => void) | null = null;

export function registerPaywallOpener(fn: (reason?: PaywallReason) => void) {
  _showPaywall = fn;
}

export function openPaywall(reason?: PaywallReason) {
  _showPaywall?.(reason);
}
