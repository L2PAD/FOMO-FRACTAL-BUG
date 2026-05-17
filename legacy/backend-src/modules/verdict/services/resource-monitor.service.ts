/**
 * Resource Monitor Service
 * ========================
 * Monitors CPU and memory usage.
 * Alerts when approaching thresholds (60-70%).
 * Used by HeavyVerdictJob to throttle computation safely.
 */

import * as os from 'os';

export interface ResourceSnapshot {
  cpuPercent: number;      // 0-100 averaged across cores
  memUsedPercent: number;  // 0-100
  memUsedMB: number;
  memTotalMB: number;
  loadAvg1m: number;
  loadAvg5m: number;
  isOverloaded: boolean;
  reason?: string;
}

const CPU_WARN_THRESHOLD = 60;
const CPU_STOP_THRESHOLD = 70;
const MEM_WARN_THRESHOLD = 70;
const MEM_STOP_THRESHOLD = 80;

class ResourceMonitorService {
  private lastCpuTimes: os.CpuInfo[] | null = null;
  private lastAlertAt = 0;
  private readonly ALERT_COOLDOWN_MS = 5 * 60 * 1000; // 5 min between alerts

  /**
   * Get current resource snapshot
   */
  getSnapshot(): ResourceSnapshot {
    const totalMem = os.totalmem();
    const freeMem = os.freemem();
    const usedMem = totalMem - freeMem;
    const memUsedPercent = Math.round((usedMem / totalMem) * 100);
    const memUsedMB = Math.round(usedMem / (1024 * 1024));
    const memTotalMB = Math.round(totalMem / (1024 * 1024));

    const loadAvgs = os.loadavg();
    const cpuCount = os.cpus().length;
    // Normalize load average to percentage (load / cpuCount * 100)
    const cpuPercent = Math.round((loadAvgs[0] / cpuCount) * 100);

    let isOverloaded = false;
    let reason: string | undefined;

    if (cpuPercent >= CPU_STOP_THRESHOLD) {
      isOverloaded = true;
      reason = `CPU ${cpuPercent}% (threshold: ${CPU_STOP_THRESHOLD}%)`;
    } else if (memUsedPercent >= MEM_STOP_THRESHOLD) {
      isOverloaded = true;
      reason = `MEM ${memUsedPercent}% (threshold: ${MEM_STOP_THRESHOLD}%)`;
    }

    return {
      cpuPercent,
      memUsedPercent,
      memUsedMB,
      memTotalMB,
      loadAvg1m: loadAvgs[0],
      loadAvg5m: loadAvgs[1],
      isOverloaded,
      reason,
    };
  }

  /**
   * Check if resources are safe for computation.
   * Returns true if within thresholds.
   */
  isSafe(): boolean {
    const snap = this.getSnapshot();
    return !snap.isOverloaded;
  }

  /**
   * Check and log warnings if approaching thresholds.
   * Returns true if computation should continue, false if should stop.
   */
  checkAndWarn(): boolean {
    const snap = this.getSnapshot();

    if (snap.isOverloaded) {
      this.emitAlert(
        `RESOURCE OVERLOAD: ${snap.reason}. Pausing heavy computation.` +
        ` (CPU: ${snap.cpuPercent}%, MEM: ${snap.memUsedPercent}%, Load: ${snap.loadAvg1m.toFixed(2)})`
      );
      return false;
    }

    // Warning zone
    if (snap.cpuPercent >= CPU_WARN_THRESHOLD || snap.memUsedPercent >= MEM_WARN_THRESHOLD) {
      this.emitAlert(
        `RESOURCE WARNING: Approaching limits.` +
        ` CPU: ${snap.cpuPercent}%, MEM: ${snap.memUsedPercent}% (${snap.memUsedMB}/${snap.memTotalMB}MB), Load: ${snap.loadAvg1m.toFixed(2)}`
      );
    }

    return true;
  }

  /**
   * Emit resource alert (with cooldown to avoid spam)
   */
  private emitAlert(message: string): void {
    const now = Date.now();
    if (now - this.lastAlertAt < this.ALERT_COOLDOWN_MS) return;

    this.lastAlertAt = now;
    console.warn(`[ResourceMonitor] ⚠ ${message}`);
  }
}

export const resourceMonitorService = new ResourceMonitorService();
