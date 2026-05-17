/**
 * Entities Legacy Tab
 * ===================
 * 
 * P0.8: Wraps v1 EntitiesPage for embedding in OnchainV3
 * P0.8 FIX: Passes nav callbacks to prevent legacy route navigation
 */

import LegacyTabWrapper from '../components/LegacyTabWrapper';
// @ts-ignore - JSX component without TS types
import EntitiesPage from '../../EntitiesPage';

interface EmbeddedNav {
  onBack?: () => void;
  onOpenEntity?: (entityId: string) => void;
  onOpenWallet?: (address: string) => void;
  onOpenSignals?: (entityId?: string) => void;
  onOpenGraph?: (address?: string) => void;
}

interface Props {
  nav?: EmbeddedNav;
  selectedEntity?: string | null;
}

export default function EntitiesLegacyTab({ nav, selectedEntity }: Props) {
  return (
    <LegacyTabWrapper>
      <EntitiesPage 
        layoutMode="embedded" 
        nav={nav}
        selectedEntity={selectedEntity}
      />
    </LegacyTabWrapper>
  );
}
