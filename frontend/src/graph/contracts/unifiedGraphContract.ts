export type GraphNode = {
  id: string;
  label: string;
  type: string;
  address?: string;
  chain?: string;
  cluster_id?: string;
  metadata?: Record<string, any>;
};

export type GraphEdge = {
  id: string;
  source: string;
  target: string;
  direction: "in" | "out";
  type: string;

  amountUsd?: number;
  txHash?: string;
  timestamp?: number;
  chain?: string;

  confidence?: number;
  tags?: string[];
  metadata?: Record<string, any>;
};

export type Corridor = {
  id: string;
  source: string;
  target: string;
  pattern: string;
  amountUsd: number;
  path: string[];
  chains: string[];
};

export type GraphPayload = {
  nodes: GraphNode[];
  edges: GraphEdge[];

  corridors?: Corridor[];

  highlightedPath?: string[];
  riskSummary?: any;
  explain?: any;
};
