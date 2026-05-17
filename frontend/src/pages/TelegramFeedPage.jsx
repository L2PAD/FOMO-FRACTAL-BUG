/**
 * Telegram Feed Page - Newspaper Style
 * Single continuous feed without separate cards
 */
import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  ArrowLeft, 
  Eye, 
  Share2, 
  MessageCircle, 
  ExternalLink, 
  Pin, 
  PinOff,
  Loader2,
  RefreshCw,
  TrendingUp,
  Sparkles,
  ChevronLeft,
  ChevronRight,
  BookmarkX,
  X,
  Check,
  AlertTriangle,
  Zap,
  Activity,
  Bell,
  Flame,
  FileText,
  ChevronDown,
  ChevronUp,
  Image as ImageIcon,
  Filter,
  SlidersHorizontal
} from 'lucide-react';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../components/ui/tooltip';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';

const API_BASE = process.env.REACT_APP_BACKEND_URL || '';
const ACTOR_ID = 'a_public';

export default function TelegramFeedPage() {
  const navigate = useNavigate();
  const [posts, setPosts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [watchlistCount, setWatchlistCount] = useState(0);
  const [dataStale, setDataStale] = useState(false);
  
  const [searchQuery, setSearchQuery] = useState('');
  const [searchActive, setSearchActive] = useState(false);
  const [authorFilter, setAuthorFilter] = useState(null); // { username, title, avatarUrl }
  const [channelSuggestions, setChannelSuggestions] = useState([]);
  const [showChannelDropdown, setShowChannelDropdown] = useState(false);
  const searchInputRef = useRef(null);
  const dropdownRef = useRef(null);
  const debounceRef = useRef(null);
  
  const [topics, setTopics] = useState([]);
  const [topicsLoading, setTopicsLoading] = useState(false);
  const [selectedTopic, setSelectedTopic] = useState(null);
  
  const [feedStats, setFeedStats] = useState(null);
  const [signals, setSignals] = useState([]);
  const [signalsLoading, setSignalsLoading] = useState(false);
  
  const [alerts, setAlerts] = useState([]);
  const [alertsLoading, setAlertsLoading] = useState(false);
  
  const [aiSummary, setAiSummary] = useState(null);
  const [summaryLoading, setSummaryLoading] = useState(false);

  const [signalExpanded, setSignalExpanded] = useState(null);

  // Feed Filters
  const [showFeedFilter, setShowFeedFilter] = useState(false);
  const [feedFilters, setFeedFilters] = useState({
    language: '_all',
    minViews: '',
    period: '7',
    sortBy: 'date',
  });
  const [activeFilterCount, setActiveFilterCount] = useState(0);

  const fetchFeedStats = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/telegram-intel/feed/stats?actorId=${ACTOR_ID}&hours=24`);
      const data = await res.json();
      if (data.ok) {
        setFeedStats(data);
      }
    } catch (err) {
      console.error('Feed stats error:', err);
    }
  }, []);

  const fetchFeed = useCallback(async (pageNum = 1, filters = null) => {
    setLoading(true);
    try {
      const f = filters || feedFilters;
      const params = new URLSearchParams({
        actorId: ACTOR_ID,
        page: String(pageNum),
        limit: '20',
        windowDays: f.period || '7',
      });
      if (f.language && f.language !== '_all') params.set('language', f.language);
      if (f.minViews && parseInt(f.minViews) > 0) params.set('minViews', f.minViews);
      if (f.sortBy && f.sortBy !== 'date') params.set('sortBy', f.sortBy);
      
      const res = await fetch(`${API_BASE}/api/telegram-intel/feed/v2?${params.toString()}`);
      const data = await res.json();
      if (data.ok) {
        setPosts(data.items || []);
        setTotalPages(data.pages || 1);
        setTotal(data.total || 0);
        setWatchlistCount(data.watchlistCount || 0);
        setDataStale(data.dataStale || false);
        setPage(pageNum);
        setSearchActive(false);
        setSelectedTopic(null);
      }
    } catch (err) {
      console.error('Feed error:', err);
    } finally {
      setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const searchFeed = useCallback(async (query, pageNum = 1, username = null) => {
    if (!query.trim() && !username) {
      fetchFeed(1);
      return;
    }
    setLoading(true);
    try {
      const params = new URLSearchParams({ actorId: ACTOR_ID, days: '30', page: String(pageNum), limit: '20' });
      if (query.trim()) params.set('q', query.trim());
      if (username) params.set('username', username);
      
      const res = await fetch(`${API_BASE}/api/telegram-intel/feed/search?${params.toString()}`);
      const data = await res.json();
      if (data.ok) {
        setPosts(data.items || []);
        setTotalPages(data.pages || 1);
        setTotal(data.total || 0);
        setPage(pageNum);
        setSearchActive(true);
      }
    } catch (err) {
      console.error('Search error:', err);
    } finally {
      setLoading(false);
    }
  }, [fetchFeed]);

  const fetchTopics = useCallback(async () => {
    setTopicsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/telegram-intel/topics/momentum?limit=15&hours=24`);
      const data = await res.json();
      if (data.ok) setTopics(data.topics || []);
    } catch (err) {
      console.error('Topics error:', err);
    } finally {
      setTopicsLoading(false);
    }
  }, []);

  const fetchSignals = useCallback(async () => {
    setSignalsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/telegram-intel/signals/cross-channel?window=10080`);
      const data = await res.json();
      if (data.ok) setSignals(data.events || []);
    } catch (err) {
      console.error('Signals error:', err);
    } finally {
      setSignalsLoading(false);
    }
  }, []);

  const fetchAlerts = useCallback(async () => {
    setAlertsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/telegram-intel/alerts?actorId=${ACTOR_ID}&hours=48&limit=10`);
      const data = await res.json();
      if (data.ok) setAlerts(data.alerts || []);
    } catch (err) {
      console.error('Alerts error:', err);
    } finally {
      setAlertsLoading(false);
    }
  }, []);

  const fetchAiSummary = useCallback(async () => {
    setSummaryLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/telegram-intel/feed/summary?hours=24`);
      const data = await res.json();
      if (data.ok) setAiSummary(data);
    } catch (err) {
      console.error('AI Summary error:', err);
    } finally {
      setSummaryLoading(false);
    }
  }, []);

  const togglePin = async (post) => {
    // Enforce max 3 pins
    const currentPinned = posts.filter(p => p.isPinned);
    if (!post.isPinned && currentPinned.length >= 3) {
      return;
    }
    try {
      await fetch(`${API_BASE}/api/telegram-intel/feed/me/pin`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          actorId: ACTOR_ID,
          username: post.username,
          messageId: post.messageId,
          isPinned: !post.isPinned
        })
      });
      setPosts(prev => prev.map(p => 
        p.username === post.username && p.messageId === post.messageId
          ? { ...p, isPinned: !p.isPinned }
          : p
      ));
    } catch (err) {
      console.error('Pin error:', err);
    }
  };

  const markRead = async (post) => {
    if (post.isRead) return;
    try {
      await fetch(`${API_BASE}/api/telegram-intel/feed/me/read`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          actorId: ACTOR_ID,
          username: post.username,
          messageId: post.messageId
        })
      });
      setPosts(prev => prev.map(p => 
        p.username === post.username && p.messageId === post.messageId
          ? { ...p, isRead: true }
          : p
      ));
    } catch (err) {
      console.error('Mark read error:', err);
    }
  };

  const handleTopicClick = (topic) => {
    setSelectedTopic(topic.topic);
    setSearchQuery(topic.topic);
    setSearchActive(true);
    setAuthorFilter(null);
    searchFeed(topic.topic, 1);
  };

  // Autocomplete for channels
  const fetchChannelSuggestions = useCallback(async (query) => {
    if (!query || query.length < 1) {
      setChannelSuggestions([]);
      setShowChannelDropdown(false);
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/api/telegram-intel/channels/autocomplete?q=${encodeURIComponent(query)}&limit=6`);
      const data = await res.json();
      if (data.ok && data.suggestions) {
        setChannelSuggestions(data.suggestions);
        setShowChannelDropdown(data.suggestions.length > 0);
      }
    } catch (err) {
      console.error('[Autocomplete] error:', err);
    }
  }, []);

  const handleSearchInputChange = (e) => {
    const val = e.target.value;
    setSearchQuery(val);
    if (!authorFilter) {
      if (val.trim().length >= 2) {
        setShowChannelDropdown(true);
      } else {
        setShowChannelDropdown(false);
      }
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => fetchChannelSuggestions(val), 200);
    }
  };

  const selectChannel = (ch) => {
    setAuthorFilter(ch);
    setSearchQuery('');
    setShowChannelDropdown(false);
    setChannelSuggestions([]);
    setSelectedTopic(null);
    // Fetch all posts from this author
    searchFeed('', 1, ch.username);
  };

  // Click outside to close dropdown
  useEffect(() => {
    const handler = (e) => {
      if (
        dropdownRef.current && !dropdownRef.current.contains(e.target) &&
        searchInputRef.current && !searchInputRef.current.contains(e.target)
      ) {
        setShowChannelDropdown(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const handleSearch = (e) => {
    e.preventDefault();
    setShowChannelDropdown(false);
    if (searchQuery.trim()) {
      searchFeed(searchQuery, 1, authorFilter?.username || null);
    } else if (authorFilter) {
      searchFeed('', 1, authorFilter.username);
    }
  };

  const clearSearch = () => {
    setSearchQuery('');
    setSearchActive(false);
    setSelectedTopic(null);
    setAuthorFilter(null);
    setChannelSuggestions([]);
    setShowChannelDropdown(false);
    fetchFeed(1);
  };

  const clearAuthor = () => {
    setAuthorFilter(null);
    setSearchQuery('');
    setSearchActive(false);
    fetchFeed(1);
  };

  const refreshAll = () => {
    fetchFeed(1);
    fetchTopics();
    fetchSignals();
    fetchAlerts();
    fetchAiSummary();
  };

  const applyFeedFilters = (newFilters) => {
    setFeedFilters(newFilters);
    const count = Object.entries(newFilters).filter(
      ([k, v]) => v && v !== '_all' && v !== '' && !(k === 'period' && v === '7') && !(k === 'sortBy' && v === 'date')
    ).length;
    setActiveFilterCount(count);
    setShowFeedFilter(false);
    fetchFeed(1, newFilters);
  };

  const resetFeedFilters = () => {
    const defaults = { language: '_all', minViews: '', period: '7', sortBy: 'date' };
    setFeedFilters(defaults);
    setActiveFilterCount(0);
    setShowFeedFilter(false);
    fetchFeed(1, defaults);
  };

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    fetchFeed(1);
    fetchTopics();
    fetchSignals();
    fetchAlerts();
    fetchAiSummary();
    fetchFeedStats();
  }, []);

  return (
    <TooltipProvider delayDuration={300}>
    <div className="min-h-screen bg-[#f5f5f5]">
      {/* Header */}
      <header className="bg-white sticky top-0 z-30 border-b border-gray-200">
        <div className="max-w-[1800px] mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <button onClick={() => navigate('/telegram')} className="p-2 hover:bg-gray-100 rounded-lg" data-testid="back-btn">
                <ArrowLeft className="w-5 h-5 text-gray-600" />
              </button>
              <div>
                <h1 className="text-xl font-bold text-gray-900">Telegram Intelligence</h1>
                <div className="flex items-center gap-3 text-sm text-gray-500">
                  <span>{watchlistCount} channels</span>
                  <span>•</span>
                  <span>{total} posts</span>
                  {dataStale && <span className="text-amber-600 flex items-center gap-1"><AlertTriangle className="w-3 h-3" />Stale</span>}
                </div>
              </div>
            </div>
            
            <form onSubmit={handleSearch} className="flex-1 max-w-xl mx-8">
              <div className="relative" ref={searchInputRef}>
                <div className="flex items-center w-full bg-gray-50 rounded-full focus-within:bg-white focus-within:shadow-sm transition-all">
                  {/* Author filter chip */}
                  {authorFilter && (
                    <div className="flex items-center gap-1.5 ml-3 px-2 py-1 bg-blue-100 text-blue-700 rounded-full text-xs font-medium flex-shrink-0" data-testid="author-filter-chip">
                      {authorFilter.avatarUrl ? (
                        <img src={`${API_BASE}${authorFilter.avatarUrl}`} alt="" className="w-4 h-4 rounded-full object-cover"
                          onError={(e) => { e.target.style.display = 'none'; }} />
                      ) : null}
                      <span>@{authorFilter.username}</span>
                      <button type="button" onClick={clearAuthor} className="ml-0.5 hover:text-blue-900">
                        <X className="w-3 h-3" />
                      </button>
                    </div>
                  )}
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={handleSearchInputChange}
                    onFocus={() => { if (channelSuggestions.length > 0 && !authorFilter) setShowChannelDropdown(true); }}
                    placeholder={authorFilter ? "Search within channel..." : "Search channels or keywords..."}
                    className="flex-1 px-4 py-2.5 bg-transparent text-gray-900 placeholder-gray-400 outline-none text-sm rounded-full"
                    data-testid="search-input"
                  />
                  {(searchQuery || searchActive || authorFilter) && (
                    <button type="button" onClick={clearSearch} className="px-3">
                      <X className="w-4 h-4 text-gray-400" />
                    </button>
                  )}
                </div>

                {/* Search dropdown: post content search + channel filter */}
                {showChannelDropdown && searchQuery.trim().length >= 2 && !authorFilter && (
                  <div 
                    ref={dropdownRef}
                    className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-50 overflow-hidden"
                    data-testid="channel-suggestions"
                  >
                    {/* Primary: search posts by content */}
                    <button
                      type="button"
                      onClick={() => { setShowChannelDropdown(false); searchFeed(searchQuery, 1); }}
                      className="w-full flex items-center gap-3 px-4 py-3 hover:bg-teal-50 transition-colors text-left border-b border-gray-100"
                      data-testid="search-posts-btn"
                    >
                      <FileText className="w-4 h-4 text-teal-600 flex-shrink-0" />
                      <span className="text-sm text-gray-900">
                        Search posts containing <strong className="text-teal-700">"{searchQuery}"</strong>
                      </span>
                    </button>

                    {/* Secondary: filter by channel */}
                    {channelSuggestions.length > 0 && (
                      <>
                        <div className="px-3 py-1.5 text-[10px] uppercase tracking-wide text-gray-400 font-medium">
                          Or filter by channel
                        </div>
                        {channelSuggestions.map((ch) => (
                          <button
                            key={ch.username}
                            type="button"
                            onClick={() => selectChannel(ch)}
                            className="w-full flex items-center gap-3 px-3 py-2 hover:bg-blue-50 transition-colors text-left"
                            data-testid={`channel-suggest-${ch.username}`}
                          >
                            {ch.avatarUrl ? (
                              <img src={`${API_BASE}${ch.avatarUrl}`} alt="" className="w-7 h-7 rounded-full object-cover flex-shrink-0"
                                onError={(e) => { e.target.style.display = 'none'; e.target.nextSibling.style.display = 'flex'; }} />
                            ) : null}
                            <div 
                              className={`w-7 h-7 rounded-full items-center justify-center text-white text-[10px] font-semibold flex-shrink-0 ${ch.avatarUrl ? 'hidden' : 'flex'}`}
                              style={{ backgroundColor: ch.sectorColor || '#6366f1' }}
                            >
                              {(ch.title || ch.username).substring(0, 2).toUpperCase()}
                            </div>
                            <div className="flex-1 min-w-0">
                              <p className="text-sm font-medium text-gray-900 truncate">{ch.title || ch.username}</p>
                              <p className="text-xs text-gray-500">@{ch.username}</p>
                            </div>
                          </button>
                        ))}
                      </>
                    )}
                  </div>
                )}
              </div>
            </form>
            
            <div className="flex items-center gap-2">
              <button 
                onClick={() => setShowFeedFilter(!showFeedFilter)} 
                className="relative flex items-center gap-2 px-4 py-2 border border-gray-200 hover:bg-gray-50 rounded-lg text-sm font-medium text-gray-700 transition-colors"
                data-testid="feed-filter-btn"
              >
                <SlidersHorizontal className="w-4 h-4" />
                Filter
                {activeFilterCount > 0 && (
                  <span className="absolute -top-1.5 -right-1.5 w-5 h-5 bg-teal-600 text-white text-[10px] font-bold rounded-full flex items-center justify-center">
                    {activeFilterCount}
                  </span>
                )}
              </button>
              <button onClick={refreshAll} disabled={loading} className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium" data-testid="refresh-btn">
                <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                Refresh
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Feed Filter Drawer */}
      {showFeedFilter && (
        <FeedFilterDrawer
          filters={feedFilters}
          onApply={applyFeedFilters}
          onReset={resetFeedFilters}
          onClose={() => setShowFeedFilter(false)}
        />
      )}

      <main className="max-w-[1800px] mx-auto px-6 py-6">
        <div className="grid grid-cols-12 gap-6">
          {/* Left Sidebar */}
          <aside className="col-span-3 space-y-4">
            <SidebarCard 
              title="AI Feed Summary" 
              icon={<FileText className="w-4 h-4 text-blue-500" />} 
              onRefresh={fetchAiSummary} 
              loading={summaryLoading}
              tooltip="AI analysis of recent posts from the last 24 hours. Highlights key topics, trends, and market sentiment."
            >
              {aiSummary?.summary ? (
                <div>
                  <p className="text-sm text-gray-700 leading-relaxed">{aiSummary.summary}</p>
                  <p className="text-xs text-gray-400 mt-2">{aiSummary.postsAnalyzed || 0} posts analyzed</p>
                </div>
              ) : (
                <p className="text-sm text-gray-400 text-center py-2">No summary available</p>
              )}
            </SidebarCard>

            <SidebarCard 
              title="Cross-Channel Signals" 
              icon={<Zap className="w-4 h-4 text-amber-500" />} 
              onRefresh={fetchSignals} 
              loading={signalsLoading}
              tooltip="Detects topics and entities mentioned across multiple channels simultaneously. Strong signal indicates important news."
            >
              {signals.length === 0 ? (
                <p className="text-sm text-gray-400 text-center py-2">No active signals</p>
              ) : (
                <div className="space-y-1" data-testid="cross-channel-signals">
                  {signals.map((s, i) => (
                    <button 
                      key={i}
                      onClick={() => setSignalExpanded(signalExpanded === i ? null : i)}
                      className="w-full text-left p-2 rounded-lg transition-all outline-none hover:bg-gray-50"
                      data-testid={`signal-item-${i}`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-gray-900 text-sm truncate">{s.entity || s.topic}</span>
                        <div className="flex items-center gap-1 flex-shrink-0">
                          {(s.isStrongSignal || s.channelCount >= 5) && <Flame className="w-3.5 h-3.5 text-amber-500" />}
                          {signalExpanded === i ? <ChevronUp className="w-3.5 h-3.5 text-gray-400" /> : <ChevronDown className="w-3.5 h-3.5 text-gray-400" />}
                        </div>
                      </div>
                      <p className="text-xs text-gray-500">{s.channelCount} ch • {s.mentions} mentions</p>
                      
                      {signalExpanded === i && (
                        <div className="mt-2 pt-2 border-t border-gray-200 space-y-1.5" onClick={(e) => e.stopPropagation()}>
                          <p className="text-[10px] uppercase tracking-wide text-gray-400 font-medium">Channels mentioning</p>
                          <div className="flex flex-wrap gap-1">
                            {(s.channels || []).map((ch) => (
                              <a 
                                key={ch}
                                href={`/telegram/${ch}`}
                                className="text-xs px-2 py-0.5 bg-white border border-gray-200 rounded-full hover:border-blue-300 hover:text-blue-600 transition-colors"
                                data-testid={`signal-channel-${ch}`}
                              >
                                @{ch}
                              </a>
                            ))}
                          </div>
                          {s.totalViews > 0 && (
                            <p className="text-xs text-gray-500 flex items-center gap-1 mt-1">
                              <Eye className="w-3 h-3" /> {(s.totalViews || 0).toLocaleString()} total views
                            </p>
                          )}
                          <button
                            onClick={(e) => { e.stopPropagation(); setSearchQuery(s.entity || s.topic); searchFeed(s.entity || s.topic, 1); setSignalExpanded(null); }}
                            className="text-xs text-blue-600 hover:text-blue-800 font-medium mt-1"
                          >
                            Search in feed
                          </button>
                        </div>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </SidebarCard>

            <SidebarCard 
              title="Recent Alerts" 
              icon={<Bell className="w-4 h-4 text-rose-500" />}
              tooltip="Notifications about unusual activity: viral posts, sudden growth, new channels."
            >
              {alerts.length === 0 ? (
                <p className="text-sm text-gray-400 text-center py-2">No alerts yet</p>
              ) : (
                <div className="space-y-2">
                  {alerts.slice(0, 5).map((a, i) => (
                    <div key={i} className="p-2">
                      <p className="text-sm text-gray-900 font-medium truncate">{a.title}</p>
                      <p className="text-xs text-gray-500 truncate">{a.description || a.message}</p>
                    </div>
                  ))}
                </div>
              )}
            </SidebarCard>
          </aside>

          {/* Main Feed - Newspaper Style */}
          <div className="col-span-6">
            {(searchActive || selectedTopic || authorFilter) && (
              <div className="mb-4 flex items-center gap-2 px-4 py-2 bg-blue-50 rounded-lg">
                <span className="text-sm text-blue-700 font-medium">
                  {authorFilter && !searchQuery ? `Channel: @${authorFilter.username}` : 
                   selectedTopic ? `Topic: ${selectedTopic}` : 
                   authorFilter ? `@${authorFilter.username}: "${searchQuery}"` :
                   `Search: "${searchQuery}"`}
                </span>
                <span className="text-sm text-blue-500">• {total} results</span>
                <button onClick={clearSearch} className="ml-auto text-sm text-blue-600 hover:text-blue-800 font-medium">Clear</button>
              </div>
            )}
            
            {loading && posts.length === 0 ? (
              <div className="flex items-center justify-center h-64">
                <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
              </div>
            ) : posts.length === 0 ? (
              <div className="text-center py-16 bg-white rounded-xl">
                <BookmarkX className="w-16 h-16 mx-auto text-gray-300 mb-4" />
                <p className="text-gray-600 font-medium">No posts in your feed</p>
                <p className="text-sm text-gray-400 mt-1">Add channels to your watchlist</p>
              </div>
            ) : (
              <>
                {/* Pinned posts - fixed at top */}
                {(() => {
                  const pinnedPosts = posts.filter(p => p.isPinned);
                  if (pinnedPosts.length === 0) return null;
                  return (
                    <div className="bg-white rounded-xl overflow-hidden mb-3 border border-blue-100" data-testid="pinned-section">
                      <div className="px-4 py-2 bg-blue-50 border-b border-blue-100 flex items-center gap-2">
                        <Pin className="w-3.5 h-3.5 text-blue-500" />
                        <span className="text-xs font-medium text-blue-700">Pinned ({pinnedPosts.length}/3)</span>
                      </div>
                      {pinnedPosts.map((post, index) => (
                        <FeedItem 
                          key={`pin-${post.username}-${post.messageId}`} 
                          post={post}
                          onPin={() => togglePin(post)}
                          onRead={() => markRead(post)}
                          isFirst={index === 0}
                          isLast={index === pinnedPosts.length - 1}
                        />
                      ))}
                    </div>
                  );
                })()}

                {/* Regular feed */}
                <div className="bg-white rounded-xl overflow-hidden">
                  {posts.filter(p => !p.isPinned).map((post, index, arr) => (
                    <FeedItem 
                      key={`${post.username}-${post.messageId}`} 
                      post={post}
                      onPin={() => togglePin(post)}
                      onRead={() => markRead(post)}
                      isFirst={index === 0}
                      isLast={index === arr.length - 1}
                    />
                  ))}
                </div>
              </>
            )}
            
            {totalPages > 1 && (
              <div className="flex items-center justify-between mt-4 px-4 py-3 bg-white rounded-xl">
                <button 
                  onClick={() => searchActive ? searchFeed(searchQuery, page - 1, authorFilter?.username) : fetchFeed(page - 1)}
                  disabled={page <= 1 || loading}
                  className="flex items-center gap-1 px-4 py-2 text-sm text-gray-600 hover:text-gray-900 disabled:opacity-30"
                >
                  <ChevronLeft className="w-4 h-4" /> Previous
                </button>
                <span className="text-sm text-gray-500">Page {page} of {totalPages}</span>
                <button 
                  onClick={() => searchActive ? searchFeed(searchQuery, page + 1, authorFilter?.username) : fetchFeed(page + 1)}
                  disabled={page >= totalPages || loading}
                  className="flex items-center gap-1 px-4 py-2 text-sm text-gray-600 hover:text-gray-900 disabled:opacity-30"
                >
                  Next <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            )}
          </div>
          
          {/* Right Sidebar */}
          <aside className="col-span-3 space-y-4">
            <SidebarCard 
              title="Topic Momentum" 
              icon={<TrendingUp className="w-4 h-4 text-emerald-500" />} 
              onRefresh={fetchTopics} 
              loading={topicsLoading}
              tooltip="Trending topics extracted from posts in the last 6 hours. Multiplier shows trend strength. Click to search."
            >
              {topics.length === 0 ? (
                <p className="text-sm text-gray-400 text-center py-2">No trending topics</p>
              ) : (
                <div className="space-y-1">
                  {topics.slice(0, 10).map((t, i) => (
                    <button key={t.topic} onClick={() => handleTopicClick(t)} className={`w-full flex items-center justify-between p-2 rounded-lg hover:bg-gray-50`}>
                      <div className="flex items-center gap-2">
                        {t.isSpiking && <Flame className="w-3 h-3 text-orange-500" />}
                        <span className={`text-sm ${t.isSpiking ? 'text-orange-600 font-medium' : 'text-gray-700'}`}>{t.topic}</span>
                      </div>
                      <span className={`text-xs px-1.5 py-0.5 rounded ${t.momentum > 5 ? 'text-orange-600' : t.momentum > 2 ? 'text-emerald-600' : 'text-gray-500'}`}>
                        {t.momentum}x
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </SidebarCard>

            <div className="bg-white rounded-xl p-4">
              <div className="flex items-center gap-2 mb-3">
                <Activity className="w-4 h-4 text-violet-500" />
                <Tooltip>
                  <TooltipTrigger asChild>
                    <span className="font-medium text-gray-900 text-sm cursor-default">Feed Stats</span>
                  </TooltipTrigger>
                  <TooltipContent side="top" className="max-w-[200px] text-center">
                    <p>Your feed statistics: posts in 24h, media count, pinned posts, and strong signals.</p>
                  </TooltipContent>
                </Tooltip>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 text-center">
                  <p className="text-2xl font-bold text-gray-900">{feedStats?.postsToday || 0}</p>
                  <p className="text-xs text-gray-500">Posts 24h</p>
                </div>
                <div className="p-3 text-center">
                  <p className="text-2xl font-bold text-gray-900">{feedStats?.mediaCount || 0}</p>
                  <p className="text-xs text-gray-500">Media</p>
                </div>
                <div className="p-3 text-center">
                  <p className="text-2xl font-bold text-gray-900">{feedStats?.pinnedCount || 0}</p>
                  <p className="text-xs text-gray-500">Pinned</p>
                </div>
                <div className="p-3 text-center">
                  <p className="text-2xl font-bold text-gray-900">{signals.filter(s => (s.isStrongSignal || s.channelCount >= 5)).length}</p>
                  <p className="text-xs text-gray-500">Signals</p>
                </div>
              </div>
            </div>
          </aside>
        </div>
      </main>
    </div>
    </TooltipProvider>
  );
}

// Sidebar Card Component
function SidebarCard({ title, icon, children, onRefresh, loading, tooltip }) {
  return (
    <div className="bg-white rounded-xl">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
        <div className="flex items-center gap-2">
          {icon}
          {tooltip ? (
            <Tooltip>
              <TooltipTrigger asChild>
                <span className="font-medium text-gray-900 text-sm cursor-default">{title}</span>
              </TooltipTrigger>
              <TooltipContent side="top" className="max-w-[220px] text-center">
                <p>{tooltip}</p>
              </TooltipContent>
            </Tooltip>
          ) : (
            <span className="font-medium text-gray-900 text-sm">{title}</span>
          )}
        </div>
        {onRefresh && (
          <button onClick={onRefresh} className="p-1 hover:bg-gray-100 rounded">
            <RefreshCw className={`w-3.5 h-3.5 text-gray-400 ${loading ? 'animate-spin' : ''}`} />
          </button>
        )}
      </div>
      <div className="p-3">{children}</div>
    </div>
  );
}

// Feed Item - Part of continuous feed
function FeedItem({ post, onPin, onRead, isFirst, isLast }) {
  const [expanded, setExpanded] = useState(false);
  const [imageLoaded, setImageLoaded] = useState(false);
  const text = post.text || '';
  const isLong = text.length > 400;
  const displayText = isLong && !expanded ? text.slice(0, 400) + '...' : text;
  
  const renderText = (text) => {
    if (!text) return null;
    let processed = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    processed = processed.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" class="text-blue-600 hover:underline">$1</a>');
    processed = processed.replace(/(?<!href="|">)(https?:\/\/[^\s<&]+)/g, '<a href="$1" target="_blank" class="text-blue-600 hover:underline break-all">$1</a>');
    processed = processed.replace(/\n/g, '<br/>');
    return <div className="text-gray-700 text-sm leading-relaxed" dangerouslySetInnerHTML={{ __html: processed }} />;
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '';
    try {
      const date = new Date(dateStr);
      const now = new Date();
      const diff = now - date;
      if (diff < 60000) return 'Just now';
      if (diff < 3600000) return `${Math.floor(diff / 60000)}m`;
      if (diff < 86400000) return `${Math.floor(diff / 3600000)}h`;
      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    } catch { return ''; }
  };

  const formatNumber = (num) => {
    if (!num) return '0';
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toString();
  };

  const mediaUrl = post.media?.url ? `${API_BASE}/api/telegram-intel/media/${post.username}/${post.messageId}.jpg` : null;

  return (
    <article 
      className={`${post.isRead ? 'opacity-50' : ''} ${!isLast ? 'border-b border-gray-100' : ''}`}
      onClick={onRead}
      data-testid={`post-${post.messageId}`}
    >
      <div className="px-5 py-4">
        {/* Status badges */}
        {(post.isPinned || post.pinnedInChannel || post.isAnomaly || (post.isCluster && post.clusterSize > 1)) && (
          <div className="flex items-center gap-3 mb-3 text-xs">
            {post.pinnedInChannel && (
              <span className="flex items-center gap-1 text-amber-700 bg-amber-50 px-2 py-0.5 rounded-full font-medium" data-testid={`pinned-channel-${post.messageId}`}>
                <Pin className="w-3 h-3" />Pinned in channel
              </span>
            )}
            {post.isPinned && !post.pinnedInChannel && <span className="flex items-center gap-1 text-blue-600"><Pin className="w-3 h-3" />Pinned</span>}
            {post.isAnomaly && <span className="flex items-center gap-1 text-orange-600"><AlertTriangle className="w-3 h-3" />Unusual</span>}
            {post.isCluster && post.clusterSize > 1 && <span className="flex items-center gap-1 text-violet-600"><Sparkles className="w-3 h-3" />{post.clusterSize} channels</span>}
          </div>
        )}

        {/* Header */}
        <div className="flex items-start gap-3 mb-3">
          {post.channelAvatar ? (
            <img src={`${API_BASE}${post.channelAvatar}`} alt="" className="w-10 h-10 rounded-full object-cover"
              onError={(e) => { e.target.style.display = 'none'; e.target.nextSibling.style.display = 'flex'; }} />
          ) : null}
          <div className={`w-10 h-10 rounded-full items-center justify-center text-white text-xs font-semibold ${post.channelAvatar ? 'hidden' : 'flex'}`}
            style={{ backgroundColor: post.channelSectorColor || '#6366f1' }}>
            {post.channelTitle?.substring(0, 2).toUpperCase() || 'CH'}
          </div>
          
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <a href={`/telegram/${post.username}`} className="font-semibold text-gray-900 hover:text-blue-600" onClick={(e) => e.stopPropagation()}>
                {post.channelTitle || post.username}
              </a>
              {post.feedScore > 20 && (
                <span className="px-1.5 py-0.5 bg-orange-100 text-orange-600 rounded text-[10px] font-medium flex items-center gap-0.5">
                  <Flame className="w-2.5 h-2.5" />Hot
                </span>
              )}
            </div>
            <p className="text-xs text-gray-500">@{post.username} · {formatDate(post.date)}</p>
          </div>
          
          <div className="flex items-center gap-1">
            <button onClick={(e) => { e.stopPropagation(); onPin(); }}
              className={`p-1.5 rounded ${post.isPinned ? 'text-blue-600' : 'text-gray-400 hover:text-gray-600'}`}>
              {post.isPinned ? <PinOff className="w-4 h-4" /> : <Pin className="w-4 h-4" />}
            </button>
            <a href={`https://t.me/${post.username}/${post.messageId}`} target="_blank" rel="noopener noreferrer"
              className="p-1.5 text-gray-400 hover:text-gray-600" onClick={(e) => e.stopPropagation()}>
              <ExternalLink className="w-4 h-4" />
            </a>
          </div>
        </div>

        {/* Content */}
        <div className="mb-3">
          {renderText(displayText)}
          {isLong && (
            <button onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }} className="text-xs text-blue-600 hover:text-blue-800 mt-1 font-medium">
              {expanded ? 'Show less' : 'Show more'}
            </button>
          )}
        </div>

        {/* Media Image */}
        {mediaUrl && (
          <div className="mb-3 rounded-lg overflow-hidden bg-gray-50" data-testid={`media-${post.messageId}`}>
            <img 
              src={mediaUrl} 
              alt="" 
              className={`w-full h-auto max-h-96 object-cover transition-opacity duration-300 ${imageLoaded ? 'opacity-100' : 'opacity-0'}`} 
              loading="lazy"
              onLoad={() => setImageLoaded(true)}
              onError={(e) => { e.target.parentElement.style.display = 'none'; }} 
            />
            {!imageLoaded && (
              <div className="flex items-center justify-center h-48 text-gray-400">
                <ImageIcon className="w-8 h-8" />
              </div>
            )}
          </div>
        )}

        {post.hasMedia && !mediaUrl && (
          <div className="mb-3 rounded-lg overflow-hidden bg-gradient-to-br from-gray-50 to-gray-100 border border-gray-100 p-4 flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center flex-shrink-0">
              <ImageIcon className="w-5 h-5 text-blue-400" />
            </div>
            <div>
              <p className="text-sm font-medium text-gray-700">Media attached</p>
              <a href={`https://t.me/${post.username}/${post.messageId}`} target="_blank" rel="noopener noreferrer" 
                className="text-xs text-blue-500 hover:text-blue-700" onClick={(e) => e.stopPropagation()}>
                View in Telegram
              </a>
            </div>
          </div>
        )}

        {/* Stats - original design + reactions */}
        <div className="flex items-center gap-4 text-xs text-gray-500">
          <span className="flex items-center gap-1"><Eye className="w-3.5 h-3.5" />{formatNumber(post.views)}</span>
          <span className="flex items-center gap-1"><Share2 className="w-3.5 h-3.5" />{formatNumber(post.forwards)}</span>
          {post.replies > 0 && <span className="flex items-center gap-1"><MessageCircle className="w-3.5 h-3.5" />{formatNumber(post.replies)}</span>}
          {/* Reactions - top 3 emoji */}
          {post.reactions?.total > 0 && post.reactions.top?.slice(0, 3).map((r, i) => (
            <span key={i} className="flex items-center gap-0.5">
              <span>{r.emoji}</span>
              <span>{formatNumber(r.count)}</span>
            </span>
          ))}
          {post.reactions?.extraCount > 0 && <span className="text-gray-400">(+{post.reactions.extraCount})</span>}
          {/* Anomaly badge */}
          {post.feedScore > 200 && <span className="px-1.5 py-0.5 bg-orange-100 text-orange-600 rounded text-[10px] font-medium">Spike</span>}
          <span className="ml-auto text-gray-400">Score: {post.feedScore?.toFixed(1) || 0}</span>
          {post.isRead && <Check className="w-3.5 h-3.5 text-green-500" />}
        </div>
      </div>
    </article>
  );
}


function FeedFilterDrawer({ filters, onApply, onReset, onClose }) {
  const [local, setLocal] = useState({ ...filters });

  const update = (key, val) => setLocal(prev => ({ ...prev, [key]: val }));

  return (
    <>
      <div className="fixed inset-0 bg-black/20 z-40" onClick={onClose} />
      <div className="fixed right-0 top-0 h-full w-[380px] bg-white shadow-xl z-50 flex flex-col" data-testid="feed-filter-drawer">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">Feed Filters</h2>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-gray-100">
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
          {/* Language */}
          <div>
            <label className="text-sm font-medium text-gray-700 mb-2 block">Language</label>
            <Select value={local.language} onValueChange={(v) => update('language', v)}>
              <SelectTrigger className="w-full border-gray-200 bg-white rounded-lg h-10 text-sm">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="rounded-lg border-gray-200 bg-white shadow-lg">
                <SelectItem value="_all">All Languages</SelectItem>
                <SelectItem value="EN">English</SelectItem>
                <SelectItem value="RU">Russian</SelectItem>
                <SelectItem value="UA">Ukrainian</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Time Period */}
          <div>
            <label className="text-sm font-medium text-gray-700 mb-2 block">Time Period</label>
            <Select value={local.period} onValueChange={(v) => update('period', v)}>
              <SelectTrigger className="w-full border-gray-200 bg-white rounded-lg h-10 text-sm">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="rounded-lg border-gray-200 bg-white shadow-lg">
                <SelectItem value="1">Last 24 Hours</SelectItem>
                <SelectItem value="3">Last 3 Days</SelectItem>
                <SelectItem value="7">Last 7 Days</SelectItem>
                <SelectItem value="14">Last 14 Days</SelectItem>
                <SelectItem value="30">Last 30 Days</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Min Views */}
          <div>
            <label className="text-sm font-medium text-gray-700 mb-2 block">Minimum Views</label>
            <input
              type="number"
              value={local.minViews}
              onChange={(e) => update('minViews', e.target.value)}
              placeholder="e.g. 1000"
              min="0"
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-100 focus:border-teal-400"
            />
          </div>

          {/* Sort By */}
          <div>
            <label className="text-sm font-medium text-gray-700 mb-2 block">Sort By</label>
            <Select value={local.sortBy} onValueChange={(v) => update('sortBy', v)}>
              <SelectTrigger className="w-full border-gray-200 bg-white rounded-lg h-10 text-sm">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="rounded-lg border-gray-200 bg-white shadow-lg">
                <SelectItem value="date">Newest First</SelectItem>
                <SelectItem value="views">Most Views</SelectItem>
                <SelectItem value="forwards">Most Forwards</SelectItem>
                <SelectItem value="reactions">Most Reactions</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-gray-200 bg-gray-50">
          <button onClick={onReset} className="flex items-center gap-2 px-4 py-2 text-sm text-gray-600 hover:text-gray-900">
            <RefreshCw className="w-4 h-4" />
            Reset
          </button>
          <button
            onClick={() => onApply(local)}
            className="px-6 py-2 bg-teal-600 text-white rounded-lg text-sm font-medium hover:bg-teal-700 transition-colors"
            data-testid="apply-feed-filters-btn"
          >
            Apply Filters
          </button>
        </div>
      </div>
    </>
  );
}
