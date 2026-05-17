/**
 * Deployment Profiles - Feature Flags
 * Single source of truth for feature activation
 * 
 * Profiles:
 * - twitter-only: Twitter parser + Extension + Telegram
 * - sentiment-only: ML + Sentiment pipeline
 * - twitter-sentiment: Twitter + Sentiment
 * - onchain-only: Indexer + Onchain analytics
 * - full: All services
 *
 * System Profiles (SYSTEM_PROFILE env):
 * - dev: All except heavy cron
 * - exchange_only: Exchange + Radar only (OnChain/Sentiment/Telegram cold)
 * - intel_only: Twitter + Sentiment only
 * - full: Everything enabled
 */

export type DeployProfile =
  | 'twitter-only'
  | 'sentiment-only'
  | 'twitter-sentiment'
  | 'onchain-only'
  | 'onchain-v2'
  | 'full'

export type SystemProfile = 'dev' | 'exchange_only' | 'intel_only' | 'full'

export function getSystemProfile(): SystemProfile {
  const raw = process.env.SYSTEM_PROFILE || 'dev'
  if (['dev', 'exchange_only', 'intel_only', 'full'].includes(raw)) {
    return raw as SystemProfile
  }
  console.warn(`[PROFILE] Unknown SYSTEM_PROFILE="${raw}", defaulting to "dev"`)
  return 'dev'
}

export interface FeatureFlags {
  twitter: boolean
  sentiment: boolean
  onchain: boolean
  onchain_v2: boolean
  indexer: boolean
  ml: boolean
}

export const FEATURES: FeatureFlags = {
  twitter: false,
  sentiment: false,
  onchain: false,
  onchain_v2: false,
  indexer: false,
  ml: false,
}

export function resolveFeatures(profile: DeployProfile): FeatureFlags {
  // Reset all features
  FEATURES.twitter = false
  FEATURES.sentiment = false
  FEATURES.onchain = false
  FEATURES.onchain_v2 = false
  FEATURES.indexer = false
  FEATURES.ml = false

  switch (profile) {
    case 'twitter-only':
      FEATURES.twitter = true
      break

    case 'sentiment-only':
      FEATURES.sentiment = true
      break

    case 'twitter-sentiment':
      FEATURES.twitter = true
      FEATURES.sentiment = true
      break

    case 'onchain-only':
      FEATURES.onchain = true
      FEATURES.indexer = true
      FEATURES.ml = true
      break

    case 'onchain-v2':
      FEATURES.onchain_v2 = true
      FEATURES.indexer = true
      FEATURES.ml = true
      break

    case 'full':
      FEATURES.twitter = true
      FEATURES.sentiment = true
      FEATURES.onchain = true
      FEATURES.onchain_v2 = true
      FEATURES.indexer = true
      FEATURES.ml = true
      break

    default:
      throw new Error(`Unknown DEPLOY_PROFILE: ${profile}`)
  }

  return FEATURES
}

export function getProfileDescription(profile: DeployProfile): string {
  const descriptions: Record<DeployProfile, string> = {
    'twitter-only': 'Twitter parser + Extension + Telegram + Admin',
    'sentiment-only': 'ML + Sentiment pipeline (no Twitter)',
    'twitter-sentiment': 'Twitter + Sentiment (full Twitter Intelligence)',
    'onchain-only': 'Indexer + Onchain analytics + ML (legacy)',
    'onchain-v2': 'OnChain V2 isolated module + Indexer + ML',
    'full': 'All services enabled',
  }
  return descriptions[profile]
}

export function getSystemProfileDescription(profile: SystemProfile): string {
  const descriptions: Record<SystemProfile, string> = {
    'dev': 'Development — all modules, no heavy cron',
    'exchange_only': 'Exchange + Radar only — OnChain/Sentiment/Telegram cold',
    'intel_only': 'Twitter + Sentiment only',
    'full': 'All services enabled (production)',
  }
  return descriptions[profile]
}
