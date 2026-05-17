/**
 * Edge Type Configuration (On-chain Intelligence)
 * 
 * Edge COLOR is determined ONLY by direction (see graphColors.js).
 * Edge type is used for filtering only.
 */

export const EDGE_TYPES = {
  transfer:            { label: 'Transfer' },
  swap:                { label: 'Swap' },
  bridge:              { label: 'Bridge' },
  deposit:             { label: 'Deposit' },
  withdraw:            { label: 'Withdraw' },
  exit:                { label: 'Exit' },
  corridor:            { label: 'Corridor' },
  accumulation:        { label: 'Accumulation' },
  distribution:        { label: 'Distribution' },
  rotation:            { label: 'Rotation' },
  liquidity_provision: { label: 'Liquidity' },
  market_making:       { label: 'Market Making' },
  cluster_member:      { label: 'Cluster Member' },
  entity_control:      { label: 'Entity Control' },
  capital_route:       { label: 'Capital Route' },
  signal_link:         { label: 'Signal' },
  risk_link:           { label: 'Risk' },
  alert_link:          { label: 'Alert' },
};

export const EDGE_TYPE_MAP = {
  TRANSFER:              'transfer',
  SWAP:                  'swap',
  BRIDGE:                'bridge',
  DEPOSIT:               'deposit',
  WITHDRAW:              'withdraw',
  CONTRACT_CALL:         'transfer',
  EXIT:                  'exit',
  FLOW_CORRELATION:      'transfer',
  TOKEN_OVERLAP:         'transfer',
  TEMPORAL_SYNC:         'transfer',
  BRIDGE_ACTIVITY:       'bridge',
  BEHAVIORAL_SIMILARITY: 'transfer',
  accumulation:          'accumulation',
  distribution:          'distribution',
  rotation:              'rotation',
  liquidity_provision:   'liquidity_provision',
  market_making:         'market_making',
  cluster_member:        'cluster_member',
  entity_control:        'entity_control',
  capital_route:         'capital_route',
  signal_link:           'signal_link',
  risk_link:             'risk_link',
  alert_link:            'alert_link',
};

export function mapEdgeType(backendType) {
  return EDGE_TYPE_MAP[backendType] || 'transfer';
}
