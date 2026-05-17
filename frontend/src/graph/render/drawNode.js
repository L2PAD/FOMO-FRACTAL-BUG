/**
 * Node Renderer - ЕДИНЫЙ для Influence и Routers
 * 
 * ЖЁСТКИЕ ПРАВИЛА:
 * - Лейбл формат: 0xABCD…1234 (4 символа + … + 4 символа)
 * - Текст ВНУТРИ круга, если не влезает — уменьшаем font-size
 * - State halo: ACCUMULATION = зелёный, DISTRIBUTION = красный, ROUTING = жёлтый
 * - Known entities show logo icons inside circles
 */

import { getNodeLabel } from '../core/formatLabel.js';

// ============ ЦВЕТА (FOMO-style) ============
const COLORS = {
  nodeFill: '#1a1f2e',
  nodeStroke: '#3a3f4b',
  nodeStrokeSelected: '#ffffff',
  textColor: '#e7e9ee',
  accumulation: '#30A46C',  // green (FOMO)
  distribution: '#E5484D',  // red (FOMO)
  router: '#EAB308',        // yellow (routing)
  verifiedDot: '#22c55e',
};

// ============ ENTITY LOGOS ============
const _API = process.env.REACT_APP_BACKEND_URL || '';
const _p = (u) => `${_API}/api/img-proxy?url=${encodeURIComponent(u)}`;
const ENTITY_LOGO_URLS = {
  'binance':     _p('https://assets.coingecko.com/coins/images/825/small/bnb-icon2_2x.png'),
  'coinbase':    _p('https://assets.coingecko.com/markets/images/23/small/Coinbase_Coin_Primary.png'),
  'kraken':      _p('https://assets.coingecko.com/markets/images/29/small/kraken.jpg'),
  'okx':         _p('https://assets.coingecko.com/markets/images/96/small/WeChat_Image_20220117220452.png'),
  'bybit':       _p('https://assets.coingecko.com/markets/images/698/small/bybit_spot.png'),
  'uniswap':     _p('https://assets.coingecko.com/coins/images/12504/small/uniswap-logo.png'),
  'aave':        _p('https://assets.coingecko.com/coins/images/12645/small/aave-token-round.png'),
  'curve':       _p('https://assets.coingecko.com/coins/images/12124/small/Curve.png'),
  'sushi':       _p('https://assets.coingecko.com/coins/images/12271/small/512x512_Logo_no_chop.png'),
  'compound':    _p('https://assets.coingecko.com/coins/images/10775/small/COMP.png'),
  'maker':       _p('https://assets.coingecko.com/coins/images/1364/small/Mark_Maker.png'),
  'lido':        _p('https://assets.coingecko.com/coins/images/13573/small/Lido_DAO.png'),
  'balancer':    _p('https://assets.coingecko.com/coins/images/11683/small/Balancer.png'),
  'link':        _p('https://assets.coingecko.com/coins/images/877/small/chainlink-new-logo.png'),
  'wintermute':  _p('https://assets.coingecko.com/coins/images/30572/small/wintermute.jpg'),
  'jump':        _p('https://assets.coingecko.com/coins/images/30572/small/wintermute.jpg'),
  'gemini':      _p('https://assets.coingecko.com/markets/images/24/small/gemini.png'),
  'bitfinex':    _p('https://assets.coingecko.com/markets/images/4/small/BItfinex.png'),
  'arbitrum':    _p('https://assets.coingecko.com/coins/images/16547/small/photo_2023-03-29_21.47.00.jpeg'),
  'optimism':    _p('https://assets.coingecko.com/coins/images/25244/small/Optimism.png'),
  'circle':      _p('https://assets.coingecko.com/coins/images/6319/small/usdc.png'),
  'wormhole':    _p('https://assets.coingecko.com/coins/images/35087/small/womrhole_logo_full_color_rgb_2000px_72ppi_fb766ac85a.png'),
  'stargate':    _p('https://assets.coingecko.com/coins/images/24413/small/STG_LOGO.png'),
};

// Module-level image cache
const _iconCache = new Map();
let _iconsLoading = false;

function _preloadIcons() {
  if (_iconsLoading) return;
  _iconsLoading = true;
  Object.entries(ENTITY_LOGO_URLS).forEach(([key, url]) => {
    if (_iconCache.has(key)) return;
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => _iconCache.set(key, img);
    img.onerror = () => _iconCache.set(key, null);
    img.src = url;
  });
}

// Start preloading immediately
_preloadIcons();

function getEntityIcon(label) {
  if (!label) return null;
  const lower = label.toLowerCase().replace(/_/g, ' ');
  for (const [key, img] of _iconCache.entries()) {
    if (img && (lower === key || lower.startsWith(key + ' ') || lower.includes(key))) {
      return img;
    }
  }
  return null;
}

// Verified entities set
const VERIFIED_ENTITIES = new Set([
  'binance', 'coinbase', 'jump trading', 'jump', 'wintermute',
  'uniswap', 'aave', 'lido', 'circle', 'kraken', 'okx', 'bybit',
  'gemini', 'bitfinex', 'maker', 'compound', 'curve',
  'sushiswap', 'arbitrum', 'optimism',
]);

function isVerifiedEntity(label) {
  if (!label) return false;
  const lower = label.toLowerCase().replace(/_/g, ' ');
  for (const key of VERIFIED_ENTITIES) {
    if (lower === key || lower.startsWith(key + ' ') || lower.includes(key)) return true;
  }
  return false;
}

// ============ РАЗМЕРЫ ============
const MIN_RADIUS = 16;
const MAX_RADIUS = 40;
const DEFAULT_RADIUS = 22;

/**
 * Получить радиус узла
 */
export function getNodeRadius(node) {
  if (!node) return DEFAULT_RADIUS;
  
  // Используем size если есть
  if (node.size && typeof node.size === 'number') {
    return Math.max(MIN_RADIUS, Math.min(MAX_RADIUS, node.size));
  }
  
  // Используем influenceScore для масштабирования
  const influence = node.influenceScore || node.sizeWeight || 0.3;
  return MIN_RADIUS + (MAX_RADIUS - MIN_RADIUS) * Math.min(1, Math.max(0, influence));
}

/**
 * Подобрать размер шрифта чтобы текст влез в круг
 */
function fitTextToCircle(ctx, text, maxWidth, baseFontSize = 12) {
  let size = baseFontSize;
  ctx.font = `600 ${size}px Gilroy, sans-serif`;
  
  while (ctx.measureText(text).width > maxWidth && size > 6) {
    size -= 0.5;
    ctx.font = `600 ${size}px Gilroy, sans-serif`;
  }
  
  return size;
}

/**
 * Отрисовка узла на canvas
 * 
 * @param {Object} node - данные узла
 * @param {CanvasRenderingContext2D} ctx - canvas context
 * @param {number} globalScale - текущий zoom scale
 * @param {Object} opts - { selected, hovered, dimmed }
 */
export function drawNode(node, ctx, globalScale, opts = {}) {
  const { selected = false, hovered = false, dimmed = false } = opts;
  
  const x = node.x;
  const y = node.y;
  
  if (x === undefined || y === undefined) return;
  
  const r = getNodeRadius(node);
  
  ctx.save();
  
  // Dimmed mode (для Active Path)
  if (dimmed) {
    ctx.globalAlpha = 0.15;
  }
  
  // ============ ОСНОВНОЙ КРУГ ============
  ctx.beginPath();
  ctx.arc(x, y, r, 0, Math.PI * 2);
  ctx.fillStyle = COLORS.nodeFill;
  ctx.fill();
  
  // Граница
  ctx.lineWidth = Math.max(1, 2 / globalScale);
  ctx.strokeStyle = selected ? COLORS.nodeStrokeSelected : COLORS.nodeStroke;
  ctx.stroke();
  
  // ============ STATE HALO ============
  const state = node.state;
  
  if (state === 'ACCUMULATION') {
    ctx.beginPath();
    ctx.arc(x, y, r + 3 / globalScale, 0, Math.PI * 2);
    ctx.lineWidth = 3 / globalScale;
    ctx.strokeStyle = COLORS.accumulation;
    ctx.stroke();
  } else if (state === 'DISTRIBUTION') {
    ctx.beginPath();
    ctx.arc(x, y, r + 3 / globalScale, 0, Math.PI * 2);
    ctx.lineWidth = 3 / globalScale;
    ctx.strokeStyle = COLORS.distribution;
    ctx.stroke();
  } else if (state === 'ROUTING') {
    ctx.beginPath();
    ctx.arc(x, y, r + 3 / globalScale, 0, Math.PI * 2);
    ctx.lineWidth = 2 / globalScale;
    ctx.strokeStyle = '#EAB308';
    ctx.stroke();
  }
  
  // ============ ICON OR LABEL ============
  const label = getNodeLabel(node);
  const fullName = (node.label || node.name || label || '').replace(/_/g, ' ');
  const icon = getEntityIcon(fullName);
  
  if (icon) {
    // Draw circular clipped logo
    ctx.save();
    ctx.beginPath();
    ctx.arc(x, y, r * 0.75, 0, Math.PI * 2);
    ctx.clip();
    const iconSize = r * 1.5;
    ctx.drawImage(icon, x - iconSize / 2, y - iconSize / 2, iconSize, iconSize);
    ctx.restore();
  } else {
    // Text label
    const maxTextWidth = r * 1.7;
    const baseFontSize = Math.max(10, Math.min(16, 14 / globalScale));
    const fontSize = fitTextToCircle(ctx, label, maxTextWidth, baseFontSize);
    
    ctx.font = `600 ${fontSize}px Gilroy, sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = COLORS.textColor;
    ctx.fillText(label, x, y);
  }
  
  // ============ VERIFIED DOT ============
  if (isVerifiedEntity(fullName)) {
    const dotR = r * 0.15;
    ctx.beginPath();
    ctx.arc(x + r * 0.65, y - r * 0.65, dotR, 0, Math.PI * 2);
    ctx.fillStyle = COLORS.verifiedDot;
    ctx.fill();
    ctx.strokeStyle = COLORS.nodeFill;
    ctx.lineWidth = 0.5;
    ctx.stroke();
  }
  
  // ============ SELECTION RING ============
  if (selected || hovered) {
    ctx.beginPath();
    ctx.arc(x, y, r + 6 / globalScale, 0, Math.PI * 2);
    ctx.lineWidth = 2 / globalScale;
    ctx.strokeStyle = selected ? '#ffffff' : 'rgba(255,255,255,0.5)';
    ctx.stroke();
  }
  
  ctx.restore();
}

/**
 * Проверка попадания точки в узел (для hover/click)
 */
export function nodeContainsPoint(node, px, py) {
  if (!node || node.x === undefined || node.y === undefined) return false;
  
  const r = getNodeRadius(node);
  const dx = px - node.x;
  const dy = py - node.y;
  
  return (dx * dx + dy * dy) <= (r * r);
}

export default { drawNode, getNodeRadius, nodeContainsPoint };
