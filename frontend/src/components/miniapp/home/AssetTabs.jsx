import { X } from 'lucide-react';
import { useMiniApp } from '../../../context/MiniAppContext';

const MAX_PANEL_ASSETS = 5;

export function AssetTabs() {
  const { selectedAsset, setSelectedAsset, panelAssets, removeFromPanel } = useMiniApp();

  const pills = panelAssets.slice(0, MAX_PANEL_ASSETS);

  if (pills.length === 0) {
    return (
      <div data-testid="asset-tabs" style={{ padding: '10px 16px 4px' }}>
        <div style={{
          fontSize: '12px', color: 'var(--ma-muted, #52525b)',
          fontFamily: "'Manrope', sans-serif", textAlign: 'center',
          padding: '8px', borderRadius: '12px',
          border: '1px dashed var(--ma-border, #27272a)',
        }}>
          Search to add assets
        </div>
      </div>
    );
  }

  return (
    <div
      data-testid="asset-tabs"
      style={{
        display: 'flex',
        gap: '6px',
        padding: '10px 16px 4px',
        overflowX: 'auto',
      }}
    >
      {pills.map(a => {
        const isActive = selectedAsset === a;
        return (
          <div
            key={a}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '2px',
              padding: '0 4px 0 0',
              borderRadius: '20px',
              border: isActive ? 'none' : '1px solid var(--ma-border, #27272a)',
              background: isActive ? 'var(--ma-text, #fafafa)' : 'transparent',
              flexShrink: 0,
              transition: 'all 0.15s ease',
            }}
          >
            <button
              data-testid={`asset-tab-${a.toLowerCase()}`}
              onClick={() => setSelectedAsset(a)}
              style={{
                padding: '8px 10px 8px 14px',
                background: 'transparent',
                border: 'none',
                color: isActive ? 'var(--ma-bg, #09090b)' : 'var(--ma-secondary, #a1a1aa)',
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: '13px',
                fontWeight: isActive ? 700 : 500,
                cursor: 'pointer',
                whiteSpace: 'nowrap',
              }}
            >
              {a}
            </button>
            <button
              data-testid={`asset-remove-${a.toLowerCase()}`}
              onClick={(e) => { e.stopPropagation(); removeFromPanel(a); }}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                width: '18px', height: '18px', borderRadius: '50%',
                background: isActive ? 'rgba(0,0,0,0.15)' : 'var(--ma-hover, rgba(39,39,42,0.5))',
                border: 'none', cursor: 'pointer', padding: 0,
                transition: 'background 0.15s',
              }}
            >
              <X size={10} color={isActive ? 'var(--ma-bg, #09090b)' : 'var(--ma-muted, #52525b)'} />
            </button>
          </div>
        );
      })}
    </div>
  );
}
