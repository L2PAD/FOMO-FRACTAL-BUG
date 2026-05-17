import React, { useRef, useCallback, useState, useEffect, useMemo, memo } from "react";
import ForceGraph from "react-force-graph-2d";
import { NODE_TYPES } from "../graph/constants/nodeTypes";
import { EDGE_TYPES } from "../graph/constants/edgeTypes";
import { resolveNodeLabel } from "../graph/utils/nodeLabelResolver";

// FOMO-style node colors — Arkham-level tuning
const NODE_FILL = '#232938';
const NODE_STROKE = '#596172';
const MAIN_NODE_GLOW = '#4f8cff';

// Known verified entities for green verification marker
const VERIFIED_ENTITIES = new Set([
  'binance', 'coinbase', 'jump trading', 'jump', 'wintermute',
  'uniswap', 'aave', 'lido', 'circle', 'kraken', 'okx', 'bybit',
  'ftx', 'gemini', 'bitfinex', 'maker', 'compound', 'curve',
  'sushiswap', 'arbitrum', 'optimism',
]);

// === Entity Logo URLs ===
// Key: lowercase prefix to match against fullName/label
// Proxied through backend to avoid CORS issues with canvas drawing
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
  'ftx':         _p('https://assets.coingecko.com/markets/images/349/small/ftx.jpg'),
  'arbitrum':    _p('https://assets.coingecko.com/coins/images/16547/small/photo_2023-03-29_21.47.00.jpeg'),
  'optimism':    _p('https://assets.coingecko.com/coins/images/25244/small/Optimism.png'),
  'circle':      _p('https://assets.coingecko.com/coins/images/6319/small/usdc.png'),
  'wormhole':    _p('https://assets.coingecko.com/coins/images/35087/small/womrhole_logo_full_color_rgb_2000px_72ppi_fb766ac85a.png'),
  'stargate':    _p('https://assets.coingecko.com/coins/images/24413/small/STG_LOGO.png'),
  'a16z':        _p('https://assets.coingecko.com/coins/images/825/small/bnb-icon2_2x.png'),
};

function matchEntityLogo(label) {
  if (!label) return null;
  const lower = label.toLowerCase().replace(/_/g, ' ');
  for (const [key, url] of Object.entries(ENTITY_LOGO_URLS)) {
    if (lower === key || lower.startsWith(key + ' ') || lower.startsWith(key + '_') || lower.includes(key)) {
      return url;
    }
  }
  return null;
}

function isVerifiedEntity(label) {
  if (!label) return false;
  const lower = label.toLowerCase().replace(/_/g, ' ');
  for (const key of VERIFIED_ENTITIES) {
    if (lower === key || lower.startsWith(key + ' ') || lower.startsWith(key + '_')) return true;
  }
  return false;
}

function shortNodeLabel(fullName) {
  if (!fullName) return '';
  // Replace underscores with spaces
  const clean = fullName.replace(/_/g, ' ');
  if (clean.length <= 4) return clean;
  return clean.slice(0, 4) + '\u2026';
}

// === Distance-aware lane offset (Arkham-style) ===
// spread ∝ sqrt(distance) + clamp + compression
function getOffset(laneIndex, laneCount, distance) {
  if (laneCount <= 1) return 0;

  const center = (laneCount - 1) / 2;

  const K = 0.02;
  const MIN_SPREAD = 2;
  const MAX_SPREAD = 18;

  const spread = Math.min(
    MAX_SPREAD,
    Math.max(MIN_SPREAD, K * Math.sqrt(distance))
  );

  const baseOffset = (laneIndex - center) * spread;

  // Compression layer for very close nodes
  const DIST_THRESHOLD = 80;
  const compression = Math.min(1, distance / DIST_THRESHOLD);

  return baseOffset * compression;
}

const CURVE_FACTOR = 0.5;

// ============================================
// MEMOIZED GRAPH CANVAS
// ============================================
const GraphCanvas = memo(function GraphCanvas({
  forceRef, graphData, width, height, drawNode, drawLink,
  handleNodeDrag, handleNodeDragEnd, handleEngineStop,
  handleNodeClick, onNodeHover, onLinkHover, onLinkClick,
  onRenderFramePost, hasExternalHover,
}) {
  return (
    <ForceGraph
      ref={forceRef}
      graphData={graphData}
      width={width}
      height={height}
      backgroundColor="#0a0e1a"
      nodeCanvasObject={drawNode}
      linkCanvasObject={drawLink}
      nodeLabel={hasExternalHover ? '' : ((node) => node.label)}
      nodeRelSize={6}
      nodePointerAreaPaint={(node, color, ctx) => {
        const size = node.size || 5;
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(node.x, node.y, size, 0, 2 * Math.PI);
        ctx.fill();
      }}
      linkWidth={1}
      linkDirectionalParticles={0}
      linkHoverPrecision={8}
      linkPointerAreaPaint={(link, paintStyle, ctx) => {
        // Match the distance-aware lane compression for accurate hover detection
        const start = link.source;
        const end = link.target;
        if (typeof start !== "object" || typeof end !== "object") return;
        if (start.x == null || end.x == null) return;

        const dx = end.x - start.x;
        const dy = end.y - start.y;
        const distance = Math.sqrt(dx * dx + dy * dy);
        if (distance < 0.1) return;

        const laneCount = link.lane_count || 1;
        const laneIndex = link.lane_index || 0;
        const offset = getOffset(laneIndex, laneCount, distance);
        const nx = -dy / distance;
        const ny = dx / distance;

        ctx.strokeStyle = paintStyle;
        ctx.lineWidth = 4;
        ctx.beginPath();
        if (offset === 0) {
          ctx.moveTo(start.x, start.y);
          ctx.lineTo(end.x, end.y);
        } else {
          const cpx = (start.x + end.x) / 2 + nx * offset * CURVE_FACTOR;
          const cpy = (start.y + end.y) / 2 + ny * offset * CURVE_FACTOR;
          ctx.moveTo(start.x, start.y);
          ctx.quadraticCurveTo(cpx, cpy, end.x, end.y);
        }
        ctx.stroke();
      }}
      cooldownTicks={100}
      onNodeDrag={handleNodeDrag}
      onNodeDragEnd={handleNodeDragEnd}
      onEngineStop={handleEngineStop}
      onNodeHover={onNodeHover}
      onNodeClick={handleNodeClick}
      onLinkClick={onLinkClick}
      onLinkHover={onLinkHover}
      onRenderFramePost={onRenderFramePost}
      enableNodeDrag={true}
      enableZoomInteraction={true}
      enablePanInteraction={true}
      warmupTicks={50}
      d3VelocityDecay={0.5}
    />
  );
});

// ============================================
// PURE RENDERING ENGINE
// No API calls. No data transformation.
// No store-level filtering (that happens BEFORE data reaches here).
// Keeps: hover, highlight, pin, fullscreen, zoom, drag.
// ============================================
const CORRIDOR_COLOR = '#f59e0b'; // amber

const ForceGraphViewer = ({
  graphData: externalData = { nodes: [], edges: [] },
  corridors = [],
  highlightedPath = [],
  playbackHighlights = null, // Map<edgeKey, {intensity, color}> or null
  onNodeNavigate,
  onNodeHover: onNodeHoverExternal,
  centerNodeId = null,
  hideFullscreen = false,
  dimmed = false,
  activeRoute = null,
  cexRoutes = [],
  onCexRouteLock,
  cexUnlockTrigger = 0,
}) => {
  const forceRef = useRef(null);
  const containerRef = useRef(null);
  const hoveredNodeRef = useRef(null);
  const hoveredLinkRef = useRef(null);
  const mainNodeIdRef = useRef(null);
  const onNodeHoverExternalRef = useRef(null);
  useEffect(() => { onNodeHoverExternalRef.current = onNodeHoverExternal; }, [onNodeHoverExternal]);
  const cexRoutesRef = useRef(cexRoutes);
  useEffect(() => { cexRoutesRef.current = cexRoutes; }, [cexRoutes]);

  // Locked CEX route: Set of route indices that are "pinned" via double-click
  const [lockedCexRouteIndices, setLockedCexRouteIndices] = useState(null);
  const lockedCexRouteRef = useRef(null);
  useEffect(() => { lockedCexRouteRef.current = lockedCexRouteIndices; }, [lockedCexRouteIndices]);
  const onCexRouteLockRef = useRef(null);
  useEffect(() => { onCexRouteLockRef.current = onCexRouteLock; }, [onCexRouteLock]);
  // Clear locked route when CEX mode is deactivated
  useEffect(() => { if (!cexRoutes || !cexRoutes.length) setLockedCexRouteIndices(null); }, [cexRoutes]);
  // External unlock trigger (from parent X button)
  useEffect(() => { if (cexUnlockTrigger > 0) setLockedCexRouteIndices(null); }, [cexUnlockTrigger]);

  // Precomputed map: sorted segment key → Set<routeIndex> for fast lookup in drawLink
  const cexSegmentMapRef = useRef(new Map());
  useEffect(() => {
    const map = new Map();
    (cexRoutes || []).forEach((route, routeIdx) => {
      const path = route.path;
      if (!path || path.length < 2) return;
      for (let i = 0; i < path.length - 1; i++) {
        const segKey = [path[i], path[i + 1]].sort().join('|');
        if (!map.has(segKey)) map.set(segKey, new Set());
        map.get(segKey).add(routeIdx);
      }
    });
    cexSegmentMapRef.current = map;
  }, [cexRoutes]);

  // Per-pair direction info: segKey → { hasIncoming, hasOutgoing }
  const cexPairInfoRef = useRef(new Map());
  // Frame-level dedup: prevents drawing the same CEX pair multiple times per frame
  const drawnCexPairsRef = useRef(new Set());

  const [renderData, setRenderData] = useState({ nodes: [], links: [] });

  // Recompute per-pair direction info whenever renderData or cexRoutes change
  useEffect(() => {
    const segMap = cexSegmentMapRef.current;
    if (!segMap.size) { cexPairInfoRef.current = new Map(); return; }
    const pairInfo = new Map();
    for (const segKey of segMap.keys()) {
      pairInfo.set(segKey, { hasIncoming: false, hasOutgoing: false });
    }
    for (const link of (renderData.links || [])) {
      const s = typeof link.source === 'object' ? link.source.id : link.source;
      const t = typeof link.target === 'object' ? link.target.id : link.target;
      const segKey = [s, t].sort().join('|');
      const info = pairInfo.get(segKey);
      if (!info) continue;
      const dir = (link.direction || '').toLowerCase();
      if (dir === 'incoming') info.hasIncoming = true;
      else info.hasOutgoing = true;
    }
    for (const [, info] of pairInfo) {
      if (!info.hasIncoming && !info.hasOutgoing) {
        info.hasIncoming = true;
        info.hasOutgoing = true;
      }
    }
    cexPairInfoRef.current = pairInfo;
  }, [renderData.links, cexRoutes]);
  const [lockIcon, setLockIcon] = useState(null);
  const entityIconsRef = useRef(new Map()); // cached Image objects
  const [entityIconsReady, setEntityIconsReady] = useState(0); // triggers re-render when icons load
  const [hoveredLink, setHoveredLink] = useState(null);
  const [hoveredNode, setHoveredNode] = useState(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [pinnedNodes, setPinnedNodes] = useState(new Set());
  const [fsSize, setFsSize] = useState(() => ({
    w: typeof window !== "undefined" ? window.innerWidth : 800,
    h: typeof window !== "undefined" ? window.innerHeight : 600,
  }));

  const highlightedEdgeIds = useMemo(() => new Set(highlightedPath || []), [highlightedPath]);

  // Track the seed/main node for direction-based edge coloring
  useEffect(() => {
    mainNodeIdRef.current = centerNodeId || renderData.nodes[0]?.id || null;
  }, [centerNodeId, renderData]);

  // ============================================
  // PROCESS EXTERNAL DATA → FORCE GRAPH FORMAT
  // (layout, dedup, curve — this is rendering prep, NOT data logic)
  // ============================================
  useEffect(() => {
    if (!externalData || (!externalData.nodes?.length && !externalData.edges?.length)) {
      setRenderData({ nodes: [], links: [] });
      return;
    }

    const nodeMap = new Map();
    let mainNodeData = null;
    if (centerNodeId) mainNodeData = externalData.nodes.find(n => n.id === centerNodeId);
    if (!mainNodeData) mainNodeData = externalData.nodes[0];

    if (!mainNodeData) { setRenderData({ nodes: [], links: [] }); return; }

    nodeMap.set(mainNodeData.id, {
      id: mainNodeData.id,
      label: resolveNodeLabel(mainNodeData),
      fullName: (mainNodeData.label || '').replace(/_/g, ' '),
      type: 'main',
      nodeType: mainNodeData.type || 'wallet',
      chain: mainNodeData.chain,
      address: mainNodeData.address,
      ringColor: mainNodeData.ringColor || null,
      ringOpacity: mainNodeData.ringOpacity ?? 0,
      size: 5,
    });

    externalData.nodes.forEach(n => {
      if (nodeMap.has(n.id)) return;
      nodeMap.set(n.id, {
        id: n.id,
        label: resolveNodeLabel(n),
        fullName: (n.label || '').replace(/_/g, ' '),
        type: 'node',
        nodeType: n.type || 'wallet',
        chain: n.chain,
        address: n.address,
        ringColor: n.ringColor || null,
        ringOpacity: n.ringOpacity ?? 0,
        size: 5,
      });
    });

    const nodes = Array.from(nodeMap.values());
    const childNodes = nodes.slice(1);
    const spreadRadius = 180 + Math.max(0, childNodes.length * 5);
    const angleStep = childNodes.length > 0 ? (2 * Math.PI) / childNodes.length : 0;
    childNodes.forEach((node, idx) => {
      node.x = Math.cos(idx * angleStep) * spreadRadius;
      node.y = Math.sin(idx * angleStep) * spreadRadius;
    });

    const edgeSet = new Set();
    const links = [];
    externalData.edges.forEach(e => {
      const src = e.source || e.fromNodeId;
      const tgt = e.target || e.toNodeId;
      if (!nodeMap.has(src) || !nodeMap.has(tgt)) return;
      if (src === tgt) return;
      // Use unique edge ID — NO dedup by pair (multi-edge support)
      const edgeId = e.id || `${src}|${tgt}|${e.type || ''}|${e.lane_index ?? ''}`;
      if (edgeSet.has(edgeId)) return;
      edgeSet.add(edgeId);
      links.push({
        id: edgeId,
        source: src, target: tgt,
        direction: e.direction || 'neutral',
        edgeType: e.type || 'transfer',
        flowType: e.flowType || e.type || 'transfer',
        amountUsd: e.amountUsd, txHash: e.txHash,
        timestamp: e.timestamp, metadata: e.metadata || {},
        // Backend-provided lane geometry — use directly, no recomputation
        lane_index: e.lane_index ?? 0,
        lane_count: e.lane_count ?? 1,
        pair_key: e.pair_key || '',
        color: e.color || '#8a8a8a',
        curvature: e.curvature ?? 0,
        weight: e.weight || e.amountUsd || 0,
      });
    });

    setRenderData({ nodes, links });
  }, [externalData, centerNodeId]);

  // ============================================
  // FULLSCREEN
  // ============================================
  const toggleFullscreen = async () => {
    const el = containerRef.current;
    if (!el) { setIsFullscreen(s => !s); return; }
    const isNow = document.fullscreenElement === el || document.webkitFullscreenElement === el;
    try {
      if (!isNow) {
        if (el.requestFullscreen) await el.requestFullscreen();
        else if (el.webkitRequestFullscreen) await el.webkitRequestFullscreen();
      } else {
        if (document.exitFullscreen) await document.exitFullscreen();
        else if (document.webkitExitFullscreen) await document.webkitExitFullscreen();
      }
    } catch { setIsFullscreen(s => !s); }
  };

  useEffect(() => {
    const onFsChange = () => {
      const el = containerRef.current;
      if (!el) return;
      setIsFullscreen(Boolean(document.fullscreenElement === el || document.webkitFullscreenElement === el));
    };
    document.addEventListener("fullscreenchange", onFsChange);
    document.addEventListener("webkitfullscreenchange", onFsChange);
    return () => {
      document.removeEventListener("fullscreenchange", onFsChange);
      document.removeEventListener("webkitfullscreenchange", onFsChange);
    };
  }, []);

  useEffect(() => {
    if (!isFullscreen) return;
    const update = () => setFsSize({ w: window.innerWidth, h: window.innerHeight });
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, [isFullscreen]);

  // ============================================
  // ICON LOADING
  // ============================================
  useEffect(() => {
    const lockSvg = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>`;
    const blob = new Blob([lockSvg], { type: "image/svg+xml" });
    const url = URL.createObjectURL(blob);
    const img = new Image();
    img.onload = () => { setLockIcon(img); URL.revokeObjectURL(url); };
    img.src = url;
  }, []);

  // Preload entity logos
  useEffect(() => {
    const iconsMap = entityIconsRef.current;
    let loaded = 0;
    Object.entries(ENTITY_LOGO_URLS).forEach(([key, url]) => {
      if (iconsMap.has(key)) return;
      const img = new Image();
      img.crossOrigin = 'anonymous';
      img.onload = () => {
        iconsMap.set(key, img);
        loaded++;
        setEntityIconsReady(prev => prev + 1);
      };
      img.onerror = () => {
        // Mark as failed so we don't retry
        iconsMap.set(key, null);
      };
      img.src = url;
    });
  }, []);

  const isConnectedTo = useCallback((node, hoveredId, links) => {
    if (!hoveredId) return false;
    return links.some(link => {
      const s = typeof link.source === 'object' ? link.source.id : link.source;
      const t = typeof link.target === 'object' ? link.target.id : link.target;
      return (s === hoveredId && t === node.id) || (t === hoveredId && s === node.id);
    });
  }, []);

  // ============================================
  // NODE RENDERING — Circle with entity logo or text
  // ============================================
  const getEntityIcon = useCallback((label) => {
    if (!label) return null;
    const lower = label.toLowerCase().replace(/_/g, ' ');
    for (const [key, img] of entityIconsRef.current.entries()) {
      if (img && (lower === key || lower.startsWith(key + ' ') || lower.startsWith(key + '_') || lower.includes(key))) {
        return img;
      }
    }
    return null;
  }, []);

  const drawNode = useCallback((node, ctx) => {
    if (node.x === undefined || !isFinite(node.x)) return;
    const size = node.size || 5;
    const hovered = hoveredNodeRef.current;
    const isHovered = hovered && hovered.id === node.id;
    const isConnected = isConnectedTo(node, hovered?.id, renderData.links);
    const shouldDim = hovered && !isHovered && !isConnected && node.type !== 'main';

    // Route focus dimming: dim everything unless node is part of active route or CEX route
    const isRouteNode = activeRoute?.sample_path?.includes(node.id);
    const currentCexRoutes = cexRoutesRef.current || [];
    const isCexRouteNode = currentCexRoutes.length > 0 && currentCexRoutes.some(r => r.path?.includes(node.id));
    const routeDim = dimmed && !isRouteNode && !isCexRouteNode;

    ctx.save();
    if (routeDim) ctx.globalAlpha = 0.08;
    else if (shouldDim) ctx.globalAlpha = 0.3;
    if (node.type === "main") { ctx.shadowColor = MAIN_NODE_GLOW; ctx.shadowBlur = 14; }

    // Node circle
    ctx.beginPath();
    ctx.arc(node.x, node.y, size, 0, 2 * Math.PI);
    ctx.fillStyle = NODE_FILL;
    ctx.fill();
    ctx.strokeStyle = node.ringColor || NODE_STROKE;
    if (node.ringColor && node.ringOpacity > 0) {
      const prevAlpha = ctx.globalAlpha;
      if (routeDim) {
        ctx.globalAlpha = 0.08;
      } else if (shouldDim) {
        ctx.globalAlpha = 0.3 * node.ringOpacity;
      } else {
        ctx.globalAlpha = node.ringOpacity;
      }
      ctx.lineWidth = 0.2;
      ctx.stroke();
      ctx.globalAlpha = prevAlpha;
    } else {
      ctx.lineWidth = 0.65;
      ctx.stroke();
    }
    ctx.shadowBlur = 0;

    // Try to draw entity logo
    const cleanName = (node.fullName || node.label || '').replace(/_/g, ' ');
    const icon = getEntityIcon(cleanName);
    if (icon) {
      // Draw circular clipped logo
      ctx.save();
      ctx.beginPath();
      ctx.arc(node.x, node.y, size * 0.75, 0, 2 * Math.PI);
      ctx.clip();
      const iconSize = size * 1.5;
      ctx.drawImage(icon, node.x - iconSize / 2, node.y - iconSize / 2, iconSize, iconSize);
      ctx.restore();
    } else {
      // Text label — truncated to 4 chars from original name
      ctx.fillStyle = '#fff';
      ctx.font = `${size * 0.42}px Gilroy, sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(shortNodeLabel(cleanName), node.x, node.y);
    }

    // Green verification dot for known entities
    if (isVerifiedEntity(cleanName)) {
      const dotR = size * 0.18;
      ctx.beginPath();
      ctx.arc(node.x + size * 0.65, node.y - size * 0.65, dotR, 0, 2 * Math.PI);
      ctx.fillStyle = '#22c55e';
      ctx.fill();
      ctx.strokeStyle = NODE_FILL;
      ctx.lineWidth = 0.3;
      ctx.stroke();
    }

    // Pin icon
    if (node.fx !== undefined && node.fy !== undefined && lockIcon) {
      const ls = size * 0.7;
      ctx.drawImage(lockIcon, node.x - size * 0.7 - ls / 2, node.y - size * 0.7 - ls / 2, ls, ls);
    }
    ctx.restore();
  }, [lockIcon, renderData.links, isConnectedTo, getEntityIcon, entityIconsReady, dimmed, activeRoute]);

  // ============================================
  // EDGE RENDERING — Arkham-style distance-aware lane compression
  // distance ↓ → spread ↓ (lines compress into corridor)
  // distance ↑ → spread ↑ (but clamped to MAX_SPREAD)
  // Uses: lane_index, lane_count, direction (from backend)
  // Does NOT use backend curvature — computes dynamically from pixel distance
  // ============================================
  const drawLink = useCallback((link, ctx, globalScale) => {
    const start = link.source;
    const end = link.target;
    if (typeof start !== "object" || typeof end !== "object") return;
    if (start.x == null || end.x == null) return;

    ctx.save();

    // === 1. Distance between nodes ===
    const dx = end.x - start.x;
    const dy = end.y - start.y;
    const distance = Math.sqrt(dx * dx + dy * dy);
    if (distance < 0.1) { ctx.restore(); return; }

    // === 2. Lane geometry ===
    const laneCount = link.lane_count || 1;
    const laneIndex = link.lane_index || 0;

    // === 3. Distance-aware spread (Arkham: spread ∝ sqrt(distance) + clamp + compression) ===
    const offset = getOffset(laneIndex, laneCount, distance);

    // === 4. Perpendicular offset ===
    const nx = -dy / distance;
    const ny = dx / distance;

    // === 5. Control point with curve factor ===
    const cpx = (start.x + end.x) / 2 + nx * offset * CURVE_FACTOR;
    const cpy = (start.y + end.y) / 2 + ny * offset * CURVE_FACTOR;

    // === 6. Draw path ===
    ctx.beginPath();
    if (offset === 0) {
      ctx.moveTo(start.x, start.y);
      ctx.lineTo(end.x, end.y);
    } else {
      ctx.moveTo(start.x, start.y);
      ctx.quadraticCurveTo(cpx, cpy, end.x, end.y);
    }

    // === 7. Color from direction ===
    const sId = start.id;
    const eId = end.id;
    const dir = (link.direction || '').toLowerCase();

    // === 8. Прозрачность через globalAlpha (НЕ через rgba) ===
    const hovered = hoveredNodeRef.current;
    const isConnected = hovered && (sId === hovered.id || eId === hovered.id);
    const hasHover = !!hovered;
    const isPlaybackActive = playbackHighlights != null;
    const pbHighlight = isPlaybackActive
      ? (playbackHighlights.get(`${sId}->${eId}`) || playbackHighlights.get(`${eId}->${sId}`))
      : null;

    // Route focus: check if this edge is part of active route
    const isRouteEdge = activeRoute?.sample_path ? (() => {
      const sp = activeRoute.sample_path;
      for (let i = 0; i < sp.length - 1; i++) {
        if ((sp[i] === sId && sp[i + 1] === eId) || (sp[i] === eId && sp[i + 1] === sId)) return true;
      }
      return false;
    })() : false;

    // CEX Flow: ALL old edges dim when active (new overlay edges handle CEX routes)
    const currentCexRoutes = cexRoutesRef.current || [];
    const isCexFlowActive = currentCexRoutes.length > 0 && dimmed;

    let alpha = 0.65;
    if (isCexFlowActive) alpha = 0.04;  // CEX flow: dim ALL old edges
    else if (dimmed && !isRouteEdge) alpha = 0.04;
    else if (isPlaybackActive && !pbHighlight) alpha = 0.15;
    else if (pbHighlight) alpha = 1.0;
    else if (hasHover && isConnected) alpha = 1.0;
    else if (hasHover && !isConnected) alpha = 0.12;

    ctx.globalAlpha = alpha;

    // === 9. Edge colors — same green/red ===
    if (dir === 'incoming') {
      ctx.strokeStyle = '#34D399';
    } else {
      ctx.strokeStyle = '#EF4444';
    }

    ctx.lineWidth = Math.max(0.18, 0.65 / (globalScale || 1));

    ctx.stroke();
    ctx.restore();

    // === CEX Flow overlay: max 2 aggregated lines per node pair (1 green + 1 red) ===
    // Drawn in the same phase as regular links → under nodes (correct z-order)
    // Deduped per frame: only drawn once per unique pair
    if (isCexFlowActive) {
      const segKey = [sId, eId].sort().join('|');
      const routeIndices = cexSegmentMapRef.current.get(segKey);
      if (routeIndices && !drawnCexPairsRef.current.has(segKey)) {
        drawnCexPairsRef.current.add(segKey);

        const pairInfo = cexPairInfoRef.current.get(segKey) || { hasIncoming: true, hasOutgoing: true };
        const drawGreen = pairInfo.hasIncoming;
        const drawRed = pairInfo.hasOutgoing;
        const drawBoth = drawGreen && drawRed;
        const laneCount = drawBoth ? 2 : 1;

        // Hover/Lock-based dimming for CEX overlay (second-level dimming)
        let cexAlpha = 0.85;
        const locked = lockedCexRouteRef.current;
        if (locked) {
          // Locked mode: only locked route stays bright
          const inLocked = [...routeIndices].some(r => locked.has(r));
          if (!inLocked) cexAlpha = 0.06;
        } else {
          const hovLink = hoveredLinkRef.current;
          const hovNode = hoveredNodeRef.current;
          if (hovLink) {
            const hovSrc = typeof hovLink.source === 'object' ? hovLink.source.id : hovLink.source;
            const hovTgt = typeof hovLink.target === 'object' ? hovLink.target.id : hovLink.target;
            const hovSegKey = [hovSrc, hovTgt].sort().join('|');
            const hovRouteIndices = cexSegmentMapRef.current.get(hovSegKey);
            if (hovRouteIndices) {
              const shared = [...routeIndices].some(r => hovRouteIndices.has(r));
              if (!shared) cexAlpha = 0.08;
            }
          } else if (hovNode) {
            if (sId !== hovNode.id && eId !== hovNode.id) cexAlpha = 0.12;
          }
        }

        const cexLineWidth = Math.max(0.18, 0.65 / (globalScale || 1)) * 2;

        // CEX curvature: 1 line → straight, 2 lines → diverge visibly
        // Use fixed spread that scales with distance (like regular lane offsets but bigger)
        const cexSpread = drawBoth ? Math.max(8, distance * 0.04) : 0;

        if (drawGreen) {
          const off = drawBoth ? cexSpread : 0;
          const cx = (start.x + end.x) / 2 + nx * off * CURVE_FACTOR;
          const cy = (start.y + end.y) / 2 + ny * off * CURVE_FACTOR;
          ctx.save();
          ctx.beginPath();
          if (off === 0) { ctx.moveTo(start.x, start.y); ctx.lineTo(end.x, end.y); }
          else { ctx.moveTo(start.x, start.y); ctx.quadraticCurveTo(cx, cy, end.x, end.y); }
          ctx.strokeStyle = '#34D399';
          ctx.globalAlpha = cexAlpha;
          ctx.lineWidth = cexLineWidth;
          ctx.stroke();
          ctx.restore();
        }

        if (drawRed) {
          const off = drawBoth ? -cexSpread : 0;
          const cx = (start.x + end.x) / 2 + nx * off * CURVE_FACTOR;
          const cy = (start.y + end.y) / 2 + ny * off * CURVE_FACTOR;
          ctx.save();
          ctx.beginPath();
          if (off === 0) { ctx.moveTo(start.x, start.y); ctx.lineTo(end.x, end.y); }
          else { ctx.moveTo(start.x, start.y); ctx.quadraticCurveTo(cx, cy, end.x, end.y); }
          ctx.strokeStyle = '#EF4444';
          ctx.globalAlpha = cexAlpha;
          ctx.lineWidth = cexLineWidth;
          ctx.stroke();
          ctx.restore();
        }
      }
    }
  }, [playbackHighlights, dimmed, activeRoute]);

  // ============================================
  // ROUTE OVERLAY — bright polyline for active route
  // ============================================
  const drawRouteOverlay = useCallback((ctx) => {
    if (!activeRoute?.sample_path || activeRoute.sample_path.length < 2) return;
    if (!renderData.nodes || renderData.nodes.length === 0) return;

    const nodePos = new Map();
    renderData.nodes.forEach(n => {
      if (n.x !== undefined && n.y !== undefined) nodePos.set(n.id, n);
    });

    const path = activeRoute.sample_path;

    // Draw segments
    for (let i = 0; i < path.length - 1; i++) {
      const srcNode = nodePos.get(path[i]);
      const tgtNode = nodePos.get(path[i + 1]);
      if (!srcNode || !tgtNode) continue;

      const dx = tgtNode.x - srcNode.x;
      const dy = tgtNode.y - srcNode.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      const curve = Math.min(18, dist * 0.08);
      const mx = (srcNode.x + tgtNode.x) / 2;
      const my = (srcNode.y + tgtNode.y) / 2;
      const nx = -dy / dist;
      const ny = dx / dist;
      const cx = mx + nx * curve;
      const cy = my + ny * curve;

      // Glow
      ctx.save();
      ctx.beginPath();
      ctx.moveTo(srcNode.x, srcNode.y);
      ctx.quadraticCurveTo(cx, cy, tgtNode.x, tgtNode.y);
      ctx.strokeStyle = '#34D399';
      ctx.globalAlpha = 0.2;
      ctx.lineWidth = 8;
      ctx.stroke();
      ctx.restore();

      // Core line
      ctx.save();
      ctx.beginPath();
      ctx.moveTo(srcNode.x, srcNode.y);
      ctx.quadraticCurveTo(cx, cy, tgtNode.x, tgtNode.y);
      ctx.strokeStyle = '#34D399';
      ctx.globalAlpha = 0.95;
      ctx.lineWidth = 2.5;
      ctx.stroke();
      ctx.restore();

      // Arrow at midpoint
      const arrowX = (srcNode.x + cx + tgtNode.x) / 3;
      const arrowY = (srcNode.y + cy + tgtNode.y) / 3;
      const angle = Math.atan2(tgtNode.y - srcNode.y, tgtNode.x - srcNode.x);
      ctx.save();
      ctx.translate(arrowX, arrowY);
      ctx.rotate(angle);
      ctx.beginPath();
      ctx.moveTo(5, 0);
      ctx.lineTo(-3, -3);
      ctx.lineTo(-3, 3);
      ctx.closePath();
      ctx.fillStyle = '#34D399';
      ctx.globalAlpha = 0.9;
      ctx.fill();
      ctx.restore();
    }

    // Draw route node highlights (yellow rings)
    for (const nodeId of path) {
      const node = nodePos.get(nodeId);
      if (!node) continue;
      const r = (node.size || 5) + 3;

      ctx.save();
      ctx.beginPath();
      ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
      ctx.strokeStyle = '#FDE68A';
      ctx.globalAlpha = 0.9;
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.restore();
    }
  }, [activeRoute, renderData.nodes]);


  // ============================================
  // CORRIDOR OVERLAY — dashed amber lines for macro flows
  // ============================================
  const drawCorridorOverlay = useCallback((ctx) => {
    if (!corridors || corridors.length === 0) return;
    if (!renderData.nodes || renderData.nodes.length === 0) return;

    // Build node position lookup from rendered nodes
    const nodePos = new Map();
    renderData.nodes.forEach(n => {
      if (n.x !== undefined && n.y !== undefined) {
        nodePos.set(n.id, { x: n.x, y: n.y });
      }
    });

    corridors.forEach(corridor => {
      const srcPos = nodePos.get(corridor.source);
      const tgtPos = nodePos.get(corridor.target);
      if (!srcPos || !tgtPos) return;

      ctx.save();
      ctx.beginPath();
      ctx.setLineDash([6, 4]);
      ctx.moveTo(srcPos.x, srcPos.y);
      ctx.lineTo(tgtPos.x, tgtPos.y);
      ctx.strokeStyle = CORRIDOR_COLOR;
      ctx.lineWidth = 3;
      ctx.globalAlpha = 0.7;
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.restore();
    });
  }, [corridors, renderData.nodes]);

  // ============================================
  // CEX FLOW MISSING — draw overlay for segments not drawn by drawLink
  // (handles filtered edges that are part of CEX routes)
  // ============================================
  const drawCexFlowMissing = useCallback((ctx) => {
    const routes = cexRoutesRef.current || [];
    if (routes.length === 0 || !dimmed) return;
    const segMap = cexSegmentMapRef.current;
    if (!segMap.size) return;
    const drawnPairs = drawnCexPairsRef.current;
    const missingKeys = [];
    for (const segKey of segMap.keys()) {
      if (!drawnPairs.has(segKey)) missingKeys.push(segKey);
    }
    if (missingKeys.length === 0) return;

    const nodePos = new Map();
    renderData.nodes.forEach(n => {
      if (n.x !== undefined && n.y !== undefined) nodePos.set(n.id, n);
    });
    const globalScale = forceRef.current?.zoom?.() || 1;
    const cexLineWidth = Math.max(0.18, 0.65 / globalScale) * 2;
    const locked = lockedCexRouteRef.current;
    const hovLink = hoveredLinkRef.current;
    const hovNode = hoveredNodeRef.current;

    for (const segKey of missingKeys) {
      const [id1, id2] = segKey.split('|');
      const n1 = nodePos.get(id1);
      const n2 = nodePos.get(id2);
      if (!n1 || !n2) continue;
      const dx = n2.x - n1.x;
      const dy = n2.y - n1.y;
      const distance = Math.sqrt(dx * dx + dy * dy);
      if (distance < 0.1) continue;
      const nx = -dy / distance;
      const ny = dx / distance;
      const routeIndices = segMap.get(segKey);
      const pairInfo = cexPairInfoRef.current.get(segKey) || { hasIncoming: true, hasOutgoing: true };
      const drawGreen = pairInfo.hasIncoming;
      const drawRed = pairInfo.hasOutgoing;
      const drawBoth = drawGreen && drawRed;
      let cexAlpha = 0.85;
      if (locked) {
        const inLocked = [...routeIndices].some(r => locked.has(r));
        if (!inLocked) cexAlpha = 0.06;
      } else if (hovLink) {
        const hS = typeof hovLink.source === 'object' ? hovLink.source.id : hovLink.source;
        const hT = typeof hovLink.target === 'object' ? hovLink.target.id : hovLink.target;
        const hKey = [hS, hT].sort().join('|');
        const hRI = segMap.get(hKey);
        if (hRI && ![...routeIndices].some(r => hRI.has(r))) cexAlpha = 0.08;
      } else if (hovNode) {
        if (id1 !== hovNode.id && id2 !== hovNode.id) cexAlpha = 0.12;
      }
      const cexSpread = drawBoth ? Math.max(8, distance * 0.04) : 0;
      if (drawGreen) {
        const off = drawBoth ? cexSpread : 0;
        const cx = (n1.x + n2.x) / 2 + nx * off * CURVE_FACTOR;
        const cy = (n1.y + n2.y) / 2 + ny * off * CURVE_FACTOR;
        ctx.save(); ctx.beginPath();
        if (off === 0) { ctx.moveTo(n1.x, n1.y); ctx.lineTo(n2.x, n2.y); }
        else { ctx.moveTo(n1.x, n1.y); ctx.quadraticCurveTo(cx, cy, n2.x, n2.y); }
        ctx.strokeStyle = '#34D399'; ctx.globalAlpha = cexAlpha;
        ctx.lineWidth = cexLineWidth; ctx.stroke(); ctx.restore();
      }
      if (drawRed) {
        const off = drawBoth ? -cexSpread : 0;
        const cx = (n1.x + n2.x) / 2 + nx * off * CURVE_FACTOR;
        const cy = (n1.y + n2.y) / 2 + ny * off * CURVE_FACTOR;
        ctx.save(); ctx.beginPath();
        if (off === 0) { ctx.moveTo(n1.x, n1.y); ctx.lineTo(n2.x, n2.y); }
        else { ctx.moveTo(n1.x, n1.y); ctx.quadraticCurveTo(cx, cy, n2.x, n2.y); }
        ctx.strokeStyle = '#EF4444'; ctx.globalAlpha = cexAlpha;
        ctx.lineWidth = cexLineWidth; ctx.stroke(); ctx.restore();
      }
    }
  }, [dimmed, renderData.nodes]);

  // Enhanced drawLink that also renders corridor overlay
  const drawLinkWithCorridors = useCallback((link, ctx) => {
    drawLink(link, ctx);
    // Corridor overlay is drawn once after all links via onRenderFramePost
  }, [drawLink]);

  const handleNodeDrag = useCallback((node) => { if (node) { node.fx = node.x; node.fy = node.y; } }, []);
  const handleNodeDragEnd = useCallback((node) => { if (node) { node.fx = node.x; node.fy = node.y; } }, []);
  const handleEngineStop = useCallback(() => {
    if (forceRef.current?.d3Force) {
      forceRef.current.d3Force("charge")?.strength(-30);
      forceRef.current.d3Force("link")?.distance(60);
      forceRef.current.d3Force("center")?.strength(1.2);
    }
  }, []);

  const toggleNodePin = useCallback((node) => {
    if (pinnedNodes.has(node.id)) {
      node.fx = undefined; node.fy = undefined;
      setPinnedNodes(prev => { const next = new Set(prev); next.delete(node.id); return next; });
    } else {
      node.fx = node.x; node.fy = node.y;
      setPinnedNodes(prev => new Set(prev).add(node.id));
    }
    setRenderData(prev => ({ ...prev }));
  }, [pinnedNodes]);

  const handleNodeClick = useCallback((node, event) => {
    const nodeSize = node.size || 5;
    if (forceRef.current) {
      const gc = forceRef.current.screen2GraphCoords(event.offsetX, event.offsetY);
      const dist = Math.sqrt(Math.pow(gc.x - (node.x - nodeSize * 0.7), 2) + Math.pow(gc.y - (node.y - nodeSize * 0.7), 2));
      if (dist < nodeSize * 0.7 * 1.5) { toggleNodePin(node); return; }
    }
    if (onNodeNavigate && node.id) onNodeNavigate(node.id);
  }, [onNodeNavigate, toggleNodePin]);

  const effectiveWidth = isFullscreen ? fsSize.w : (typeof window !== "undefined" ? window.innerWidth : 800);
  const effectiveHeight = isFullscreen ? fsSize.h : (typeof window !== "undefined" ? window.innerHeight : 600);

  return (
    <div
      ref={containerRef}
      data-testid="force-graph-container"
      style={{
        position: isFullscreen ? "fixed" : "relative",
        width: isFullscreen ? "100vw" : "100%",
        height: isFullscreen ? "100vh" : "100%",
        top: isFullscreen ? 0 : "auto", left: isFullscreen ? 0 : "auto",
        zIndex: isFullscreen ? 9999 : "auto",
        backgroundColor: isFullscreen ? "#0a0e1a" : "transparent",
      }}
      onMouseMove={(e) => setMousePos({ x: e.clientX, y: e.clientY })}
    >
      {/* Fullscreen toggle */}
      {!hideFullscreen && (
        <button
          data-testid="graph-fullscreen-btn"
          onClick={toggleFullscreen}
          style={{
            position: "absolute", top: "20px", right: "20px", zIndex: 10,
            backgroundColor: "rgba(30, 41, 59, 0.8)", border: "1px solid rgba(148, 163, 184, 0.2)",
            borderRadius: "8px", padding: "9.5px 12px", color: "#f8fafc", cursor: "pointer",
            display: "flex", alignItems: "center", gap: "8px", fontSize: "14px", fontWeight: 500,
            transition: "all 0.2s ease", backdropFilter: "blur(10px)",
          }}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            {isFullscreen
              ? <path d="M8 3v3a2 2 0 0 1-2 2H3m18 0h-3a2 2 0 0 1-2-2V3m0 18v-3a2 2 0 0 1 2-2h3M3 16h3a2 2 0 0 1 2 2v3" />
              : <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3" />
            }
          </svg>
          <span>{isFullscreen ? 'Exit' : 'Fullscreen'}</span>
        </button>
      )}

      <GraphCanvas
        forceRef={forceRef}
        graphData={renderData}
        width={containerRef.current?.clientWidth || effectiveWidth}
        height={effectiveHeight}
        drawNode={drawNode}
        drawLink={drawLink}
        handleNodeDrag={handleNodeDrag}
        handleNodeDragEnd={handleNodeDragEnd}
        handleEngineStop={handleEngineStop}
        handleNodeClick={handleNodeClick}
        onLinkClick={useCallback((link) => {
          // Double-click on CEX route edge → toggle lock
          if (!link) return;
          const now = Date.now();
          const last = link.__lastCexClick || 0;
          link.__lastCexClick = now;
          if (now - last > 400) return;

          const sId = typeof link.source === 'object' ? link.source.id : link.source;
          const eId = typeof link.target === 'object' ? link.target.id : link.target;
          const segKey = [sId, eId].sort().join('|');
          const routeIndices = cexSegmentMapRef.current.get(segKey);
          if (!routeIndices) return;

          const currentLocked = lockedCexRouteRef.current;
          if (currentLocked) {
            const shared = [...routeIndices].some(r => currentLocked.has(r));
            if (shared) {
              setLockedCexRouteIndices(null);
              onCexRouteLockRef.current?.(null);
              return;
            }
          }
          setLockedCexRouteIndices(new Set(routeIndices));
          onCexRouteLockRef.current?.(new Set(routeIndices));
        }, [])}
        onRenderFramePost={useCallback((ctx) => {
          drawCexFlowMissing(ctx);
          drawnCexPairsRef.current.clear();
          drawCorridorOverlay(ctx);
          drawRouteOverlay(ctx);
        }, [drawCexFlowMissing, drawCorridorOverlay, drawRouteOverlay])}
        hasExternalHover={!!onNodeHoverExternal}
        onNodeHover={useCallback((node) => {
          document.body.style.cursor = node ? "pointer" : "default";
          hoveredNodeRef.current = node;
          setHoveredNode(node);
          onNodeHoverExternalRef.current?.(node);
        }, [])}
        onLinkHover={useCallback((link) => {
          hoveredLinkRef.current = link;
          setHoveredLink(link);
        }, [])}
      />

      {/* Node Tooltip — entity name, type, address with copy */}
      {hoveredNode && !onNodeHoverExternal && (
        <div style={{
          position: "fixed", left: mousePos.x + 12, top: mousePos.y + 12,
          backgroundColor: "rgba(15, 23, 42, 0.95)", border: "1px solid rgba(100, 116, 139, 0.3)",
          color: "white", padding: "8px 12px", borderRadius: "6px",
          fontSize: "12px", pointerEvents: "auto", zIndex: 1000, maxWidth: "320px",
        }}>
          <div style={{ fontWeight: 500, color: "#f1f5f9" }}>
            {(hoveredNode.fullName || hoveredNode.label || '').replace(/_/g, ' ')}
          </div>
          <div style={{ color: "#94a3b8", fontSize: "11px", textTransform: "capitalize" }}>
            {NODE_TYPES[hoveredNode.nodeType]?.label || hoveredNode.nodeType || 'Entity'}
            {hoveredNode.chain && hoveredNode.chain !== 'multi' && (
              <span style={{ marginLeft: "4px", color: "#64748b" }}>({hoveredNode.chain})</span>
            )}
          </div>
          {(() => {
            // Extract address from node
            const addr = hoveredNode.address || (() => {
              const parts = (hoveredNode.id || '').split(':');
              const mid = parts[1] || '';
              return mid.startsWith('0x') ? mid : null;
            })();
            if (!addr || !addr.startsWith('0x') || addr.length < 10) return null;
            const short = `${addr.slice(0, 6)}...${addr.slice(-4)}`;
            return (
              <div style={{ display: "flex", alignItems: "center", gap: "6px", marginTop: "4px" }}>
                <span style={{ color: "#64748b", fontSize: "11px", fontFamily: "'Gilroy', sans-serif" }}>{short}</span>
                <button
                  data-testid="copy-address-btn"
                  onClick={(e) => {
                    e.stopPropagation();
                    navigator.clipboard.writeText(addr).catch(() => {
                      const ta = document.createElement('textarea');
                      ta.value = addr; ta.style.position = 'fixed'; ta.style.opacity = '0';
                      document.body.appendChild(ta); ta.select(); document.execCommand('copy');
                      document.body.removeChild(ta);
                    });
                  }}
                  style={{ background: "none", border: "none", cursor: "pointer", color: "#64748b", padding: "2px", display: "flex", alignItems: "center", transition: "color 0.15s" }}
                  onMouseOver={(e) => e.currentTarget.style.color = '#fff'}
                  onMouseOut={(e) => e.currentTarget.style.color = '#64748b'}
                  title="Copy address"
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                </button>
              </div>
            );
          })()}
        </div>
      )}

      {/* Link Tooltip — shows for EACH edge individually with correct color */}
      {hoveredLink && !hoveredNode && (
        <div style={{
          position: "fixed", left: mousePos.x + 12, top: mousePos.y + 12,
          backgroundColor: "rgba(15, 23, 42, 0.95)", border: "1px solid rgba(100, 116, 139, 0.3)",
          color: "white", padding: "5px 8px", borderRadius: "4px",
          fontSize: "11px", pointerEvents: "none", zIndex: 1000,
        }}>
          <span style={{ color: hoveredLink.direction === 'incoming' ? '#34d399' : '#ef4444' }}>
            {hoveredLink.direction === 'incoming' ? 'Incoming' : 'Outgoing'} {hoveredLink.flowType || hoveredLink.edgeType || hoveredLink.type || 'transfer'}
          </span>
          {(hoveredLink.amountUsd > 0 || hoveredLink.volumeUsd > 0) && (
            <span style={{ color: "#94a3b8", marginLeft: "6px" }}>
              ${Number(hoveredLink.amountUsd || hoveredLink.volumeUsd || 0).toLocaleString()}
            </span>
          )}
          {hoveredLink.txCount > 0 && (
            <span style={{ color: "#64748b", marginLeft: "6px" }}>
              ({hoveredLink.txCount} tx)
            </span>
          )}
          <div style={{ color: "#475569", fontSize: "10px", marginTop: "2px" }}>
            Lane {(hoveredLink.lane_index ?? 0) + 1}/{hoveredLink.lane_count ?? 1}
          </div>
        </div>
      )}
    </div>
  );
};

export default ForceGraphViewer;
