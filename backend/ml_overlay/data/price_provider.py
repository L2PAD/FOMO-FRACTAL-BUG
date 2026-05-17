"""
Price Provider — fetch BTC OHLCV via yfinance (5+ years daily)
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta


def get_ohlcv(symbol: str = "BTC-USD", years: int = 7) -> pd.DataFrame:
    """
    Fetch daily OHLCV from yfinance.
    Returns DataFrame with columns: open, high, low, close, volume
    Index: DatetimeIndex (UTC, date only)
    """
    end = datetime.utcnow()
    start = end - timedelta(days=years * 365)

    ticker = yf.Ticker(symbol)
    df = ticker.history(start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"), interval="1d")

    if df.empty:
        raise ValueError(f"No data returned for {symbol}")

    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.columns = ["open", "high", "low", "close", "volume"]
    df.index = pd.to_datetime(df.index).tz_localize(None)
    df = df.sort_index()
    df = df[~df.index.duplicated(keep="first")]

    return df
