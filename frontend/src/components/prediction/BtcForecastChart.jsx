/**
 * BtcForecastChart v4 — Rolling Expectation Curve
 * No cone/fan/band overlay. Clean curve by normalized forecast points.
 * Props: data (from graph4), horizon, hideForecast (1D), oneDayOverlay
 */
import React, { useEffect, useRef } from 'react';
import { createChart, LineSeries } from 'lightweight-charts';

const DAY_SEC = 86400;

function ewma(points, alpha) {
  let prev = null;
  return points.map(pt => {
    const v = prev === null ? pt.value : alpha * pt.value + (1 - alpha) * prev;
    prev = v;
    return { time: pt.time, value: v };
  });
}

export default function BtcForecastChart({ data, horizon, hideForecast, oneDayOverlay }) {
  const containerRef = useRef(null);
  const chartRef = useRef(null);

  useEffect(() => {
    if (!data || !containerRef.current) return;
    let cancelled = false;

    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
    }

    const container = containerRef.current;
    container.querySelectorAll('[data-overlay]').forEach(el => el.remove());
    container._endDot = null;
    container._midDot = null;

    const chart = createChart(container, {
      width: container.clientWidth,
      height: container.clientHeight || 420,
      layout: {
        background: { color: '#ffffff' },
        textColor: '#64748b',
        fontSize: 11,
        fontFamily: "'Gilroy', -apple-system, BlinkMacSystemFont, sans-serif",
      },
      grid: {
        vertLines: { color: 'rgba(15, 23, 42, 0.03)' },
        horzLines: { color: 'rgba(15, 23, 42, 0.03)' },
      },
      rightPriceScale: { borderColor: 'rgba(15, 23, 42, 0.06)' },
      timeScale: {
        borderColor: 'rgba(15, 23, 42, 0.06)',
        timeVisible: false,
        rightOffset: hideForecast ? 8 : 5,
        tickMarkFormatter: (time) => {
          const d = new Date(time * 1000);
          const m = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
          return `${m[d.getUTCMonth()]} ${d.getUTCDate()}`;
        },
      },
      localization: {
        locale: 'en-US',
        priceFormatter: (p) => `$${p.toLocaleString('en-US', { maximumFractionDigits: 0 })}`,
      },
      crosshair: {
        vertLine: { color: 'rgba(15, 23, 42, 0.08)', width: 1, style: 3 },
        horzLine: { color: 'rgba(15, 23, 42, 0.08)', width: 1, style: 3 },
      },
      handleScroll: true,
      handleScale: true,
    });
    chartRef.current = chart;

    const { priceSeries, rollingForecasts, nowTs } = data;
    const nowSec = Math.floor(nowTs / 1000);

    // Price line (green)
    const priceLine = chart.addSeries(LineSeries, {
      color: '#16a34a',
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: true,
      crosshairMarkerVisible: true,
    });
    priceLine.setData(priceSeries.map(pt => ({
      time: Math.floor(pt.t / 1000),
      value: pt.p,
    })));

    // Forecast curve (black) — normalized rolling expectations
    let forecastLineRef = null;
    if (!hideForecast && rollingForecasts.length > 0) {
      // Build normalized points: x = madeAt + horizon, y = entryPrice * (1 + movePct/100)
      const rawPts = [];
      for (const f of rollingForecasts) {
        const targetSec = Math.floor(f.madeAtTs / 1000) + f.horizonDays * DAY_SEC;
        const normalizedY = f.entryPrice * (1 + f.expectedMovePct / 100);
        if (normalizedY > 0) {
          rawPts.push({ time: targetSec, value: normalizedY });
        }
      }

      // Only keep future target points (targetSec > nowSec)
      const futurePts = rawPts.filter(pt => pt.time > nowSec);
      futurePts.sort((a, b) => a.time - b.time);

      // Stitch: start from NOW price, then future forecast targets
      if (futurePts.length > 0) {
        const stitchPts = [{ time: nowSec, value: data.nowPrice }, ...futurePts];

        // Deduplicate (keep last value for same timestamp)
        const deduped = [];
        for (const pt of stitchPts) {
          if (deduped.length > 0 && deduped[deduped.length - 1].time === pt.time) {
            deduped[deduped.length - 1].value = pt.value;
          } else {
            deduped.push({ ...pt });
          }
        }

        // EWMA smoothing (NOW point seeds the smoother naturally)
        const alpha = horizon === '30D' ? 0.35 : 0.55;
        const smoothed = ewma(deduped, alpha);

        if (smoothed.length > 0) {
          const forecastLine = chart.addSeries(LineSeries, {
            color: '#0f172a',
            lineWidth: 2,
            priceLineVisible: false,
            lastValueVisible: true,
            crosshairMarkerVisible: true,
            crosshairMarkerRadius: 3,
          });
          forecastLine.setData(smoothed);
          forecastLineRef = forecastLine;

          // Endpoint dot + label
          const lastPt = smoothed[smoothed.length - 1];
          const dotEl = document.createElement('div');
          dotEl.setAttribute('data-overlay', 'dot');
          Object.assign(dotEl.style, {
            position: 'absolute', width: '8px', height: '8px', borderRadius: '50%',
            border: '2px solid #0f172a', background: '#ffffff',
            pointerEvents: 'none', zIndex: '11', display: 'none',
          });
          container.appendChild(dotEl);

          const lblEl = document.createElement('div');
          lblEl.setAttribute('data-overlay', 'label');
          Object.assign(lblEl.style, {
            position: 'absolute', fontSize: '10px', fontWeight: '600', color: '#0f172a',
            pointerEvents: 'none', zIndex: '12', whiteSpace: 'nowrap', display: 'none',
          });
          lblEl.textContent = horizon;
          container.appendChild(lblEl);

          container._endDot = { el: dotEl, lbl: lblEl, time: lastPt.time, value: lastPt.value };

          // 30D: add intermediate 7D marker on the curve
          if (horizon === '30D') {
            const sevenDaySec = nowSec + 7 * DAY_SEC;
            // Find smoothed value at 7D mark via linear interpolation
            let val7d = null;
            for (let i = 0; i < smoothed.length - 1; i++) {
              if (smoothed[i].time <= sevenDaySec && smoothed[i + 1].time >= sevenDaySec) {
                const t0 = smoothed[i].time, t1 = smoothed[i + 1].time;
                const v0 = smoothed[i].value, v1 = smoothed[i + 1].value;
                val7d = t1 === t0 ? v0 : v0 + (v1 - v0) * (sevenDaySec - t0) / (t1 - t0);
                break;
              }
            }
            if (val7d !== null) {
              const dot7 = document.createElement('div');
              dot7.setAttribute('data-overlay', 'dot-7d');
              Object.assign(dot7.style, {
                position: 'absolute', width: '8px', height: '8px', borderRadius: '50%',
                border: '2px solid #0f172a', background: '#ffffff',
                pointerEvents: 'none', zIndex: '11', display: 'none',
              });
              container.appendChild(dot7);

              const lbl7 = document.createElement('div');
              lbl7.setAttribute('data-overlay', 'label-7d');
              Object.assign(lbl7.style, {
                position: 'absolute', fontSize: '10px', fontWeight: '600', color: '#0f172a',
                pointerEvents: 'none', zIndex: '12', whiteSpace: 'nowrap', display: 'none',
              });
              lbl7.textContent = '7D';
              container.appendChild(lbl7);

              container._midDot = { el: dot7, lbl: lbl7, time: sevenDaySec, value: val7d };
            }
          }
        }
      }
    }

    chart.timeScale().fitContent();

    // NOW vertical overlay
    const nowWrapper = document.createElement('div');
    nowWrapper.setAttribute('data-overlay', 'now');
    Object.assign(nowWrapper.style, {
      position: 'absolute', top: '0', bottom: '30px', width: '1px',
      pointerEvents: 'none', zIndex: '10', display: 'none',
    });
    const nowLabel = document.createElement('div');
    Object.assign(nowLabel.style, {
      position: 'absolute', top: '0', left: '50%', transform: 'translateX(-50%)',
      fontSize: '9px', fontWeight: '700', color: '#7B61FF', letterSpacing: '0.5px',
    });
    nowLabel.textContent = 'NOW';
    nowWrapper.appendChild(nowLabel);
    const nowLine = document.createElement('div');
    Object.assign(nowLine.style, {
      position: 'absolute', top: '14px', bottom: '0', width: '0',
      borderLeft: '1px dashed #7B61FF', opacity: '0.7',
    });
    nowWrapper.appendChild(nowLine);
    container.style.position = 'relative';
    container.appendChild(nowWrapper);

    // 1D arrow overlay
    let arrowEl = null;
    if (oneDayOverlay) {
      arrowEl = document.createElement('div');
      arrowEl.setAttribute('data-overlay', '1d-arrow');
      const arrowChar = oneDayOverlay.direction === 'LONG' || oneDayOverlay.direction === 'UP'
        ? '\u2191'
        : oneDayOverlay.direction === 'SHORT' || oneDayOverlay.direction === 'DOWN'
        ? '\u2193'
        : '\u2192';
      const pct = oneDayOverlay.movePct;
      const sign = pct >= 0 ? '+' : '';
      arrowEl.innerHTML = `<span style="font-size:14px;line-height:1">${arrowChar}</span><span style="font-size:11px;font-weight:600">${sign}${pct.toFixed(1)}%</span>`;
      Object.assign(arrowEl.style, {
        position: 'absolute', display: 'none', pointerEvents: 'none', zIndex: '13',
        color: oneDayOverlay.color, whiteSpace: 'nowrap',
        flexDirection: 'row', alignItems: 'center', gap: '2px',
      });
      container.appendChild(arrowEl);
    }

    // rAF sync loop
    let rafId = null;
    const syncOverlays = () => {
      if (cancelled) return;
      const nx = chart.timeScale().timeToCoordinate(nowSec);
      if (nx !== null && nx >= 0) {
        nowWrapper.style.left = `${nx}px`;
        nowWrapper.style.display = '';
        if (arrowEl) {
          const priceY = priceLine.priceToCoordinate(data.nowPrice);
          if (priceY !== null && priceY >= 0) {
            arrowEl.style.left = `${nx + 8}px`;
            arrowEl.style.top = `${priceY - 10}px`;
            arrowEl.style.display = 'flex';
          } else {
            arrowEl.style.display = 'none';
          }
        }
      } else {
        nowWrapper.style.display = 'none';
        if (arrowEl) arrowEl.style.display = 'none';
      }

      // Endpoint dot
      const endDot = container._endDot;
      if (endDot && forecastLineRef) {
        const x = chart.timeScale().timeToCoordinate(endDot.time);
        const y = forecastLineRef.priceToCoordinate(endDot.value);
        if (x !== null && y !== null && x >= 0 && y >= 0) {
          endDot.el.style.left = `${x - 4}px`;
          endDot.el.style.top = `${y - 4}px`;
          endDot.el.style.display = '';
          endDot.lbl.style.left = `${x + 6}px`;
          endDot.lbl.style.top = `${y - 14}px`;
          endDot.lbl.style.display = '';
        } else {
          endDot.el.style.display = 'none';
          endDot.lbl.style.display = 'none';
        }
      }

      // Mid-point dot (7D on 30D chart)
      const midDot = container._midDot;
      if (midDot && forecastLineRef) {
        const mx = chart.timeScale().timeToCoordinate(midDot.time);
        const my = forecastLineRef.priceToCoordinate(midDot.value);
        if (mx !== null && my !== null && mx >= 0 && my >= 0) {
          midDot.el.style.left = `${mx - 4}px`;
          midDot.el.style.top = `${my - 4}px`;
          midDot.el.style.display = '';
          midDot.lbl.style.left = `${mx + 6}px`;
          midDot.lbl.style.top = `${my - 14}px`;
          midDot.lbl.style.display = '';
        } else {
          midDot.el.style.display = 'none';
          midDot.lbl.style.display = 'none';
        }
      }

      rafId = requestAnimationFrame(syncOverlays);
    };
    rafId = requestAnimationFrame(syncOverlays);

    const ro = new ResizeObserver(entries => {
      if (entries.length > 0) {
        const { width, height } = entries[0].contentRect;
        chart.applyOptions({ width, height: height || 420 });
      }
    });
    ro.observe(container);

    return () => {
      cancelled = true;
      if (rafId) cancelAnimationFrame(rafId);
      ro.disconnect();
      container.querySelectorAll('[data-overlay]').forEach(el => el.remove());
      container._endDot = null;
      container._midDot = null;
      chart.remove();
      chartRef.current = null;
    };
  }, [data, horizon, hideForecast, oneDayOverlay]);

  return (
    <div
      ref={containerRef}
      data-testid="btc-forecast-chart"
      style={{ minHeight: 420, height: '100%', position: 'relative' }}
    />
  );
}
