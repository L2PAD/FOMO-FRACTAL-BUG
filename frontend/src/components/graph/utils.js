export const fmtUsd = (v) => {
  if (!v && v !== 0) return '$0';
  const abs = Math.abs(v);
  if (abs >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `$${(v / 1e3).toFixed(1)}K`;
  return `$${v.toFixed(0)}`;
};

export const MODE_LABELS = {
  smart_money: 'Smart Money',
  cex_flow: 'CEX Flow',
  token_rotation: 'Token Rotation',
  entity: 'Entity',
  risk: 'Risk',
};

export const MODE_CATEGORY_MAP = {
  smart_money: 'smart_money',
  token_rotation: 'token_flow',
  entity: 'entity',
  risk: 'risk',
  cex_flow: 'route',
};
