/**
 * Entities Tab — Phase E-UI
 * Replaces legacy EntitiesLegacyTab with new Entity Intelligence Terminal
 */

import { useState } from 'react';
// @ts-ignore
import EntitiesListPage from '../../EntitiesTerminal';
// @ts-ignore
import EntityTerminalPage from '../../EntityTerminal';

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

export default function EntitiesTab({ nav, selectedEntity }: Props) {
  const [activeEntity, setActiveEntity] = useState<string | null>(selectedEntity || null);

  // If we have a selected entity, show the detail terminal
  if (activeEntity) {
    return <EntityTerminalEmbedded 
      entityId={activeEntity} 
      onBack={() => setActiveEntity(null)} 
    />;
  }

  // Otherwise show the list
  return <EntitiesListEmbedded onSelectEntity={(slug: string) => setActiveEntity(slug)} />;
}

/** Embedded list — intercepts navigation to keep within tab */
function EntitiesListEmbedded({ onSelectEntity }: { onSelectEntity: (slug: string) => void }) {
  // We render EntitiesTerminal but override its navigation
  return <EntitiesListPage _embeddedOnSelect={onSelectEntity} />;
}

/** Embedded detail — wraps EntityTerminal with back button */
function EntityTerminalEmbedded({ entityId, onBack }: { entityId: string; onBack: () => void }) {
  return <EntityTerminalPage _embeddedEntityId={entityId} _embeddedOnBack={onBack} />;
}
