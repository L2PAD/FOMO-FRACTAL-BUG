import { useState, useRef, useEffect } from 'react';
import { Search, X } from 'lucide-react';
import { useMiniApp } from '../../../context/MiniAppContext';

const API = process.env.REACT_APP_BACKEND_URL;

export function SearchBar() {
  const { setSelectedAsset, setActiveTab, recentAssets, favoriteAssets } = useMiniApp();
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const [results, setResults] = useState([]);
  const inputRef = useRef(null);

  useEffect(() => {
    if (!query) { setResults([]); return; }
    const t = setTimeout(async () => {
      try {
        const res = await fetch(`${API}/api/miniapp/search?q=${encodeURIComponent(query)}`);
        const json = await res.json();
        if (json.ok) setResults(json.results);
      } catch {}
    }, 200);
    return () => clearTimeout(t);
  }, [query]);

  const selectAsset = (ticker) => {
    setSelectedAsset(ticker);
    setActiveTab('home');
    setQuery('');
    setOpen(false);
  };

  return (
    <div style={{ position: 'relative', padding: '12px 16px 0' }} data-testid="search-container">
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
        padding: '10px 14px',
        background: 'var(--ma-surface, #18181b)',
        borderRadius: '16px',
        border: open ? '1px solid var(--ma-border-active, #52525b)' : '1px solid var(--ma-border, #27272a)',
        transition: 'border 0.15s',
      }}>
        <Search size={16} color="var(--ma-muted, #52525b)" />
        <input
          ref={inputRef}
          data-testid="search-input"
          value={query}
          onChange={e => setQuery(e.target.value)}
          onFocus={() => setOpen(true)}
          placeholder="Search"
          style={{
            flex: 1,
            background: 'transparent',
            border: 'none',
            outline: 'none',
            color: 'var(--ma-text, #fafafa)',
            fontSize: '14px',
            fontFamily: "'Manrope', sans-serif",
          }}
        />
        {query && (
          <button onClick={() => { setQuery(''); setOpen(false); }} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}>
            <X size={14} color="var(--ma-muted, #52525b)" />
          </button>
        )}
      </div>

      {/* Dropdown */}
      {open && (
        <div
          data-testid="search-dropdown"
          style={{
            position: 'absolute',
            top: '100%',
            left: '16px',
            right: '16px',
            background: 'var(--ma-surface, #18181b)',
            border: '1px solid var(--ma-border, #27272a)',
            borderRadius: '16px',
            marginTop: '4px',
            maxHeight: '280px',
            overflowY: 'auto',
            zIndex: 40,
            padding: '8px',
          }}
        >
          {!query && (
            <>
              {favoriteAssets.length > 0 && (
                <DropdownSection label="Favorites" items={favoriteAssets} onSelect={selectAsset} />
              )}
              {recentAssets.length > 0 && (
                <DropdownSection label="Recent" items={recentAssets} onSelect={selectAsset} />
              )}
            </>
          )}
          {query && results.length > 0 && (
            <div>
              {results.map(r => (
                <button
                  key={r.ticker}
                  onClick={() => selectAsset(r.ticker)}
                  data-testid={`search-result-${r.ticker.toLowerCase()}`}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                    width: '100%',
                    padding: '10px 12px',
                    background: 'transparent',
                    border: 'none',
                    borderRadius: '10px',
                    cursor: 'pointer',
                    textAlign: 'left',
                  }}
                  onMouseEnter={e => e.currentTarget.style.background = 'var(--ma-hover, #27272a)'}
                  onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                >
                  <span style={{ fontSize: '14px', fontWeight: 700, color: 'var(--ma-text, #fafafa)', fontFamily: "'JetBrains Mono', monospace" }}>{r.ticker}</span>
                  <span style={{ fontSize: '12px', color: 'var(--ma-secondary, #a1a1aa)', fontFamily: "'Manrope', sans-serif" }}>{r.name}</span>
                </button>
              ))}
            </div>
          )}
          {query && results.length === 0 && (
            <div style={{ padding: '16px', textAlign: 'center', color: 'var(--ma-muted, #52525b)', fontSize: '13px' }}>No results</div>
          )}
          {/* Backdrop close */}
          <button
            onClick={() => setOpen(false)}
            style={{ position: 'fixed', inset: 0, background: 'transparent', border: 'none', zIndex: -1 }}
          />
        </div>
      )}
    </div>
  );
}

function DropdownSection({ label, items, onSelect }) {
  return (
    <div style={{ marginBottom: '8px' }}>
      <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--ma-muted)', padding: '4px 12px', letterSpacing: '0.15em', textTransform: 'uppercase', fontFamily: "'Manrope', sans-serif" }}>
        {label}
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', padding: '4px 8px' }}>
        {items.map(a => (
          <button
            key={a}
            onClick={() => onSelect(a)}
            style={{
              padding: '6px 14px',
              background: 'var(--ma-hover)',
              border: 'none',
              borderRadius: '20px',
              color: 'var(--ma-text)',
              fontSize: '12px',
              fontWeight: 600,
              fontFamily: "'JetBrains Mono', monospace",
              cursor: 'pointer',
            }}
          >
            {a}
          </button>
        ))}
      </div>
    </div>
  );
}
