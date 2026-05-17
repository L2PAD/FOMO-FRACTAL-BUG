/**
 * Filter Presets - Quick buttons
 */
export const PRESETS = [
  {
    id: 'cis-default',
    label: 'CIS Crypto (RU/UA)',
    apply: (f) => ({
      ...f,
      page: 1,
      lang: ['ru', 'uk', 'mixed'],
      minMembers: 1000,
      minCrypto: 0.08,
      sort: 'utility',
      order: 'desc',
    }),
  },
  {
    id: 'fast-growing',
    label: 'Fast Growing',
    apply: (f) => ({
      ...f,
      page: 1,
      minGrowth7: 0.10,
      maxFraud: 0.45,
      sort: 'growth7',
      order: 'desc',
    }),
  },
  {
    id: 'high-reach',
    label: 'High Reach',
    apply: (f) => ({
      ...f,
      page: 1,
      minReach: 5000,
      maxFraud: 0.5,
      sort: 'reach',
      order: 'desc',
    }),
  },
  {
    id: 'clean',
    label: 'Low Fraud',
    apply: (f) => ({
      ...f,
      page: 1,
      maxFraud: 0.25,
      sort: 'utility',
      order: 'desc',
    }),
  },
  {
    id: 'active',
    label: 'Very Active',
    apply: (f) => ({
      ...f,
      page: 1,
      minPostsPerDay: 2,
      sort: 'fresh',
      order: 'desc',
    }),
  },
];

export const GROUP_OPTIONS = [
  { value: 'Trading', label: 'Trading' },
  { value: 'Media', label: 'Media' },
  { value: 'Projects', label: 'Projects' },
  { value: 'VC', label: 'VC / Funds' },
  { value: 'Education', label: 'Education' },
];

export const TYPE_OPTIONS = [
  { value: 'Channel', label: 'Channel' },
  { value: 'Group', label: 'Group' },
];

export const SEGMENT_OPTIONS = [
  { value: 'Trading', label: 'Trading / Alpha' },
  { value: 'News', label: 'News / Media' },
  { value: 'NFT', label: 'NFT' },
  { value: 'Early', label: 'Early Projects' },
  { value: 'VC', label: 'VC / Funds' },
  { value: 'DeFi', label: 'DeFi' },
  { value: 'Airdrop', label: 'Airdrops' },
];
