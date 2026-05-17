/**
 * ADMIN NAVIGATION REGISTRY
 *
 * Hierarchical navigation structure for the admin panel.
 *
 * PRINCIPLES:
 * 1. Tree structure, not flat list
 * 2. Level 1 always visible (domains)
 * 3. Level 2 collapsible (groups)
 * 4. Level 3 is actual pages
 * 5. Modules are isolated - cannot affect Platform/ML
 *
 * Adding new pages: just add a node to the tree
 * Adding new modules: add to MODULES section
 *
 * BASE: GitHub FOMOwiki/FOMO-SEOFv1 (5 March 2026) — CONSTANT
 * ADDITIONS: All routes from App.js that were not yet linked
 */

import {
  Activity,
  Database,
  Zap,
  Server,
  TestTube,
  FileText,
  Brain,
  BarChart3,
  Box,
  RefreshCw,
  LineChart,
  Gauge,
  Award,
  TrendingUp,
  Twitter,
  Shield,
  Settings,
  MessageSquare,
  MessageCircle,
  Link2,
  Bell,
  UserCog,
  FlaskConical,
  Newspaper,
  DollarSign,
  Users,
  Smartphone,
} from 'lucide-react';

export const ADMIN_NAV = [
  // ═══════════════════════════════════════════════════════════════
  // PLATFORM — Operations: System / Decision Engine / Audit Log
  // ═══════════════════════════════════════════════════════════════
  {
    id: 'platform',
    label: 'Platform',
    icon: Server,
    defaultExpanded: true,
    children: [
      {
        id: 'system-overview',
        label: 'System',
        path: '/admin/system-overview',
        icon: Activity,
      },
      {
        id: 'decision-engine',
        label: 'Decision Engine',
        path: '/admin/overview-engine',
        icon: Settings,
      },
      {
        id: 'audit',
        label: 'Audit Log',
        path: '/admin/audit',
        icon: FileText,
      },
    ],
  },

  // ═══════════════════════════════════════════════════════════════
  // ML INTELLIGENCE
  // Production: Overview / MetaBrain / Training
  // Research: Models / Datasets / Ablation / Stability / Attribution
  // ═══════════════════════════════════════════════════════════════
  {
    id: 'ml',
    label: 'ML Intelligence',
    icon: Brain,
    children: [
      {
        id: 'ml-overview',
        label: 'Обзор',
        path: '/admin/ml/overview',
        icon: BarChart3,
      },
      {
        id: 'ml-meta-brain',
        label: 'MetaBrain',
        path: '/admin/ml/meta-brain',
        icon: Brain,
      },
      {
        id: 'ml-signals',
        label: 'Сигналы',
        path: '/admin/ml/signals',
        icon: Zap,
      },
      {
        id: 'ml-models',
        label: 'Модели',
        path: '/admin/ml/models',
        icon: Box,
      },
      {
        id: 'retrain-policies',
        label: 'Auto-Retrain',
        path: '/admin/auto-retrain',
        icon: RefreshCw,
      },
      {
        id: 'ml-research',
        label: 'Исследования',
        path: '/admin/ml/research',
        icon: FlaskConical,
      },
      {
        id: 'ml-backtesting',
        label: 'Backtesting',
        path: '/admin/backtesting',
        icon: TestTube,
      },
    ],
  },

  // ═══════════════════════════════════════════════════════════════
  // EXCHANGE - Exchange Intelligence Module
  // ═══════════════════════════════════════════════════════════════
  {
    id: 'exchange',
    label: 'Exchange',
    icon: TrendingUp,
    children: [
      {
        id: 'exchange-control',
        label: 'Управление',
        path: '/admin/exchange',
        icon: Settings,
      },
      {
        id: 'exchange-intelligence',
        label: 'Intelligence Console',
        path: '/admin/exchange/intelligence',
        icon: Gauge,
      },
      {
        id: 'exchange-decision-intel',
        label: 'Decision Intelligence',
        path: '/admin/exchange/decision-intel',
        icon: Activity,
      },
    ],
  },

  // ═══════════════════════════════════════════════════════════════
  // ON-CHAIN — Pipeline architecture: Overview / Infrastructure / Engine / Validation / Governance / Research
  // ═══════════════════════════════════════════════════════════════
  {
    id: 'onchain',
    label: 'On-chain',
    icon: Link2,
    path: '/admin/onchain',
  },

  // ═══════════════════════════════════════════════════════════════
  // FRACTAL ENGINE - Independent fractal analysis module
  // ═══════════════════════════════════════════════════════════════
  {
    id: 'fractal',
    label: 'Fractal Engine',
    icon: LineChart,
    path: '/admin/fractal',
  },

  // ═══════════════════════════════════════════════════════════════
  // SENTIMENT — Three-layer architecture: Operations / Governance / Research
  // ═══════════════════════════════════════════════════════════════
  {
    id: 'sentiment',
    label: 'Sentiment',
    icon: MessageCircle,
    children: [
      {
        id: 'sentiment-api',
        label: 'API Console',
        path: '/admin/sentiment-api',
        icon: Zap,
      },
      {
        id: 'sentiment-admin',
        label: 'Admin',
        path: '/admin/sentiment',
        icon: Settings,
      },
      {
        id: 'sentiment-reliability',
        label: 'Reliability',
        path: '/admin/sentiment/reliability',
        icon: Shield,
      },
      {
        id: 'sentiment-research',
        label: 'Research',
        path: '/admin/sentiment/research',
        icon: TrendingUp,
      },
      {
        id: 'sentiment-data-monitor',
        label: 'Data Monitor',
        path: '/admin/sentiment/data-monitor',
        icon: Database,
      },
    ],
  },

  // ═══════════════════════════════════════════════════════════════
  // TWITTER — Top-level: Admin overview + Parser + Connections
  // ═══════════════════════════════════════════════════════════════
  {
    id: 'twitter',
    label: 'Twitter',
    icon: Twitter,
    children: [
      {
        id: 'twitter-admin',
        label: 'Twitter Admin',
        path: '/admin/twitter-admin',
        icon: UserCog,
      },
      {
        id: 'twitter-parser',
        label: 'Parser',
        path: '/admin/twitter-parser/sessions',
        icon: Database,
      },
      {
        id: 'twitter-connections',
        label: 'Connections',
        path: '/admin/connections',
        icon: Link2,
      },
    ],
  },

  // ═══════════════════════════════════════════════════════════════
  // NEWS — News Intelligence (internal tabs inside NewsAdminPage)
  // ═══════════════════════════════════════════════════════════════
  {
    id: 'news',
    label: 'News',
    icon: Newspaper,
    path: '/admin/news',
  },

  // ═══════════════════════════════════════════════════════════════
  // SIGNALS — Unified: Signals + Alert Settings + FOMO Alerts
  // ═══════════════════════════════════════════════════════════════
  {
    id: 'signals',
    label: 'Signals',
    icon: Bell,
    path: '/admin/signals',
  },

  // ═══════════════════════════════════════════════════════════════
  // TELEGRAM — Telegram Delivery & Intelligence
  // ═══════════════════════════════════════════════════════════════
  {
    id: 'telegram',
    label: 'Telegram',
    icon: MessageSquare,
    path: '/admin/connections?tab=telegram',
  },

  // ═══════════════════════════════════════════════════════════════
  // PREDICTIONS — Self-Improvement Engine (internal tabs)
  // ═══════════════════════════════════════════════════════════════
  {
    id: 'predictions',
    label: 'Predictions',
    icon: Award,
    path: '/admin/predictions/tuning',
  },

  // ═══════════════════════════════════════════════════════════════
  // MINI APP — Pocket Intelligence OS: Monitoring & Control
  // Single link → internal horizontal tabs
  // ═══════════════════════════════════════════════════════════════
  {
    id: 'miniapp',
    label: 'Мини-апка',
    icon: Smartphone,
    path: '/admin/miniapp',
  },

  // ═══════════════════════════════════════════════════════════════
  // BILLING — Subscription Management & Revenue Analytics
  // Single link → internal horizontal tabs inside BillingAdminPage
  // ═══════════════════════════════════════════════════════════════
  {
    id: 'billing',
    label: 'Billing',
    icon: DollarSign,
    path: '/admin/billing',
  },

  // ═══════════════════════════════════════════════════════════════
  // REFERRALS — Promo Codes, Referral System, Influencer Management
  // ═══════════════════════════════════════════════════════════════
  {
    id: 'referrals',
    label: 'Referrals',
    icon: Users,
    path: '/admin/referrals',
  },

  // ═══════════════════════════════════════════════════════════════
  // INTEL SYSTEM — Infrastructure, Keys, Profile
  // Single link → internal horizontal tabs inside IntelAdminPage
  // ═══════════════════════════════════════════════════════════════
  {
    id: 'intel-system',
    label: 'Intel System',
    icon: Shield,
    path: '/admin/intel',
  },
];

/**
 * Flatten navigation tree to get all paths for route matching
 */
export function getAllPaths(nodes = ADMIN_NAV, paths = []) {
  for (const node of nodes) {
    if (node.path) {
      paths.push(node.path);
    }
    if (node.children) {
      getAllPaths(node.children, paths);
    }
  }
  return paths;
}

/**
 * Find node by path
 */
export function findNodeByPath(path, nodes = ADMIN_NAV) {
  for (const node of nodes) {
    if (node.path === path) {
      return node;
    }
    if (node.children) {
      const found = findNodeByPath(path, node.children);
      if (found) return found;
    }
  }
  return null;
}

/**
 * Get breadcrumb path for a given route
 */
export function getBreadcrumb(path, nodes = ADMIN_NAV, trail = []) {
  for (const node of nodes) {
    const currentTrail = [...trail, node.label];

    if (node.path === path) {
      return currentTrail;
    }

    if (node.children) {
      const found = getBreadcrumb(path, node.children, currentTrail);
      if (found) return found;
    }
  }
  return null;
}

/**
 * Check if a path is within a section
 */
export function isPathInSection(path, sectionId, nodes = ADMIN_NAV) {
  const section = nodes.find(n => n.id === sectionId);
  if (!section) return false;

  const sectionPaths = getAllPaths([section]);
  return sectionPaths.some(p => path.startsWith(p));
}

export default ADMIN_NAV;
