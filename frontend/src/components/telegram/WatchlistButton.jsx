/**
 * WatchlistButton Component (BLOCK 5.1 UI)
 * Toggle button to add/remove channel from watchlist
 */
import React, { useState, useEffect } from 'react';
import { Star, Loader2 } from 'lucide-react';
import { Button } from '../ui/button';
import { checkWatchlist, addToWatchlist, removeFromWatchlist } from '../../api/telegramIntel.api';

export function WatchlistButton({ username, size = 'default', showLabel = true, onToggle }) {
  const [inWatchlist, setInWatchlist] = useState(false);
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState(false);

  useEffect(() => {
    if (!username) return;
    
    setLoading(true);
    checkWatchlist(username)
      .then((res) => {
        if (res.ok) {
          setInWatchlist(res.inWatchlist);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [username]);

  const handleToggle = async (e) => {
    e.preventDefault();
    e.stopPropagation();
    
    if (toggling) return;
    
    setToggling(true);
    try {
      if (inWatchlist) {
        const res = await removeFromWatchlist(username);
        if (res.ok) {
          setInWatchlist(false);
          onToggle?.(false);
        }
      } else {
        const res = await addToWatchlist(username);
        if (res.ok) {
          setInWatchlist(true);
          onToggle?.(true);
        }
      }
    } catch (err) {
      console.error('Watchlist toggle error:', err);
    } finally {
      setToggling(false);
    }
  };

  if (loading) {
    return (
      <Button
        variant="ghost"
        size={size}
        disabled
        className="text-muted-foreground"
        data-testid="watchlist-btn-loading"
      >
        <Loader2 className="h-4 w-4 animate-spin" />
        {showLabel && <span className="ml-2">Loading...</span>}
      </Button>
    );
  }

  return (
    <Button
      variant={inWatchlist ? 'default' : 'outline'}
      size={size}
      onClick={handleToggle}
      disabled={toggling}
      className={inWatchlist ? 'bg-amber-500 hover:bg-amber-600 text-white' : ''}
      data-testid={inWatchlist ? 'watchlist-btn-remove' : 'watchlist-btn-add'}
    >
      {toggling ? (
        <Loader2 className="h-4 w-4 animate-spin" />
      ) : (
        <Star className={`h-4 w-4 ${inWatchlist ? 'fill-current' : ''}`} />
      )}
      {showLabel && (
        <span className="ml-2">
          {inWatchlist ? 'В избранном' : 'В избранное'}
        </span>
      )}
    </Button>
  );
}

export default WatchlistButton;
