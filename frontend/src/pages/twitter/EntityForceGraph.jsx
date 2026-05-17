import React, { useRef, useCallback, useState, useEffect, useMemo, memo } from "react";
import ForceGraph from "react-force-graph-2d";

const API_URL = process.env.REACT_APP_BACKEND_URL;

// ============================================
// MEMOIZED GRAPH CANVAS COMPONENT
// Isolates the heavy ForceGraph rendering from parent re-renders
// ============================================
const GraphCanvas = memo(function GraphCanvas({
  forceRef,
  graphData,
  width,
  height,
  drawNode,
  drawLink,
  handleNodeDrag,
  handleNodeDragEnd,
  handleEngineStop,
  handleNodeClick,
  onNodeHover,
  onLinkHover,
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
      nodeLabel={(node) => node.label}
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
      cooldownTicks={100}
      onNodeDrag={handleNodeDrag}
      onNodeDragEnd={handleNodeDragEnd}
      onEngineStop={handleEngineStop}
      onNodeHover={onNodeHover}
      onNodeClick={handleNodeClick}
      onLinkHover={onLinkHover}
      enableNodeDrag={true}
      enableZoomInteraction={true}
      enablePanInteraction={true}
      warmupTicks={50}
      d3VelocityDecay={0.5}
    />
  );
});

const ForceGraphViewer = ({ centerEntity = null }) => {
  const forceRef = useRef(null);
  const containerRef = useRef(null);
  
  // Use refs for hover state to avoid re-renders of GraphCanvas
  const hoveredNodeRef = useRef(null);
  const hoveredLinkRef = useRef(null);
  const mousePosRef = useRef({ x: 0, y: 0 });
  
  const [graphData, setGraphData] = useState({
    nodes: [],
    links: [],
  });
  const [cryptoIcons, setCryptoIcons] = useState({});
  const [lockIcon, setLockIcon] = useState(null);
  const [unlockIcon, setUnlockIcon] = useState(null);
  // State for tooltips (triggers re-render only for tooltip display)
  const [hoveredLink, setHoveredLink] = useState(null);
  const [hoveredNode, setHoveredNode] = useState(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const [currentMainNode, setCurrentMainNode] = useState(null);
  const [hopLevel, setHopLevel] = useState(1);
  const [navigationHistory, setNavigationHistory] = useState([]);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [fsSize, setFsSize] = useState(() => ({
    w: typeof window !== "undefined" ? window.innerWidth : 800,
    h: typeof window !== "undefined" ? window.innerHeight : 600,
  }));
  
  // Filter state
  const [showFilters, setShowFilters] = useState(false);
  const [entityFilters, setEntityFilters] = useState({
    project: true,
    fund: true,
    person: true,
    exchange: true,
    token: true,
    asset: true,
  });
  
  // Relation type filters
  const [relationFilters, setRelationFilters] = useState({
    invested_in: true,
    coinvested_with: true,
    founded: true,
    has_token: true,
    traded_on: true,
    works_at: true,
  });
  
  // G3: Scope filters (Graph Context Layer)
  const [scopeFilters, setScopeFilters] = useState({
    founder: true,
    investment: true,
    ecosystem: true,
    partnership: true,
    market: true,
    event: true,
    mention: false, // Off by default - usually noise
  });
  
  // Graph view mode: 'standard' or 'clustered'
  const [viewMode, setViewMode] = useState('standard');
  
  // Graph depth
  const [graphDepth, setGraphDepth] = useState(2);
  
  // Expanded clusters (for clustered mode)
  const [expandedClusters, setExpandedClusters] = useState(new Set());
  
  // Pinned nodes state
  const [pinnedNodes, setPinnedNodes] = useState(new Set());

  // Entity from prop or default
  const selectedEntity = centerEntity ? { name: centerEntity } : { name: "Binance" };
  const selectedTab = "on-chain";
  const filters = { persons: true, funds: true, projects: true };
  const onChainFilters = {
    centralizedExchanges: true,
    depositAddresses: true,
    individualsAndFunds: true,
    decentralizedExchanges: true,
    lending: true,
    misc: true,
    uncategorized: true,
    all: true,
  };

  const toggleFullscreen = async () => {
    const el = containerRef.current;
    if (!el || typeof document === "undefined") {
      setIsFullscreen((s) => !s);
      return;
    }

    const isNowFullscreen =
      document.fullscreenElement === el ||
      document.webkitFullscreenElement === el ||
      document.mozFullScreenElement === el ||
      document.msFullscreenElement === el;

    try {
      if (!isNowFullscreen) {
        if (el.requestFullscreen) await el.requestFullscreen();
        else if (el.webkitRequestFullscreen) await el.webkitRequestFullscreen();
        else if (el.mozRequestFullScreen) await el.mozRequestFullScreen();
        else if (el.msRequestFullscreen) await el.msRequestFullscreen();
      } else {
        if (document.exitFullscreen) await document.exitFullscreen();
        else if (document.webkitExitFullscreen) await document.webkitExitFullscreen();
        else if (document.mozCancelFullScreen) await document.mozCancelFullScreen();
        else if (document.msExitFullscreen) await document.msExitFullscreen();
      }
    } catch (err) {
      setIsFullscreen((s) => !s);
    }
  };

  useEffect(() => {
    const onFsChange = () => {
      const el = containerRef.current;
      if (!el || typeof document === "undefined") return;

      const isNowFullscreen =
        document.fullscreenElement === el ||
        document.webkitFullscreenElement === el ||
        document.mozFullScreenElement === el ||
        document.msFullscreenElement === el;

      setIsFullscreen(Boolean(isNowFullscreen));
    };

    document.addEventListener("fullscreenchange", onFsChange);
    document.addEventListener("webkitfullscreenchange", onFsChange);
    document.addEventListener("mozfullscreenchange", onFsChange);
    document.addEventListener("MSFullscreenChange", onFsChange);

    return () => {
      document.removeEventListener("fullscreenchange", onFsChange);
      document.removeEventListener("webkitfullscreenchange", onFsChange);
      document.removeEventListener("mozfullscreenchange", onFsChange);
      document.removeEventListener("MSFullscreenChange", onFsChange);
    };
  }, []);

  useEffect(() => {
    if (!isFullscreen) return;

    const update = () =>
      setFsSize({ w: window.innerWidth, h: window.innerHeight });

    update();

    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, [isFullscreen]);


  useEffect(() => {
    const lockSvg = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>`;
    const lockBlob = new Blob([lockSvg], { type: "image/svg+xml" });
    const lockUrl = URL.createObjectURL(lockBlob);
    const lockImg = new Image();
    lockImg.onload = () => { setLockIcon(lockImg); URL.revokeObjectURL(lockUrl); };
    lockImg.src = lockUrl;
    
    const unlockSvg = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#64748b" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 9.9-1"/></svg>`;
    const unlockBlob = new Blob([unlockSvg], { type: "image/svg+xml" });
    const unlockUrl = URL.createObjectURL(unlockBlob);
    const unlockImg = new Image();
    unlockImg.onload = () => { setUnlockIcon(unlockImg); URL.revokeObjectURL(unlockUrl); };
    unlockImg.src = unlockUrl;
  }, []);

  useEffect(() => {
    const loadCryptoIcon = (name, ticker) => {
      const img = new Image();
      img.crossOrigin = "anonymous";
      img.src =
        window.location.origin +
        `/static/crypto-icons/${ticker.toLowerCase()}.svg`;
      img.onload = () => {
        setCryptoIcons((prev) => ({ ...prev, [name]: img }));
      };
      img.style.width = "100%";
      img.style.height = "100%";
      img.onerror = () => {
        const fallbackImg = new Image();
        fallbackImg.crossOrigin = "anonymous";
        fallbackImg.src = `${window.location.origin}/static/crypto-icons/${ticker.toLowerCase()}.svg`;
        fallbackImg.onload = () => {
          setCryptoIcons((prev) => ({ ...prev, [name]: fallbackImg }));
        };
      };
    };

    loadCryptoIcon("Binance", "binance");
    loadCryptoIcon("Gate.io", "gate");
    loadCryptoIcon("Bitcoin", "btc");
    loadCryptoIcon("Coinbase", "coinbase");
    loadCryptoIcon("Ethereum", "eth");
    loadCryptoIcon("BNB", "bnb");
    loadCryptoIcon("Solana", "sol");
  }, []);

  useEffect(() => {
    // Only fetch graph data when centerEntity is provided
    if (!centerEntity) {
      setGraphData({ nodes: [], links: [] });
      setLoading(false);
      return;
    }
    
    const fetchGraphData = async () => {
      setLoading(true);
      try {
        const url = `${API_URL}/api/entity-graph/network?limit_nodes=150&limit_edges=400&depth=2&node_id=${centerEntity}`;
        
        const response = await fetch(url);
        if (!response.ok) throw new Error('Failed to fetch graph');
        
        const data = await response.json();
        
        // ========================================
        // DEDUPLICATION & SANITIZATION
        // ========================================
        
        // Deduplicate nodes by canonical ID
        const nodeMap = new Map();
        
        // Find main node — centerEntity is always provided
        let mainNodeData = data.nodes.find(n => n.id === centerEntity) || data.nodes[0];
        
        if (!mainNodeData) {
          setGraphData({ nodes: [], links: [] });
          setLoading(false);
          return;
        }
        
        // Add main node first
        const mainNode = {
          id: mainNodeData.id,
          label: mainNodeData.label,
          fullName: mainNodeData.label,
          type: "main",
          size: 5,
        };
        nodeMap.set(mainNodeData.id, mainNode);
        
        // Add other nodes (deduplicated by ID)
        data.nodes.forEach((apiNode) => {
          if (nodeMap.has(apiNode.id)) return; // Skip duplicates
          
          const node = {
            id: apiNode.id,
            label: apiNode.label.slice(0, 12) + (apiNode.label.length > 12 ? '...' : ''),
            fullName: apiNode.label, // Store full name for tooltip
            type: "lock",
            size: 5,
          };
          nodeMap.set(apiNode.id, node);
        });
        
        const nodes = Array.from(nodeMap.values());
        
        // Position nodes in circular layout around main node
        const childNodes = nodes.slice(1);
        const spreadRadius = 180 + Math.max(0, childNodes.length * 5);
        const angleStep = childNodes.length > 0 ? (2 * Math.PI) / childNodes.length : 0;
        childNodes.forEach((node, idx) => {
          node.x = Math.cos(idx * angleStep) * spreadRadius;
          node.y = Math.sin(idx * angleStep) * spreadRadius;
        });
        
        // Deduplicate edges
        const edgeSet = new Set();
        const links = [];
        
        data.edges.forEach(edge => {
          // Skip if source or target not in nodeMap
          if (!nodeMap.has(edge.source) || !nodeMap.has(edge.target)) return;
          
          // Skip self-loops
          if (edge.source === edge.target) return;
          
          // Deduplicate by source-target-relation
          const edgeKey = `${edge.source}|${edge.target}|${edge.relation}`;
          if (edgeSet.has(edgeKey)) return;
          edgeSet.add(edgeKey);
          
          const value = edge.value !== undefined ? edge.value : (Math.random() * 200 - 100);
          links.push({ 
            source: edge.source, 
            target: edge.target, 
            value,
            metadata: edge.metadata || {},
            relation: edge.relation || 'related_to'
          });
        });
        
        // Process links for curved lines (multiple connections between same pair)
        const linkMap = new Map();
        const processedLinks = links.map((link) => {
          const key = [link.source, link.target].sort().join("-");
          const count = linkMap.get(key) || 0;
          linkMap.set(key, count + 1);
          return { ...link, connectionIndex: count };
        });

        const finalLinks = processedLinks.map((link) => {
          const key = [link.source, link.target].sort().join("-");
          return { ...link, total: linkMap.get(key) };
        });
        
        setGraphData({ nodes, links: finalLinks });
        setCurrentMainNode(mainNode);
        setHopLevel(1);
        setNavigationHistory([mainNode]);
        
      } catch (err) {
        console.error('[GraphViewer] API fetch failed:', err);
        setGraphData({ nodes: [], links: [] });
      } finally {
        setLoading(false);
      }
    };
    
    fetchGraphData();
  }, [centerEntity, selectedEntity.name]);

  // Zoom to fit after graph loads or view mode changes
  useEffect(() => {
    if (!loading && graphData.nodes.length > 0 && forceRef.current) {
      const timer = setTimeout(() => {
        forceRef.current?.zoomToFit?.(400, 40);
      }, 1500);
      return () => clearTimeout(timer);
    }
  }, [loading, graphData.nodes.length, viewMode]);

  // Get color by entity type
  const getEntityColor = (nodeId) => {
    if (!nodeId || typeof nodeId !== 'string') return '#64748b';
    const type = nodeId.split(':')[0];
    const colors = {
      project: '#3b82f6',
      fund: '#10b981',
      person: '#f59e0b',
      exchange: '#ef4444',
      token: '#8b5cf6',
      asset: '#64748b',
      cluster: '#6366f1',
    };
    return colors[type] || '#64748b';
  };

  // Check if node is connected to hovered node (uses ref for performance)
  const isConnectedToHoveredRef = useCallback((node, hoveredNodeId, links) => {
    if (!hoveredNodeId) return false;
    return links.some(link => {
      const sourceId = typeof link.source === 'object' ? link.source.id : link.source;
      const targetId = typeof link.target === 'object' ? link.target.id : link.target;
      return (sourceId === hoveredNodeId && targetId === node.id) ||
             (targetId === hoveredNodeId && sourceId === node.id);
    });
  }, []);

  // ============================================
  // ORIGINAL STYLE NODE RENDERING
  // Gray nodes with labels inside + colored lines only
  // ============================================
  const drawNode = useCallback(
    (node, ctx, globalScale) => {
      if (node.x === undefined || node.y === undefined || !isFinite(node.x) || !isFinite(node.y)) {
        return;
      }
      
      const size = node.size || 5;
      
      const currentHoveredNode = hoveredNodeRef.current;
      const isHovered = currentHoveredNode && currentHoveredNode.id === node.id;
      const isConnected = isConnectedToHoveredRef(node, currentHoveredNode?.id, graphData.links);
      const shouldDim = currentHoveredNode && !isHovered && !isConnected && node.type !== 'main';
      
      ctx.save();
      
      if (shouldDim) {
        ctx.globalAlpha = 0.3;
      }
      
      // Main node glow only
      if (node.type === "main") {
        ctx.shadowColor = "#3b82f6";
        ctx.shadowBlur = 20;
      }
      
      // Draw circle - ORIGINAL GRAY COLOR with subtle stroke
      ctx.beginPath();
      ctx.arc(node.x, node.y, size, 0, 2 * Math.PI);
      ctx.fillStyle = "#2b2b2b";
      ctx.fill();
      ctx.strokeStyle = "#8a8a8a";
      ctx.lineWidth = 0.5;
      ctx.stroke();
      
      ctx.shadowBlur = 0;
      
      // Label inside node - ORIGINAL STYLE
      ctx.fillStyle = "#fff";
      ctx.font = `2px Inter, sans-serif`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(node.label || '', node.x, node.y);
      
      // Lock icon for pinned nodes
      if (node.fx !== undefined && node.fy !== undefined && lockIcon) {
        const lockSize = size * 0.7;
        const lockX = node.x - size * 0.7;
        const lockY = node.y - size * 0.7;
        ctx.drawImage(lockIcon, lockX - lockSize / 2, lockY - lockSize / 2, lockSize, lockSize);
      }

      ctx.restore();
    },
    [lockIcon, graphData.links, isConnectedToHoveredRef]
  );

  // ============================================
  // MINIMAL ARKHAM-STYLE EDGE RENDERING
  // Colors only on edges - this is where information is
  // ============================================
  const drawLink = useCallback(
    (link, ctx, globalScale) => {
      const start = link.source;
      const end = link.target;

      if (typeof start !== "object" || typeof end !== "object") return;
      
      const startId = typeof start === 'object' ? start.id : start;
      const endId = typeof end === 'object' ? end.id : end;
      const currentHoveredNode = hoveredNodeRef.current;
      const isHoveredLink = currentHoveredNode && (startId === currentHoveredNode.id || endId === currentHoveredNode.id);
      const shouldDim = currentHoveredNode && !isHoveredLink;

      ctx.save();
      
      // Focus mode dimming
      if (shouldDim) {
        ctx.globalAlpha = 0.1;
      }
      
      ctx.beginPath();

      const isMultiple = link.total && link.total > 1;

      if (!isMultiple || link.connectionIndex === 0) {
        ctx.moveTo(start.x, start.y);
        ctx.lineTo(end.x, end.y);
      } else {
        const dx = end.x - start.x;
        const dy = end.y - start.y;
        const distance = Math.sqrt(dx * dx + dy * dy) || 1;
        const side = link.connectionIndex % 2 === 1 ? 1 : -1;
        const curveMultiplier = Math.ceil(link.connectionIndex / 2);
        const curveOffset = side * curveMultiplier;
        const midX = (start.x + end.x) / 2;
        const midY = (start.y + end.y) / 2;
        const normalX = -dy / distance;
        const normalY = dx / distance;
        const controlX = midX + normalX * curveOffset;
        const controlY = midY + normalY * curveOffset;
        ctx.moveTo(start.x, start.y);
        ctx.quadraticCurveTo(controlX, controlY, end.x, end.y);
      }

      // Edge color by relation type - THIS IS WHERE COLOR GOES
      const relationColor = getRelationColor(link.relation);
      
      if (isHoveredLink) {
        ctx.strokeStyle = relationColor;
        ctx.lineWidth = 0.6;
        ctx.globalAlpha = 0.55;
      } else {
        ctx.strokeStyle = relationColor;
        ctx.lineWidth = 0.5;
        ctx.globalAlpha = 0.5;
      }

      ctx.stroke();
      ctx.restore();
    },
    []
  );
  
  // Relation colors - the ONLY place where color is used
  function getRelationColor(relation) {
    const colors = {
      invested_in: '#2ecc71',      // green
      coinvested_with: '#3498db',  // blue
      founded: '#f39c12',          // orange
      founded_by: '#f39c12',
      partnered_with: '#9b59b6',   // purple
      advisor: '#e67e22',
      advisor_to: '#e67e22',
      has_token: '#9b59b6',
      traded_on: '#e74c3c',
      works_at: '#1abc9c',
    };
    return colors[relation] || '#6c7480'; // default grey
  }

  const handleNodeDrag = useCallback((node) => {
    if (node) {
      node.fx = node.x;
      node.fy = node.y;
    }
  }, []);

  const handleNodeDragEnd = useCallback((node) => {
    if (node) {
      node.fx = node.x;
      node.fy = node.y;
    }
  }, []);

  const handleEngineStop = useCallback(() => {
    if (forceRef.current?.d3Force) {
      forceRef.current.d3Force("charge")?.strength(-30);
      forceRef.current.d3Force("link")?.distance(60);
      forceRef.current.d3Force("center")?.strength(1.2);
    }
  }, []);

  // Fetch and load graph for a given entity
  const loadEntityGraph = useCallback(async (entityId) => {
    setLoading(true);
    try {
      const [type, id] = entityId.split(':');
      if (!type || !id) return;
      
      const url = `${API_URL}/api/entity-graph/network?limit_nodes=150&limit_edges=400&depth=${graphDepth}&node_id=${entityId}`;
      const response = await fetch(url);
      if (!response.ok) throw new Error('Failed to fetch graph');
      
      const data = await response.json();
      
      // Find main node
      const mainNodeData = data.nodes.find(n => n.id === entityId) || data.nodes[0];
      if (!mainNodeData) {
        setGraphData({ nodes: [], links: [] });
        return;
      }
      
      // Count edges for each node (for size calculation)
      const edgeCounts = {};
      data.edges.forEach(edge => {
        edgeCounts[edge.source] = (edgeCounts[edge.source] || 0) + 1;
        edgeCounts[edge.target] = (edgeCounts[edge.target] || 0) + 1;
      });
      
      // Deduplicate nodes by ID
      const nodeMap = new Map();
      
      // Add main node first
      const mainNode = {
        id: mainNodeData.id,
        label: mainNodeData.label,
        fullName: mainNodeData.label,
        type: "main",
        size: 5,
        edgeCount: edgeCounts[mainNodeData.id] || 0,
      };
      nodeMap.set(mainNodeData.id, mainNode);
      
      // Add other nodes (deduplicated)
      data.nodes.forEach((apiNode) => {
        if (nodeMap.has(apiNode.id)) return; // Skip duplicates
        
        const node = {
          id: apiNode.id,
          label: apiNode.label?.slice(0, 12) + (apiNode.label?.length > 12 ? '...' : ''),
          fullName: apiNode.label,
          type: "lock",
          size: 5,
          edgeCount: edgeCounts[apiNode.id] || 0,
        };
        nodeMap.set(apiNode.id, node);
      });
      
      const nodes = Array.from(nodeMap.values());
      
      // Position nodes in circular layout around main node
      const childNodes = nodes.slice(1);
      const spreadRadius = 180 + Math.max(0, childNodes.length * 5);
      const angleStep = childNodes.length > 0 ? (2 * Math.PI) / childNodes.length : 0;
      childNodes.forEach((node, idx) => {
        node.x = Math.cos(idx * angleStep) * spreadRadius;
        node.y = Math.sin(idx * angleStep) * spreadRadius;
      });
      
      // Deduplicate edges
      const edgeSet = new Set();
      const links = [];
      
      data.edges.forEach(edge => {
        // Skip if source or target not in nodeMap
        if (!nodeMap.has(edge.source) || !nodeMap.has(edge.target)) return;
        
        // Skip self-loops
        if (edge.source === edge.target) return;
        
        // Deduplicate edges by source-target-relation
        const edgeKey = `${edge.source}|${edge.target}|${edge.relation}`;
        if (edgeSet.has(edgeKey)) return;
        edgeSet.add(edgeKey);
        
        const value = edge.value !== undefined ? edge.value : (Math.random() * 200 - 100);
        links.push({ 
          source: edge.source, 
          target: edge.target, 
          value,
          metadata: edge.metadata || {},
          relation: edge.relation || 'related_to'
        });
      });
      
      // Process links for curved lines (multiple connections between same nodes)
      const linkMap = new Map();
      const processedLinks = links.map((link) => {
        const key = [link.source, link.target].sort().join("-");
        const count = linkMap.get(key) || 0;
        linkMap.set(key, count + 1);
        return { ...link, connectionIndex: count };
      });

      const finalLinks = processedLinks.map((link) => {
        const key = [link.source, link.target].sort().join("-");
        return { ...link, total: linkMap.get(key) };
      });
      
      setGraphData({ nodes, links: finalLinks });
      setCurrentMainNode(mainNode);
      setNavigationHistory(prev => [...prev, mainNode]);
      
    } catch (err) {
      console.error('[GraphViewer] Failed to load entity graph:', err);
    } finally {
      setLoading(false);
    }
  }, [graphDepth]);

  // Toggle pin state for a node
  const toggleNodePin = useCallback((node) => {
    if (pinnedNodes.has(node.id)) {
      // Unpin - remove fixed position
      node.fx = undefined;
      node.fy = undefined;
      setPinnedNodes(prev => {
        const next = new Set(prev);
        next.delete(node.id);
        return next;
      });
    } else {
      // Pin - fix position
      node.fx = node.x;
      node.fy = node.y;
      setPinnedNodes(prev => new Set(prev).add(node.id));
    }
    // Trigger re-render
    setGraphData(prev => ({ ...prev }));
  }, [pinnedNodes]);

  const handleNodeClick = useCallback(
    (node, event) => {
      // Handle cluster node click - expand/collapse
      if (node.type === 'cluster' && node.clusterType) {
        setExpandedClusters(prev => {
          const next = new Set(prev);
          if (next.has(node.clusterType)) {
            next.delete(node.clusterType);
          } else {
            next.add(node.clusterType);
          }
          return next;
        });
        return;
      }
      
      // Check if click was on lock icon area
      const nodeSize = node.size || 5;
      const lockSize = nodeSize * 0.7;
      const lockCenterX = node.x - nodeSize * 0.7;
      const lockCenterY = node.y - nodeSize * 0.7;
      
      // Get click position in graph coordinates
      if (forceRef.current) {
        const graphCoords = forceRef.current.screen2GraphCoords(event.offsetX, event.offsetY);
        const distToLock = Math.sqrt(
          Math.pow(graphCoords.x - lockCenterX, 2) + 
          Math.pow(graphCoords.y - lockCenterY, 2)
        );
        
        // If clicked on lock icon area, toggle pin
        if (distToLock < lockSize * 1.5) {
          toggleNodePin(node);
          return;
        }
      }
      
      // Skip clicking on the current main node
      if (node.type === "main") return;
      
      // For any clickable node, load its real graph data
      if (node.id) {
        loadEntityGraph(node.id);
      }
    },
    [loadEntityGraph, toggleNodePin]
  );

  const effectiveWidth = isFullscreen
    ? fsSize.w
    : typeof window !== "undefined"
    ? window.innerWidth
    : 800;
  const effectiveHeight = isFullscreen
    ? fsSize.h
    : typeof window !== "undefined"
    ? window.innerHeight
    : 600;

  // Apply filters to graph data + Clustered mode
  const filteredGraphData = useMemo(() => {
    // Get entity type from node id (e.g., "project:bitcoin" -> "project")
    const getEntityType = (nodeId) => {
      if (!nodeId || typeof nodeId !== 'string') return 'unknown';
      const parts = nodeId.split(':');
      return parts[0] || 'unknown';
    };
    
    // Find main node
    const mainNode = graphData.nodes.find(n => n.type === 'main');
    const mainNodeId = mainNode?.id;
    
    // Filter nodes based on entity filters (always keep main node)
    let filteredNodes = graphData.nodes.filter(node => {
      if (node.type === 'main') return true;
      if (node.type === 'cluster') return true;
      const entityType = getEntityType(node.id);
      return entityFilters[entityType] !== false;
    });
    
    // CLUSTERED MODE: Group neighbors by type
    if (viewMode === 'clustered' && mainNode) {
      // Group non-main nodes by entity type
      const nodesByType = {};
      const mainNeighborIds = new Set();
      
      // Find direct neighbors of main node
      graphData.links.forEach(link => {
        const sourceId = typeof link.source === 'object' ? link.source.id : link.source;
        const targetId = typeof link.target === 'object' ? link.target.id : link.target;
        if (sourceId === mainNodeId) mainNeighborIds.add(targetId);
        if (targetId === mainNodeId) mainNeighborIds.add(sourceId);
      });
      
      // Group neighbors by type
      filteredNodes.forEach(node => {
        if (node.type === 'main') return;
        if (!mainNeighborIds.has(node.id)) return; // Only group direct neighbors
        
        const entityType = getEntityType(node.id);
        if (!entityFilters[entityType]) return;
        
        if (!nodesByType[entityType]) {
          nodesByType[entityType] = [];
        }
        nodesByType[entityType].push(node);
      });
      
      // Check which clusters are expanded
      const clusterNodes = [];
      const clusterLinks = [];
      
      Object.entries(nodesByType).forEach(([type, nodes]) => {
        const clusterId = `cluster:${type}`;
        const isExpanded = expandedClusters.has(type);
        
        if (isExpanded) {
          // Show individual nodes
          nodes.forEach(node => {
            clusterNodes.push(node);
            // Add link from main to each node
            const existingLink = graphData.links.find(l => {
              const src = typeof l.source === 'object' ? l.source.id : l.source;
              const tgt = typeof l.target === 'object' ? l.target.id : l.target;
              return (src === mainNodeId && tgt === node.id) || (tgt === mainNodeId && src === node.id);
            });
            if (existingLink) {
              clusterLinks.push(existingLink);
            }
          });
        } else {
                  // Show cluster node - SAME SIZE as all other nodes
          const clusterNode = {
            id: clusterId,
            label: `${type.charAt(0).toUpperCase() + type.slice(1)}s (${nodes.length})`,
            fullName: `${type.charAt(0).toUpperCase() + type.slice(1)}s (${nodes.length})`,
            type: 'cluster',
            clusterType: type,
            size: 5,
            edgeCount: nodes.length,
            childNodes: nodes.map(n => n.id),
            childNames: nodes.map(n => n.fullName || n.label).slice(0, 8), // Store names for tooltip (max 8)
            totalChildren: nodes.length,
          };
          clusterNodes.push(clusterNode);
          
          // Add link from main to cluster
          clusterLinks.push({
            source: mainNodeId,
            target: clusterId,
            relation: 'contains',
            value: nodes.length,
          });
        }
      });
      
      // Return clustered data
      return {
        nodes: [mainNode, ...clusterNodes],
        links: clusterLinks,
      };
    }
    
    // STANDARD MODE: Normal filtering
    const visibleNodeIds = new Set(filteredNodes.map(n => n.id));
    
    const filteredLinks = graphData.links.filter(link => {
      const sourceId = typeof link.source === 'object' ? link.source.id : link.source;
      const targetId = typeof link.target === 'object' ? link.target.id : link.target;
      
      if (!visibleNodeIds.has(sourceId) || !visibleNodeIds.has(targetId)) return false;
      
      const relation = link.relation || 'related_to';
      if (relationFilters[relation] === false) return false;
      
      // G3: Scope filter
      const scope = link.scope || 'other';
      if (scopeFilters[scope] === false) return false;
      
      return true;
    });
    
    return { nodes: filteredNodes, links: filteredLinks };
  }, [graphData, entityFilters, relationFilters, scopeFilters, viewMode, expandedClusters]);

  return (
    <div
      ref={containerRef}
      data-testid="force-graph-container"
      style={{
        position: isFullscreen ? "fixed" : "relative",
        width: isFullscreen ? "100vw" : "100%",
        height: isFullscreen ? "100vh" : "100%",
        top: isFullscreen ? 0 : "auto",
        left: isFullscreen ? 0 : "auto",
        zIndex: isFullscreen ? 9999 : "auto",
        backgroundColor: isFullscreen ? "#0a0e1a" : "transparent",
      }}
      onMouseMove={(e) => setMousePos({ x: e.clientX, y: e.clientY })}
    >
      {/* Fullscreen toggle button */}
      <button
        data-testid="graph-fullscreen-btn"
        onClick={toggleFullscreen}
        style={{
          position: "absolute",
          top: "20px",
          right: "20px",
          zIndex: 30,
          backgroundColor: "rgba(30, 41, 59, 0.8)",
          border: "1px solid rgba(148, 163, 184, 0.2)",
          borderRadius: "8px",
          padding: "9.5px 12px",
          color: "#f8fafc",
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          gap: "8px",
          fontSize: "14px",
          fontWeight: 500,
          transition: "all 0.2s ease",
          backdropFilter: "blur(10px)",
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.backgroundColor = "rgba(30, 41, 59, 1)";
          e.currentTarget.style.borderColor = "rgba(148, 163, 184, 0.4)";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.backgroundColor = "rgba(30, 41, 59, 0.8)";
          e.currentTarget.style.borderColor = "rgba(148, 163, 184, 0.2)";
        }}
      >
        {isFullscreen ? (
          <>
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M8 3v3a2 2 0 0 1-2 2H3m18 0h-3a2 2 0 0 1-2-2V3m0 18v-3a2 2 0 0 1 2-2h3M3 16h3a2 2 0 0 1 2 2v3" />
            </svg>
            <span>Exit Fullscreen</span>
          </>
        ) : (
          <>
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3" />
            </svg>
            <span>Fullscreen</span>
          </>
        )}
      </button>
      
      {/* Filter Button — positioned left of fullscreen button */}
      <div style={{ position: "absolute", top: "20px", right: isFullscreen ? "175px" : "145px", zIndex: 20 }}>
        <button
          data-testid="graph-filter-btn"
          onClick={() => setShowFilters(!showFilters)}
          style={{
            backgroundColor: showFilters ? "rgba(139, 92, 246, 0.8)" : "rgba(30, 41, 59, 0.8)",
            border: "1px solid rgba(148, 163, 184, 0.2)",
            borderRadius: "8px",
            padding: "9.5px 12px",
            color: "#f8fafc",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: "8px",
            fontSize: "14px",
            fontWeight: 500,
            transition: "all 0.2s ease",
            backdropFilter: "blur(10px)",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = showFilters ? "rgba(139, 92, 246, 1)" : "rgba(30, 41, 59, 1)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = showFilters ? "rgba(139, 92, 246, 0.8)" : "rgba(30, 41, 59, 0.8)";
          }}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>
          </svg>
          <span>Filter</span>
        </button>
        
        {/* Filter Dropdown */}
        {showFilters && (
          <div
            data-testid="graph-filter-panel"
            style={{
              position: "absolute",
              top: "60px",
              right: isFullscreen ? "175px" : "145px",
              backgroundColor: "rgba(15, 23, 42, 0.98)",
              border: "1px solid rgba(148, 163, 184, 0.15)",
              borderRadius: "10px",
              padding: "12px",
              minWidth: "200px",
              maxWidth: "240px",
              maxHeight: "380px",
              overflowY: "auto",
              overflowX: "hidden",
              backdropFilter: "blur(10px)",
              scrollbarWidth: "thin",
              scrollbarColor: "rgba(139, 92, 246, 0.5) rgba(30, 41, 59, 0.3)",
              zIndex: 20,
            }}
            className="filter-panel-scroll"
          >
            {/* Graph View Mode */}
            <div style={{ marginBottom: "12px" }}>
              <div style={{ fontSize: "10px", color: "#64748b", marginBottom: "6px", fontWeight: 600, letterSpacing: "0.5px" }}>
                GRAPH VIEW
              </div>
              <div style={{ display: "flex", gap: "6px" }}>
                <button
                  onClick={() => setViewMode('standard')}
                  style={{
                    flex: 1,
                    padding: "6px 10px",
                    backgroundColor: viewMode === 'standard' ? "rgba(139, 92, 246, 0.3)" : "rgba(255,255,255,0.05)",
                    border: viewMode === 'standard' ? "1px solid #8b5cf6" : "1px solid rgba(148, 163, 184, 0.2)",
                    borderRadius: "5px",
                    color: viewMode === 'standard' ? "#a78bfa" : "#94a3b8",
                    fontSize: "11px",
                    cursor: "pointer",
                    transition: "all 0.2s",
                  }}
                >
                  Standard
                </button>
                <button
                  onClick={() => setViewMode('clustered')}
                  style={{
                    flex: 1,
                    padding: "6px 10px",
                    backgroundColor: viewMode === 'clustered' ? "rgba(139, 92, 246, 0.3)" : "rgba(255,255,255,0.05)",
                    border: viewMode === 'clustered' ? "1px solid #8b5cf6" : "1px solid rgba(148, 163, 184, 0.2)",
                    borderRadius: "5px",
                    color: viewMode === 'clustered' ? "#a78bfa" : "#94a3b8",
                    fontSize: "11px",
                    cursor: "pointer",
                    transition: "all 0.2s",
                  }}
                >
                  Clustered
                </button>
              </div>
            </div>
            
            {/* Entity Types */}
            <div style={{ marginBottom: "12px" }}>
              <div style={{ fontSize: "10px", color: "#64748b", marginBottom: "4px", fontWeight: 600, letterSpacing: "0.5px" }}>
                ENTITY TYPES
              </div>
              {Object.entries(entityFilters).map(([type, enabled]) => (
                <label
                  key={type}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    padding: "4px 2px",
                    cursor: "pointer",
                    borderRadius: "4px",
                    transition: "background 0.2s",
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.backgroundColor = "rgba(255,255,255,0.05)"}
                  onMouseLeave={(e) => e.currentTarget.style.backgroundColor = "transparent"}
                >
                  <input
                    type="checkbox"
                    checked={enabled}
                    onChange={(e) => setEntityFilters(prev => ({ ...prev, [type]: e.target.checked }))}
                    style={{ width: "12px", height: "12px", accentColor: "#8b5cf6", cursor: "pointer" }}
                  />
                  <span style={{
                    display: "inline-block",
                    width: "6px",
                    height: "6px",
                    borderRadius: "50%",
                    backgroundColor: type === 'project' ? '#3b82f6' : 
                                     type === 'fund' ? '#10b981' : 
                                     type === 'person' ? '#f59e0b' : 
                                     type === 'exchange' ? '#ef4444' :
                                     type === 'token' ? '#8b5cf6' : '#64748b'
                  }} />
                  <span style={{ color: "#e2e8f0", fontSize: "11px", textTransform: "capitalize" }}>
                    {type}s
                  </span>
                </label>
              ))}
            </div>
            
            {/* Relation Types */}
            <div style={{ marginBottom: "10px" }}>
              <div style={{ fontSize: "10px", color: "#64748b", marginBottom: "4px", fontWeight: 600, letterSpacing: "0.5px" }}>
                RELATION TYPES
              </div>
              {Object.entries(relationFilters).map(([type, enabled]) => (
                <label
                  key={type}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    padding: "4px 2px",
                    cursor: "pointer",
                    borderRadius: "4px",
                    transition: "background 0.2s",
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.backgroundColor = "rgba(255,255,255,0.05)"}
                  onMouseLeave={(e) => e.currentTarget.style.backgroundColor = "transparent"}
                >
                  <input
                    type="checkbox"
                    checked={enabled}
                    onChange={(e) => setRelationFilters(prev => ({ ...prev, [type]: e.target.checked }))}
                    style={{ width: "12px", height: "12px", accentColor: "#10b981", cursor: "pointer" }}
                  />
                  <span style={{
                    display: "inline-block",
                    width: "8px",
                    height: "2px",
                    borderRadius: "1px",
                    backgroundColor: type === 'invested_in' ? '#10b981' : 
                                     type === 'coinvested_with' ? '#3b82f6' : 
                                     type === 'founded' ? '#f59e0b' : 
                                     type === 'has_token' ? '#8b5cf6' :
                                     type === 'traded_on' ? '#ef4444' : '#ec4899'
                  }} />
                  <span style={{ color: "#e2e8f0", fontSize: "11px" }}>
                    {type.replace(/_/g, ' ')}
                  </span>
                </label>
              ))}
            </div>
            
            {/* G3: Scope Filters (Context Layer) */}
            <div style={{ marginBottom: "10px" }}>
              <div style={{ fontSize: "10px", color: "#64748b", marginBottom: "4px", fontWeight: 600, letterSpacing: "0.5px" }}>
                CONTEXT SCOPES
              </div>
              {Object.entries(scopeFilters).map(([scope, enabled]) => (
                <label
                  key={scope}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    padding: "4px 2px",
                    cursor: "pointer",
                    borderRadius: "4px",
                    transition: "background 0.2s",
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.backgroundColor = "rgba(255,255,255,0.05)"}
                  onMouseLeave={(e) => e.currentTarget.style.backgroundColor = "transparent"}
                >
                  <input
                    type="checkbox"
                    checked={enabled}
                    onChange={(e) => setScopeFilters(prev => ({ ...prev, [scope]: e.target.checked }))}
                    style={{ width: "12px", height: "12px", accentColor: "#f59e0b", cursor: "pointer" }}
                  />
                  <span style={{
                    display: "inline-block",
                    width: "10px",
                    height: "10px",
                    borderRadius: "2px",
                    backgroundColor: scope === 'founder' ? '#f59e0b' : 
                                     scope === 'investment' ? '#10b981' : 
                                     scope === 'ecosystem' ? '#3b82f6' : 
                                     scope === 'partnership' ? '#8b5cf6' :
                                     scope === 'market' ? '#ef4444' :
                                     scope === 'event' ? '#06b6d4' : '#64748b',
                    fontSize: "7px",
                    fontWeight: "bold",
                    color: "#fff",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center"
                  }}>
                    {scope[0].toUpperCase()}
                  </span>
                  <span style={{ color: "#e2e8f0", fontSize: "11px", textTransform: "capitalize" }}>
                    {scope}
                  </span>
                </label>
              ))}
            </div>
            
            {/* Reset Button */}
            <div style={{ borderTop: "1px solid rgba(148, 163, 184, 0.1)", paddingTop: "10px" }}>
              <button
                data-testid="filter-reset-btn"
                onClick={() => {
                  setEntityFilters({ project: true, fund: true, person: true, exchange: true, token: true, asset: true });
                  setRelationFilters({ invested_in: true, coinvested_with: true, founded: true, has_token: true, traded_on: true, works_at: true });
                  setScopeFilters({ founder: true, investment: true, ecosystem: true, partnership: true, market: true, event: true, mention: false });
                  setViewMode('standard');
                }}
                style={{
                  width: "100%",
                  padding: "6px",
                  backgroundColor: "transparent",
                  border: "1px solid rgba(139, 92, 246, 0.3)",
                  borderRadius: "5px",
                  color: "#a78bfa",
                  fontSize: "11px",
                  cursor: "pointer",
                  transition: "all 0.2s",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = "rgba(139, 92, 246, 0.1)";
                  e.currentTarget.style.borderColor = "rgba(139, 92, 246, 0.5)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = "transparent";
                  e.currentTarget.style.borderColor = "rgba(139, 92, 246, 0.3)";
                }}
              >
                Reset All
              </button>
            </div>
          </div>
        )}
      </div>
      <GraphCanvas
        forceRef={forceRef}
        graphData={filteredGraphData}
        width={containerRef.current?.clientWidth || effectiveWidth}
        height={effectiveHeight}
        drawNode={drawNode}
        drawLink={drawLink}
        handleNodeDrag={handleNodeDrag}
        handleNodeDragEnd={handleNodeDragEnd}
        handleEngineStop={handleEngineStop}
        handleNodeClick={handleNodeClick}
        onNodeHover={useCallback((node) => {
          document.body.style.cursor = node ? "pointer" : "default";
          // Update ref immediately for drawing functions
          hoveredNodeRef.current = node;
          // Update state for tooltip display (debounced)
          setHoveredNode(node);
        }, [])}
        onLinkHover={useCallback((link) => {
          hoveredLinkRef.current = link;
          setHoveredLink(link);
        }, [])}
      />
      
      {/* MINIMAL Node Tooltip - Name + Type only */}
      {hoveredNode && (
        <div
          style={{
            position: "fixed",
            left: mousePos.x + 12,
            top: mousePos.y + 12,
            backgroundColor: "rgba(15, 23, 42, 0.95)",
            border: "1px solid rgba(100, 116, 139, 0.3)",
            color: "white",
            padding: "6px 10px",
            borderRadius: "6px",
            fontSize: "12px",
            pointerEvents: "none",
            zIndex: 1000,
            maxWidth: "300px",
          }}
        >
          <div style={{ fontWeight: 500, color: "#f1f5f9" }}>
            {hoveredNode.fullName || hoveredNode.label}
          </div>
          <div style={{ color: "#94a3b8", fontSize: "11px", textTransform: "capitalize" }}>
            {hoveredNode.type === 'cluster' 
              ? (hoveredNode.id?.split(':')[1] || 'cluster')
              : (hoveredNode.id?.split(':')[0] || 'Entity')
            }
          </div>
          {/* Show child entities for clusters */}
          {hoveredNode.type === 'cluster' && hoveredNode.childNames && (
            <div style={{ marginTop: "6px", borderTop: "1px solid rgba(100, 116, 139, 0.2)", paddingTop: "6px" }}>
              {hoveredNode.childNames.map((name, idx) => (
                <div key={idx} style={{ color: "#cbd5e1", fontSize: "11px", lineHeight: "1.4" }}>
                  • {name}
                </div>
              ))}
              {hoveredNode.totalChildren > 8 && (
                <div style={{ color: "#64748b", fontSize: "10px", marginTop: "4px" }}>
                  +{hoveredNode.totalChildren - 8} more...
                </div>
              )}
            </div>
          )}
        </div>
      )}
      
      {/* MINIMAL Link Tooltip - Relation only */}
      {hoveredLink && !hoveredNode && (
        <div
          style={{
            position: "fixed",
            left: mousePos.x + 12,
            top: mousePos.y + 12,
            backgroundColor: "rgba(15, 23, 42, 0.95)",
            border: "1px solid rgba(100, 116, 139, 0.3)",
            color: "white",
            padding: "5px 8px",
            borderRadius: "4px",
            fontSize: "11px",
            pointerEvents: "none",
            zIndex: 1000,
          }}
        >
          <span style={{ color: getRelationColor(hoveredLink.relation) }}>
            {(hoveredLink.relation || 'related').replace(/_/g, ' ')}
          </span>
        </div>
      )}
    </div>
  );
};

export default ForceGraphViewer;

