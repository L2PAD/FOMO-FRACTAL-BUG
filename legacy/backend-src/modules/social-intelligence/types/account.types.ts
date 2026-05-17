/**
 * Account Profile Types
 */
export type AccountProfile = {
  accountId: string;
  name: string;
  sourceType: 'official' | 'project' | 'exchange' | 'media' | 'analyst' | 'influencer' | 'social' | 'unknown';
  trustScore: number;
  accuracyScore: number;
  earlySignalScore: number;
  amplificationPower: number;
  hypeScore: number;
};
