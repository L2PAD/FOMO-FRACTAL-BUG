/**
 * Embedded Navigation Types
 * =========================
 * 
 * P0.8 FIX: Navigation contract for legacy pages embedded in OnchainV3
 * 
 * When layoutMode="embedded", legacy pages must NOT navigate to old routes
 * like /entities, /wallets, etc. Instead, they should use these callbacks
 * to stay within the OnchainV3 sandbox.
 */

export interface EmbeddedNavigation {
  /** Base path for OnchainV3 (default: /intelligence/onchain-v3) */
  basePath?: string;
  
  /** Go back to tab list (e.g., from entity detail back to entities list) */
  onBack?: () => void;
  
  /** Open entity detail within v3 */
  onOpenEntity?: (entityId: string) => void;
  
  /** Open wallet detail within v3 */
  onOpenWallet?: (address: string) => void;
  
  /** Open signals filtered by entity */
  onOpenSignals?: (entityId?: string) => void;
  
  /** Open graph for address */
  onOpenGraph?: (address?: string) => void;
}

export interface LegacyPageProps {
  /** Layout mode: 'default' uses full page, 'embedded' removes header/sidebar */
  layoutMode?: 'default' | 'embedded';
  
  /** Navigation callbacks for embedded mode */
  nav?: EmbeddedNavigation;
}
