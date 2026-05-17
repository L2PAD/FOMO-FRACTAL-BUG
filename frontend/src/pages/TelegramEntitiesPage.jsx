/**
 * Telegram Entities Overview Page (Production)
 * Connected to real backend with URL-driven filters
 */
import { useState, useEffect, useCallback, useRef } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { 
  Search, 
  Filter, 
  Star, 
  ChevronLeft, 
  ChevronRight,
  RefreshCw,
  Loader2,
  Rss,
  Bookmark,
  BookmarkCheck,
  Users,
  Plus,
  Check,
  Send
} from 'lucide-react';
import TelegramFilterDrawer from '../components/telegram/TelegramFilterDrawer';
import { Sparkline } from '../modules/telegram/components/Sparkline';

const API_BASE = process.env.REACT_APP_BACKEND_URL || '';

function darkenColor(hex, amount = 0.3) {
  if (!hex || !hex.startsWith('#')) return hex;
  const num = parseInt(hex.slice(1), 16);
  let r = (num >> 16) & 0xFF;
  let g = (num >> 8) & 0xFF;
  let b = num & 0xFF;
  r = Math.round(r * (1 - amount));
  g = Math.round(g * (1 - amount));
  b = Math.round(b * (1 - amount));
  return `#${((r << 16) | (g << 8) | b).toString(16).padStart(6, '0')}`;
}

export default function TelegramEntitiesPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filterOpen, setFilterOpen] = useState(false);
  const [searchInput, setSearchInput] = useState(searchParams.get('q') || '');
  const [watchlist, setWatchlist] = useState(new Set());
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [telegramResult, setTelegramResult] = useState(null);
  const [addingChannel, setAddingChannel] = useState(false);
  const [addedChannel, setAddedChannel] = useState(null);
  const suggestionsRef = useRef(null);
  const searchRef = useRef(null);
  const debounceRef = useRef(null);

  // Build API URL from search params
  const buildApiUrl = useCallback(() => {
    const params = new URLSearchParams();
    
    // Transfer all search params to API
    searchParams.forEach((value, key) => {
      params.set(key, value);
    });
    
    // Ensure defaults
    if (!params.has('limit')) params.set('limit', '20');
    if (!params.has('page')) params.set('page', '1');
    
    return `${API_BASE}/api/telegram-intel/utility/list?${params.toString()}`;
  }, [searchParams]);

  // Fetch data
  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      const url = buildApiUrl();
      const res = await fetch(url);
      
      if (!res.ok) {
        throw new Error(`API error: ${res.status}`);
      }
      
      const json = await res.json();
      setData(json);
    } catch (err) {
      console.error('[Entities] Fetch error:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [buildApiUrl]);

  // Fetch on mount and when params change
  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Fetch watchlist
  const fetchWatchlist = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/telegram-intel/watchlist`);
      const data = await res.json();
      if (data.ok && data.items) {
        setWatchlist(new Set(data.items.map(i => i.username)));
      }
    } catch (err) {
      console.error('[Watchlist] Fetch error:', err);
    }
  }, []);

  useEffect(() => {
    fetchWatchlist();
  }, [fetchWatchlist]);

  // Autocomplete: fetch suggestions as user types
  const fetchSuggestions = useCallback(async (query) => {
    if (!query || query.length < 1) {
      setSuggestions([]);
      setTelegramResult(null);
      setAddedChannel(null);
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/api/telegram-intel/channels/autocomplete?q=${encodeURIComponent(query)}&limit=6`);
      const data = await res.json();
      if (data.ok && data.suggestions) {
        setSuggestions(data.suggestions);
        setShowSuggestions(true);
        // If no DB matches and query looks like a username/name, search Telegram
        if (data.suggestions.length === 0 && query.length >= 3) {
          setTelegramResult('searching');
          try {
            const tgRes = await fetch(`${API_BASE}/api/telegram-intel/channels/search-telegram?username=${encodeURIComponent(query)}`);
            const tgData = await tgRes.json();
            if (tgData.ok && tgData.found) {
              setTelegramResult(tgData);
              setShowSuggestions(true);
            } else {
              setTelegramResult('not_found');
            }
          } catch {
            setTelegramResult(null);
          }
        } else {
          setTelegramResult(null);
        }
      }
    } catch (err) {
      console.error('[Autocomplete] error:', err);
    }
  }, []);

  // Debounced search input handler
  const handleSearchInputChange = (e) => {
    const val = e.target.value;
    setSearchInput(val);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => fetchSuggestions(val), 200);
  };

  // Click outside to close suggestions
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (
        suggestionsRef.current && !suggestionsRef.current.contains(e.target) &&
        searchRef.current && !searchRef.current.contains(e.target)
      ) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Select a suggestion -> navigate to channel
  const selectSuggestion = (ch) => {
    setShowSuggestions(false);
    setSearchInput('');
    setTelegramResult(null);
    setAddedChannel(null);
    navigate(`/telegram/${ch.username}`);
  };

  // Add channel from Telegram
  const addChannel = async (username) => {
    setAddingChannel(true);
    try {
      const res = await fetch(`${API_BASE}/api/telegram-intel/channels/add`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username }),
      });
      const data = await res.json();
      if (data.ok) {
        setAddedChannel(data.username || username);
        setTelegramResult(null);
        // Refresh entity list
        setTimeout(() => {
          fetchData();
          setShowSuggestions(false);
          setSearchInput('');
          setAddedChannel(null);
          navigate(`/telegram/${data.username || username}`);
        }, 1500);
      }
    } catch (err) {
      console.error('[AddChannel] error:', err);
    } finally {
      setAddingChannel(false);
    }
  };

  // Toggle watchlist
  const toggleWatchlist = async (username, e) => {
    e.stopPropagation();
    const isInWatchlist = watchlist.has(username);
    
    try {
      if (isInWatchlist) {
        await fetch(`${API_BASE}/api/telegram-intel/watchlist/${username}`, { method: 'DELETE' });
        setWatchlist(prev => {
          const next = new Set(prev);
          next.delete(username);
          return next;
        });
      } else {
        await fetch(`${API_BASE}/api/telegram-intel/watchlist`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username })
        });
        setWatchlist(prev => new Set([...prev, username]));
      }
    } catch (err) {
      console.error('[Watchlist] Toggle error:', err);
    }
  };

  // Clear all watchlist
  const [clearingWatchlist, setClearingWatchlist] = useState(false);
  const clearAllWatchlist = async () => {
    if (!window.confirm('Remove all channels from favorites?')) return;
    setClearingWatchlist(true);
    try {
      await fetch(`${API_BASE}/api/telegram-intel/watchlist`, { method: 'DELETE' });
      setWatchlist(new Set());
    } catch (err) {
      console.error('[Watchlist] Clear error:', err);
    } finally {
      setClearingWatchlist(false);
    }
  };

  // Handle search submit
  const handleSearch = (e) => {
    e.preventDefault();
    const newParams = new URLSearchParams(searchParams);
    if (searchInput.trim()) {
      newParams.set('q', searchInput.trim());
    } else {
      newParams.delete('q');
    }
    newParams.set('page', '1');
    setSearchParams(newParams);
  };

  // Handle pagination
  const goToPage = (page) => {
    const newParams = new URLSearchParams(searchParams);
    newParams.set('page', String(page));
    setSearchParams(newParams);
  };

  const currentPage = Number(searchParams.get('page')) || 1;
  const limit = Number(searchParams.get('limit')) || 20;
  const total = data?.total || 0;
  const totalPages = Math.ceil(total / limit);
  const items = data?.items || [];
  const stats = data?.stats || { tracked: 0, avgUtility: 0, highGrowth: 0, highRisk: 0 };

  // Count active filters
  const activeFilters = Array.from(searchParams.entries()).filter(
    ([key]) => !['page', 'limit', 'q'].includes(key)
  ).length;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header — unified style: Icon+Title | Search | Feed | Filter */}
      <div className="border-b border-gray-200 bg-white h-[71px]">
        <div className="px-6 h-full flex items-center">
          <div className="flex items-center justify-between w-full">
            {/* Left: Icon + Title + Slogan */}
            <div className="flex items-center gap-3 shrink-0">
              <Send className="w-5 h-5 text-gray-400" />
              <div>
                <h1 className="text-xl font-bold text-gray-900" data-testid="telegram-title">Telegram</h1>
                <p className="text-sm text-gray-500">Channel intelligence & signal delivery</p>
              </div>
            </div>

            {/* Right: Search + Feed + Clear + Filter */}
            <div className="flex items-center gap-3">
              {/* Stats inline */}
              <div className="flex items-center gap-5">
                <StatCard label="Tracked" value={stats.tracked} color="teal" />
                <StatCard label="Avg Score" value={stats.avgUtility} color="teal" />
                <StatCard label="High Growth" value={stats.highGrowth} color="emerald" />
                <StatCard label="High Risk" value={stats.highRisk} color="rose" />
              </div>

              <div className="w-px h-6 bg-gray-200" />

              {/* Search Form */}
              <form onSubmit={handleSearch} className="relative w-64" ref={searchRef}>
                <input
                  type="text"
                  placeholder="Search channels..."
                  value={searchInput}
                  onChange={handleSearchInputChange}
                  onFocus={() => { if (suggestions.length > 0) setShowSuggestions(true); }}
                  className="w-full px-4 py-1.5 border border-gray-200 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-teal-100 focus:border-teal-400"
                  data-testid="entity-search"
                />
                {/* Autocomplete Dropdown */}
                {showSuggestions && (suggestions.length > 0 || telegramResult) && (
                  <div 
                    ref={suggestionsRef}
                    className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-50 overflow-hidden"
                    style={{ minWidth: '360px' }}
                    data-testid="search-suggestions"
                  >
                    {suggestions.map((ch) => (
                      <button
                        key={ch.username}
                        type="button"
                        onClick={() => selectSuggestion(ch)}
                        className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-teal-50 transition-colors text-left"
                        data-testid={`suggestion-${ch.username}`}
                      >
                        {ch.avatarUrl ? (
                          <img 
                            src={`${API_BASE}${ch.avatarUrl}`} 
                            alt="" 
                            className="w-8 h-8 rounded-full object-cover flex-shrink-0"
                            onError={(e) => { e.target.style.display = 'none'; e.target.nextSibling.style.display = 'flex'; }}
                          />
                        ) : null}
                        <div 
                          className={`w-8 h-8 rounded-full items-center justify-center text-white text-xs font-semibold flex-shrink-0 ${ch.avatarUrl ? 'hidden' : 'flex'}`}
                          style={{ backgroundColor: ch.sectorColor || '#6366f1' }}
                        >
                          {(ch.title || ch.username).substring(0, 2).toUpperCase()}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-gray-900 truncate">{ch.title || ch.username}</p>
                          <p className="text-xs text-gray-500">@{ch.username} {ch.sector ? `• ${ch.sector}` : ''}</p>
                        </div>
                        <div className="flex items-center gap-1 text-xs text-gray-400 flex-shrink-0">
                          <Users className="w-3 h-3" />
                          {formatNumber(ch.members)}
                        </div>
                      </button>
                    ))}

                    {telegramResult === 'searching' && (
                      <div className="px-4 py-3 flex items-center gap-2 text-sm text-gray-500 border-t border-gray-100">
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Searching Telegram...
                      </div>
                    )}
                    {telegramResult === 'not_found' && suggestions.length === 0 && (
                      <div className="px-4 py-3 text-sm text-gray-500 border-t border-gray-100">
                        Channel not found in Telegram
                      </div>
                    )}
                    {telegramResult && typeof telegramResult === 'object' && telegramResult.found && (
                      <div className="border-t border-gray-100">
                        <div className="px-4 py-2 text-xs text-gray-400 bg-gray-50">
                          Not tracked yet — found on Telegram:
                        </div>
                        {telegramResult.source === 'telegram' && telegramResult.channel && (
                          <TelegramSearchItem
                            ch={telegramResult.channel}
                            addingChannel={addingChannel}
                            addedChannel={addedChannel}
                            onAdd={addChannel}
                          />
                        )}
                        {telegramResult.source === 'telegram_search' && telegramResult.channels && (
                          telegramResult.channels.map((ch) => (
                            <TelegramSearchItem
                              key={ch.username}
                              ch={ch}
                              addingChannel={addingChannel}
                              addedChannel={addedChannel}
                              onAdd={addChannel}
                            />
                          ))
                        )}
                      </div>
                    )}
                  </div>
                )}
              </form>

              {/* Feed Button */}
              <button 
                onClick={() => navigate('/telegram/feed')}
                className="flex items-center gap-2 px-4 py-1.5 border border-gray-200 rounded-lg text-sm bg-white hover:bg-gray-50 relative"
                data-testid="feed-button"
              >
                <Rss className="w-4 h-4 text-teal-500" />
                <span>Feed</span>
                {watchlist.size > 0 && (
                  <span className="absolute -top-1 -right-1 w-5 h-5 bg-teal-500 text-white text-xs rounded-full flex items-center justify-center">
                    {watchlist.size}
                  </span>
                )}
              </button>

              {watchlist.size > 0 && (
                <button 
                  onClick={clearAllWatchlist}
                  disabled={clearingWatchlist}
                  className="flex items-center gap-2 px-3 py-1.5 border border-red-200 rounded-lg text-sm bg-white hover:bg-red-50 text-red-600 transition-colors disabled:opacity-50"
                  data-testid="clear-watchlist-btn"
                  title="Remove all channels from favorites"
                >
                  <BookmarkCheck className="w-4 h-4" />
                  <span>{clearingWatchlist ? 'Clearing...' : 'Clear all'}</span>
                </button>
              )}

              {/* Filter Button */}
              <button 
                onClick={() => setFilterOpen(true)}
                className="flex items-center gap-2 px-4 py-1.5 border border-gray-200 rounded-lg text-sm bg-white hover:bg-gray-50 relative"
                data-testid="filter-button"
              >
                <Filter className="w-4 h-4 text-gray-500" />
                <span>Filter</span>
                {activeFilters > 0 && (
                  <span className="absolute -top-1 -right-1 w-5 h-5 bg-teal-500 text-white text-xs rounded-full flex items-center justify-center">
                    {activeFilters}
                  </span>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="px-6 py-6">
        {/* Loading State */}
        {loading && (
          <div className="bg-white rounded-xl border border-gray-200 p-12 flex items-center justify-center">
            <Loader2 className="w-8 h-8 text-teal-500 animate-spin" />
          </div>
        )}

        {/* Error State */}
        {error && !loading && (
          <div className="bg-white rounded-xl border border-red-200 p-8 text-center">
            <p className="text-red-600 mb-4">{error}</p>
            <button 
              onClick={fetchData}
              className="px-4 py-2 bg-red-100 text-red-700 rounded-lg text-sm hover:bg-red-200"
            >
              Retry
            </button>
          </div>
        )}

        {/* Table */}
        {!loading && !error && (
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden" data-testid="entities-table">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50/50">
                  <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Channel/Group
                  </th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Type
                  </th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Sector
                  </th>
                  <th className="text-right px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Members
                  </th>
                  <th className="text-right px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Avg Reach
                  </th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Growth (7D)
                  </th>
                  <th className="text-center px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Activity
                  </th>
                  <th className="text-center px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Lang
                  </th>
                  <th className="text-center px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Red Flags
                  </th>
                  <th className="text-right px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">
                    FOMO Score
                  </th>
                </tr>
              </thead>
              <tbody>
                {items.length === 0 ? (
                  <tr>
                    <td colSpan={10} className="px-6 py-12 text-center text-gray-500">
                      No entities found matching your filters.
                    </td>
                  </tr>
                ) : (
                  items.map((entity) => (
                    <EntityRow 
                      key={entity.username} 
                      entity={entity} 
                      isWatchlisted={watchlist.has(entity.username)}
                      onToggleWatchlist={toggleWatchlist}
                    />
                  ))
                )}
              </tbody>
            </table>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between px-6 py-4 border-t border-gray-100">
                <button 
                  onClick={() => goToPage(currentPage - 1)}
                  disabled={currentPage === 1}
                  className="p-2 rounded-lg hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <ChevronLeft className="w-5 h-5 text-gray-500" />
                </button>

                <div className="flex items-center gap-2">
                  {generatePageNumbers(currentPage, totalPages).map((p, i) => (
                    p === '...' ? (
                      <span key={`ellipsis-${i}`} className="text-gray-400">...</span>
                    ) : (
                      <button
                        key={p}
                        onClick={() => goToPage(p)}
                        className={`w-8 h-8 rounded-full text-sm font-medium transition-colors ${
                          currentPage === p 
                            ? 'bg-teal-500 text-white' 
                            : 'text-gray-600 hover:bg-gray-100'
                        }`}
                      >
                        {p}
                      </button>
                    )
                  ))}
                </div>

                <div className="flex items-center gap-4">
                  <span className="text-sm text-gray-500">
                    Showing {(currentPage - 1) * limit + 1} – {Math.min(currentPage * limit, total)} of {total}
                  </span>
                  <button 
                    onClick={() => goToPage(currentPage + 1)}
                    disabled={currentPage >= totalPages}
                    className="p-2 rounded-lg hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <ChevronRight className="w-5 h-5 text-gray-500" />
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      {/* Filter Drawer */}
      <TelegramFilterDrawer 
        open={filterOpen} 
        onClose={() => setFilterOpen(false)} 
      />
      </div>
    </div>
  );
}

function StatCard({ label, value, color }) {
  const colorMap = {
    teal: 'text-teal-600',
    emerald: 'text-emerald-600',
    rose: 'text-rose-600',
  };
  
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-xs text-gray-400">{label}</span>
      <span className={`text-sm font-semibold ${colorMap[color] || colorMap.teal}`}>
        {value}
      </span>
    </div>
  );
}

function EntityRow({ entity, isWatchlisted, onToggleWatchlist }) {
  const navigate = useNavigate();
  
  return (
    <tr 
      className="border-b border-gray-50 hover:bg-gray-50/50 transition-colors cursor-pointer"
      data-testid={`entity-row-${entity.username}`}
      onClick={() => navigate(`/telegram/${entity.username}`)}
    >
      {/* Channel/Group */}
      <td className="px-6 py-4">
        <div className="flex items-center gap-3">
          {/* Watchlist Button */}
          <button
            onClick={(e) => onToggleWatchlist(entity.username, e)}
            className={`p-1.5 rounded-lg transition-all ${
              isWatchlisted 
                ? 'bg-teal-100 text-teal-600 hover:bg-teal-200' 
                : 'bg-gray-100 text-gray-400 hover:bg-gray-200 hover:text-gray-600'
            }`}
            title={isWatchlisted ? 'Remove from feed' : 'Add to feed'}
            data-testid={`watchlist-btn-${entity.username}`}
          >
            {isWatchlisted ? (
              <BookmarkCheck className="w-4 h-4" />
            ) : (
              <Bookmark className="w-4 h-4" />
            )}
          </button>
          
          {entity.avatarUrl ? (
            <img 
              src={`${process.env.REACT_APP_BACKEND_URL}${entity.avatarUrl}`}
              alt={entity.title || entity.username}
              className="w-8 h-8 rounded-full object-cover"
              onError={(e) => {
                e.target.style.display = 'none';
                e.target.nextSibling.style.display = 'flex';
              }}
            />
          ) : null}
          <div 
            className="w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-semibold"
            style={{ 
              backgroundColor: entity.avatarColor,
              display: entity.avatarUrl ? 'none' : 'flex'
            }}
          >
            {entity.title?.substring(0, 2).toUpperCase() || entity.username.substring(0, 2).toUpperCase()}
          </div>
          <span className="font-medium text-gray-900 hover:text-teal-600 transition-colors">
            {entity.title || entity.username}
          </span>
        </div>
      </td>

      {/* Type */}
      <td className="px-4 py-4 text-sm text-gray-600">
        {entity.type}
      </td>

      {/* Sector */}
      <td className="px-4 py-4">
        {entity.sector ? (
          <span 
            className="text-xs font-medium"
            style={{
              color: darkenColor(entity.sectorColor || '#6b7280', 0.3)
            }}
          >
            {entity.sector}
          </span>
        ) : (
          <span className="text-xs text-gray-400">—</span>
        )}
      </td>

      {/* Members */}
      <td className="px-4 py-4 text-sm text-gray-900 text-right font-medium">
        {formatNumber(entity.members)}
      </td>

      {/* Avg Reach */}
      <td className="px-4 py-4 text-sm text-gray-900 text-right font-medium">
        {formatNumber(entity.avgReach)}
      </td>

      {/* Trend Sparkline */}
      <td className="px-4 py-4">
        <div className="flex items-center gap-2">
          <div className="w-20 h-6">
            <Sparkline 
              data={entity.sparkline || []} 
              height={24}
              width={80}
              color={entity.growth7 >= 0 ? '#10b981' : '#ef4444'} 
            />
          </div>
          {/* Growth (7D) */}
          <span className={`text-sm font-medium ${
            entity.growth7 >= 0 ? 'text-emerald-600' : 'text-red-500'
          }`}>
            {entity.growth7 >= 0 ? '+' : ''}{entity.growth7?.toFixed(1) || '0.0'}%
          </span>
        </div>
      </td>

      {/* Activity Badge */}
      <td className="px-4 py-4 text-center">
        <ActivityBadge level={entity.activity || entity.activityLabel} />
      </td>

      {/* Language */}
      <td className="px-4 py-4 text-center">
        <LanguageBadge lang={entity.language} />
      </td>

      {/* Red Flags */}
      <td className="px-4 py-4 text-center">
        <div className="flex items-center justify-center gap-1">
          <span className="text-sm text-gray-700">{entity.redFlags || 0}</span>
          <svg className="w-4 h-4 text-red-400" viewBox="0 0 24 24" fill="currentColor">
            <path d="M4 2v20h2v-8h12l-2-4 2-4H6V2H4z"/>
          </svg>
        </div>
      </td>

      {/* FOMO Score with Quality Signals */}
      <td className="px-6 py-4 text-right">
        <div className="flex items-center justify-end gap-2">
          <span className="text-sm font-semibold text-gray-900">{entity.fomoScore || entity.utilityScore}</span>
          {/* Stars based on utility score (0-5) */}
          <div className="flex items-center">
            {[...Array(entity.stars || Math.min(5, Math.max(0, Math.round((entity.utilityScore || 0) / 20))))].map((_, i) => (
              <Star key={i} className="w-3 h-3 text-amber-400 fill-amber-400" />
            ))}
          </div>
        </div>
      </td>
    </tr>
  );
}

function LanguageBadge({ lang }) {
  const config = {
    'EN': { label: 'EN', color: 'text-blue-700' },
    'RU': { label: 'RU', color: 'text-violet-700' },
    'UA': { label: 'UA', color: 'text-yellow-700' },
  };
  const c = config[lang] || { label: lang || '—', color: 'text-gray-400' };
  return <span className={`text-xs font-medium ${c.color}`}>{c.label}</span>;
}

function ActivityBadge({ level }) {
  const colors = {
    'Very High': 'text-teal-700',
    High: 'text-teal-700',
    Medium: 'text-amber-700',
    Low: 'text-rose-600',
    Dormant: 'text-gray-500',
  };

  return (
    <span className={`text-xs font-medium ${colors[level] || colors.Medium}`}>
      {level || 'Medium'}
    </span>
  );
}

function formatNumber(num) {
  if (num === null || num === undefined) return '—';
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
  if (num >= 1000) return (num / 1000).toFixed(num >= 10000 ? 0 : 1) + 'k';
  return num.toString();
}

function generatePageNumbers(current, total) {
  const pages = [];
  const delta = 2;

  for (let i = 1; i <= total; i++) {
    if (i === 1 || i === total || (i >= current - delta && i <= current + delta)) {
      pages.push(i);
    } else if (pages[pages.length - 1] !== '...') {
      pages.push('...');
    }
  }

  return pages;
}


function TelegramSearchItem({ ch, addingChannel, addedChannel, onAdd }) {
  const isAdded = addedChannel === ch.username;
  return (
    <div className="flex items-center gap-3 px-4 py-2.5 hover:bg-gray-50 transition-colors">
      <div className="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center text-white text-xs font-semibold flex-shrink-0">
        {(ch.title || '?').substring(0, 2).toUpperCase()}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-900 truncate">{ch.title}</p>
        <p className="text-xs text-gray-500">
          @{ch.username}
          {ch.participantsCount > 0 && ` \u2022 ${formatNumber(ch.participantsCount)} members`}
        </p>
      </div>
      {isAdded ? (
        <span className="flex items-center gap-1 text-xs text-teal-600 font-medium" data-testid={`added-${ch.username}`}>
          <Check className="w-4 h-4" /> Added
        </span>
      ) : (
        <button
          onClick={() => onAdd(ch.username)}
          disabled={addingChannel}
          className="flex items-center gap-1 px-3 py-1.5 bg-teal-600 text-white text-xs font-medium rounded-lg hover:bg-teal-700 transition-colors disabled:opacity-50"
          data-testid={`add-channel-btn-${ch.username}`}
        >
          {addingChannel ? (
            <Loader2 className="w-3 h-3 animate-spin" />
          ) : (
            <Plus className="w-3 h-3" />
          )}
          Add
        </button>
      )}
    </div>
  );
}
