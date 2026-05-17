/**
 * Signals Legacy Tab
 * ==================
 * 
 * P0.8: Wraps v1 SignalsPageD1 (Live Signals) for embedding in OnchainV3
 * Full D1 signals logic with filters, Telegram alerts, and Signal Stats
 */

import LegacyTabWrapper from '../components/LegacyTabWrapper';
// @ts-ignore - JSX component without TS types
import SignalsPageD1 from '../../SignalsPageD1';

interface EmbeddedNav {
  onBack?: () => void;
  onOpenEntity?: (entityId: string) => void;
  onOpenWallet?: (address: string) => void;
  onOpenSignals?: (entityId?: string) => void;
  onOpenGraph?: (address?: string) => void;
}

interface Props {
  nav?: EmbeddedNav;
}

export default function SignalsLegacyTab({ nav }: Props) {
  return (
    <LegacyTabWrapper>
      <SignalsPageD1 
        layoutMode="embedded" 
        nav={nav}
      />
    </LegacyTabWrapper>
  );
}
