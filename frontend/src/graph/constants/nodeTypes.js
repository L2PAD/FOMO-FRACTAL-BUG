/**
 * Node Type Configuration (On-chain Intelligence)
 * 
 * All nodes render as grey circles.
 * Type is used for filtering only, NOT for visual differentiation.
 */

export const NODE_TYPES = {
  wallet:    { label: 'Wallet' },
  token:     { label: 'Token' },
  exchange:  { label: 'Exchange' },
  bridge:    { label: 'Bridge' },
  contract:  { label: 'Contract' },
  exit:      { label: 'Exit' },
  cluster:   { label: 'Cluster' },
  entity:    { label: 'Entity' },
  protocol:  { label: 'Protocol' },
  dex:       { label: 'DEX' },
  cex:       { label: 'CEX' },
  narrative: { label: 'Narrative' },
  alert:     { label: 'Alert' },
  signal:    { label: 'Signal' },
  route:     { label: 'Route' },
};

export const NODE_TYPE_MAP = {
  WALLET:           'wallet',
  TOKEN:            'token',
  DEX:              'dex',
  CEX:              'cex',
  BRIDGE:           'bridge',
  CONTRACT:         'contract',
  CROSS_CHAIN_EXIT: 'exit',
  actor:            'wallet',
  wallet:           'wallet',
  entity:           'entity',
  cluster:          'cluster',
  protocol:         'protocol',
  exchange:         'exchange',
  dex:              'dex',
  cex:              'cex',
  narrative:        'narrative',
  alert:            'alert',
  signal:           'signal',
  route:            'route',
};

export function mapNodeType(backendType) {
  return NODE_TYPE_MAP[backendType] || 'wallet';
}
