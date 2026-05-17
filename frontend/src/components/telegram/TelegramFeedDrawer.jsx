/**
 * Telegram Feed Drawer
 * Displays aggregated news feed from watchlisted channels
 */
import { useState, useEffect, useCallback } from 'react';
import { X, Rss, ExternalLink, Eye, Share2, MessageCircle, ChevronLeft, ChevronRight, Loader2, BookmarkX, RefreshCw, Sparkles } from 'lucide-react';

const API_BASE = process.env.REACT_APP_BACKEND_URL || '';

export default function TelegramFeedDrawer({ open, onClose }) {
  const [posts, setPosts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [watchlistCount, setWatchlistCount] = useState(0);
  const [error, setError] = useState(null);
  
  // AI Summary state
  const [aiSummary, setAiSummary] = useState(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [showSummary, setShowSummary] = useState(true);

  const fetchFeed = useCallback(async (pageNum = 1) => {
    setLoading(true);
    setError(null);
    
    try {
      const res = await fetch(`${API_BASE}/api/telegram-intel/feed?page=${pageNum}&limit=20`);
      const data = await res.json();
      
      if (data.ok) {
        setPosts(data.items || []);
        setTotalPages(data.pages || 1);
        setTotal(data.total || 0);
        setWatchlistCount(data.watchlistCount || 0);
        setPage(pageNum);
      } else {
        setError(data.error || 'Failed to load feed');
      }
    } catch (err) {
      setError('Network error');
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchAiSummary = useCallback(async () => {
    setSummaryLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/telegram-intel/feed/summary?hours=24`);
      const data = await res.json();
      if (data.ok) {
        setAiSummary(data);
      }
    } catch (err) {
      console.error('AI Summary error:', err);
    } finally {
      setSummaryLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) {
      fetchFeed(1);
      fetchAiSummary();
    }
  }, [open, fetchFeed, fetchAiSummary]);

  if (!open) return null;

  return (
    <>
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-black/40 z-40 backdrop-blur-sm"
        onClick={onClose}
      />
      
      {/* Drawer */}
      <div className="fixed right-0 top-0 h-full w-[520px] bg-white shadow-2xl z-50 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-gradient-to-r from-teal-50 to-white">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-teal-100 flex items-center justify-center">
              <Rss className="w-5 h-5 text-teal-600" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-gray-900">News Feed</h2>
              <p className="text-xs text-gray-500">
                {watchlistCount} channel{watchlistCount !== 1 ? 's' : ''} • {total} posts
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button 
              onClick={() => fetchFeed(page)}
              className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
              title="Refresh"
            >
              <RefreshCw className={`w-4 h-4 text-gray-500 ${loading ? 'animate-spin' : ''}`} />
            </button>
            <button 
              onClick={onClose}
              className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
            >
              <X className="w-5 h-5 text-gray-500" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto">
          {/* AI Summary Section */}
          {showSummary && watchlistCount > 0 && (
            <div className="mx-4 mt-4 mb-2 p-4 bg-gradient-to-r from-violet-50 to-purple-50 rounded-xl border border-violet-100">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-violet-500" />
                  <span className="text-sm font-semibold text-violet-700">AI Summary</span>
                  <span className="text-xs text-violet-400">Last 24h</span>
                </div>
                <button 
                  onClick={() => setShowSummary(false)}
                  className="p-1 hover:bg-violet-100 rounded transition-colors"
                >
                  <X className="w-3 h-3 text-violet-400" />
                </button>
              </div>
              {summaryLoading ? (
                <div className="flex items-center gap-2 text-sm text-violet-500">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Analyzing posts...</span>
                </div>
              ) : aiSummary?.summary ? (
                <p className="text-sm text-gray-700 leading-relaxed">{aiSummary.summary}</p>
              ) : (
                <p className="text-sm text-gray-500 italic">Add channels to get AI summary</p>
              )}
              {aiSummary?.postsAnalyzed > 0 && (
                <p className="text-xs text-violet-400 mt-2">
                  Based on {aiSummary.postsAnalyzed} posts from {aiSummary.channelsCount} channels
                </p>
              )}
            </div>
          )}
          
          {loading && posts.length === 0 ? (
            <div className="flex items-center justify-center h-64">
              <Loader2 className="w-8 h-8 text-teal-500 animate-spin" />
            </div>
          ) : error ? (
            <div className="p-6 text-center">
              <p className="text-red-500 mb-4">{error}</p>
              <button 
                onClick={() => fetchFeed(1)}
                className="px-4 py-2 bg-red-100 text-red-700 rounded-lg text-sm hover:bg-red-200"
              >
                Retry
              </button>
            </div>
          ) : posts.length === 0 ? (
            <div className="p-8 text-center">
              <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-gray-100 flex items-center justify-center">
                <BookmarkX className="w-8 h-8 text-gray-400" />
              </div>
              <p className="text-gray-600 font-medium mb-2">No posts in your feed</p>
              <p className="text-sm text-gray-500">
                Add channels to your watchlist to see their posts here
              </p>
            </div>
          ) : (
            <div className="divide-y divide-gray-100">
              {posts.map((post) => (
                <FeedPost key={`${post.username}-${post.messageId}`} post={post} />
              ))}
            </div>
          )}
        </div>

        {/* Pagination Footer */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-6 py-3 border-t border-gray-200 bg-gray-50">
            <button 
              onClick={() => fetchFeed(page - 1)}
              disabled={page <= 1 || loading}
              className="flex items-center gap-1 px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <ChevronLeft className="w-4 h-4" />
              Prev
            </button>
            <span className="text-sm text-gray-500">
              Page {page} of {totalPages}
            </span>
            <button 
              onClick={() => fetchFeed(page + 1)}
              disabled={page >= totalPages || loading}
              className="flex items-center gap-1 px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Next
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>
    </>
  );
}

function FeedPost({ post }) {
  // Parse and render text with links and emoji
  const renderText = (text) => {
    if (!text) return null;
    
    // Escape HTML first to prevent XSS
    let processed = text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
    
    // Convert markdown-style links [text](url) to clickable links
    processed = processed.replace(
      /\[([^\]]+)\]\(([^)]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener noreferrer" class="text-teal-600 hover:text-teal-700 underline">$1</a>'
    );
    
    // Convert plain URLs to clickable links (but not already converted ones)
    processed = processed.replace(
      /(?<!href="|">)(https?:\/\/[^\s<&]+)/g,
      '<a href="$1" target="_blank" rel="noopener noreferrer" class="text-teal-600 hover:text-teal-700 underline break-all">$1</a>'
    );
    
    // Convert newlines to <br>
    processed = processed.replace(/\n/g, '<br/>');
    
    return (
      <div 
        className="text-gray-800 text-sm leading-relaxed"
        dangerouslySetInnerHTML={{ __html: processed }}
      />
    );
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '';
    try {
      const date = new Date(dateStr);
      const now = new Date();
      const diff = now - date;
      
      if (diff < 60000) return 'Just now';
      if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
      if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
      if (diff < 604800000) return `${Math.floor(diff / 86400000)}d ago`;
      
      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    } catch {
      return '';
    }
  };

  const formatNumber = (num) => {
    if (!num) return '0';
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toString();
  };

  return (
    <article className="p-4 hover:bg-gray-50/50 transition-colors">
      {/* Channel Header */}
      <div className="flex items-center gap-3 mb-3">
        {post.channelAvatar ? (
          <img 
            src={`${API_BASE}${post.channelAvatar}`}
            alt={post.channelTitle}
            className="w-10 h-10 rounded-full object-cover ring-2 ring-white shadow-sm"
            onError={(e) => {
              e.target.style.display = 'none';
              e.target.nextSibling.style.display = 'flex';
            }}
          />
        ) : null}
        <div 
          className="w-10 h-10 rounded-full flex items-center justify-center text-white text-sm font-semibold shadow-sm"
          style={{ 
            backgroundColor: post.channelSectorColor || '#6366f1',
            display: post.channelAvatar ? 'none' : 'flex'
          }}
        >
          {post.channelTitle?.substring(0, 2).toUpperCase() || 'CH'}
        </div>
        
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <a 
              href={`/telegram/${post.username}`}
              className="font-semibold text-gray-900 hover:text-teal-600 transition-colors truncate"
            >
              {post.channelTitle || post.username}
            </a>
            {post.channelSector && (
              <span 
                className="px-2 py-0.5 rounded-full text-xs font-medium shrink-0"
                style={{
                  backgroundColor: post.channelSectorColor ? `${post.channelSectorColor}20` : '#f3f4f6',
                  color: post.channelSectorColor || '#6b7280'
                }}
              >
                {post.channelSector}
              </span>
            )}
          </div>
          <p className="text-xs text-gray-500">@{post.username} • {formatDate(post.date)}</p>
        </div>
        
        <a 
          href={`https://t.me/${post.username}/${post.messageId}`}
          target="_blank"
          rel="noopener noreferrer"
          className="p-2 rounded-lg hover:bg-gray-100 transition-colors shrink-0"
          title="Open in Telegram"
        >
          <ExternalLink className="w-4 h-4 text-gray-400 hover:text-teal-500" />
        </a>
      </div>

      {/* Post Content */}
      <div className="mb-3">
        {renderText(post.text)}
      </div>

      {/* Media Display */}
      {post.hasMedia && post.mediaLocalPath && (
        <div className="mb-3 rounded-lg overflow-hidden bg-gray-100">
          {post.mediaType === 'photo' ? (
            <img 
              src={`${API_BASE}${post.mediaLocalPath}`}
              alt="Post media"
              className="w-full h-auto max-h-96 object-contain"
              loading="lazy"
              onError={(e) => {
                e.target.style.display = 'none';
              }}
            />
          ) : post.mediaType === 'video' ? (
            <video 
              src={`${API_BASE}${post.mediaLocalPath}`}
              controls
              className="w-full h-auto max-h-96"
              preload="metadata"
            />
          ) : null}
        </div>
      )}
      
      {/* Media indicator (when media not downloaded yet) */}
      {post.hasMedia && !post.mediaLocalPath && (
        <div className="mb-3 px-3 py-2 bg-gray-100 rounded-lg text-xs text-gray-500 flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-teal-400"></span>
          Contains {post.mediaType?.replace('MessageMedia', '') || 'media'}
        </div>
      )}

      {/* Stats */}
      <div className="flex items-center gap-4 text-xs text-gray-500">
        <span className="flex items-center gap-1">
          <Eye className="w-3.5 h-3.5" />
          {formatNumber(post.views)}
        </span>
        <span className="flex items-center gap-1">
          <Share2 className="w-3.5 h-3.5" />
          {formatNumber(post.forwards)}
        </span>
        {post.replies > 0 && (
          <span className="flex items-center gap-1">
            <MessageCircle className="w-3.5 h-3.5" />
            {formatNumber(post.replies)}
          </span>
        )}
      </div>
    </article>
  );
}
