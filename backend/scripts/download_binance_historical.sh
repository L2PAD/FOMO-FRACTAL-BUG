#!/usr/bin/env bash
#
# Download Binance historical OHLCV data (daily candles)
# Source: https://data.binance.vision/
#
# Usage: ./download_binance_historical.sh
#
# This downloads BTCUSDT, ETHUSDT 1d candles for 2023-2024

set -e

OUTPUT_DIR="/app/backend/data/historical"
mkdir -p "$OUTPUT_DIR"

SYMBOLS=("BTCUSDT" "ETHUSDT" "SOLUSDT" "BNBUSDT" "XRPUSDT")
YEARS=("2023" "2024")
MONTHS=("01" "02" "03" "04" "05" "06" "07" "08" "09" "10" "11" "12")

BASE_URL="https://data.binance.vision/data/spot/monthly/klines"

echo "═══════════════════════════════════════════════════════"
echo "  BINANCE HISTORICAL DATA DOWNLOADER"
echo "═══════════════════════════════════════════════════════"

for SYMBOL in "${SYMBOLS[@]}"; do
  echo ""
  echo "📥 Downloading $SYMBOL..."
  
  COMBINED_FILE="$OUTPUT_DIR/${SYMBOL}_1d.csv"
  > "$COMBINED_FILE"  # Clear file
  
  FIRST=true
  
  for YEAR in "${YEARS[@]}"; do
    for MONTH in "${MONTHS[@]}"; do
      FILE_NAME="${SYMBOL}-1d-${YEAR}-${MONTH}.zip"
      URL="${BASE_URL}/${SYMBOL}/1d/${FILE_NAME}"
      
      # Download
      echo -n "  ${YEAR}-${MONTH}... "
      
      if curl -sf -o "/tmp/${FILE_NAME}" "$URL" 2>/dev/null; then
        # Unzip and append
        unzip -p "/tmp/${FILE_NAME}" > "/tmp/temp_candles.csv"
        
        # Skip header if not first file
        if [ "$FIRST" = true ]; then
          cat "/tmp/temp_candles.csv" >> "$COMBINED_FILE"
          FIRST=false
        else
          tail -n +2 "/tmp/temp_candles.csv" >> "$COMBINED_FILE" 2>/dev/null || true
        fi
        
        rm -f "/tmp/${FILE_NAME}" "/tmp/temp_candles.csv"
        echo "✓"
      else
        echo "✗ (not available)"
      fi
    done
  done
  
  # Count lines
  LINES=$(wc -l < "$COMBINED_FILE")
  echo "  → $COMBINED_FILE ($LINES candles)"
done

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  DOWNLOAD COMPLETE"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "Files created:"
ls -lh "$OUTPUT_DIR"/*.csv 2>/dev/null || echo "No files found"
