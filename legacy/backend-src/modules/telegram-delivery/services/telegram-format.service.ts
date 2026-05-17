/**
 * Telegram Format Service
 *
 * Formats prediction alerts, batch digests, and weekly digests
 * for Telegram delivery. Action-first, readable in 3-5 seconds.
 */

export interface FormatInput {
  type: string;
  data: any;
}

class TelegramFormatService {
  formatEntryAlert(data: any): string {
    const action = data.action || 'UNKNOWN';
    const asset = data.asset || 'N/A';
    const question = data.question || '';
    const edge = data.edge ? `${(data.edge * 100).toFixed(0)}%` : 'N/A';
    const confidence = data.confidence ? `${(data.confidence * 100).toFixed(0)}%` : 'N/A';
    const execution = data.entryStyle || 'ENTER_MARKET';
    const conviction = data.conviction || 'MEDIUM';

    let msg = `<b>ENTRY SIGNAL | ${this.esc(asset)}</b>\n`;
    if (question) msg += `${this.esc(question)}\n`;
    msg += `\n<b>Action:</b> ${action}`;
    msg += `\n<b>Edge:</b> +${edge}`;
    msg += `\n<b>Confidence:</b> ${confidence}`;
    msg += `\n<b>Conviction:</b> ${conviction}`;
    msg += `\n<b>Execution:</b> ${execution}`;

    if (data.reasons?.length) {
      msg += `\n\n<b>Why:</b>`;
      for (const r of data.reasons.slice(0, 3)) {
        msg += `\n• ${this.esc(r)}`;
      }
    }

    if (data.risks?.length) {
      msg += `\n\n<b>Risks:</b>`;
      for (const r of data.risks.slice(0, 2)) {
        msg += `\n• ${this.esc(r)}`;
      }
    }

    if (data.urgency) {
      msg += `\n\n<b>Timing:</b> ${data.urgency}`;
    }

    return msg;
  }

  formatExitAlert(data: any): string {
    const asset = data.asset || 'N/A';
    const question = data.question || '';

    let msg = `<b>EXIT SIGNAL | ${this.esc(asset)}</b>\n`;
    if (question) msg += `${this.esc(question)}\n`;
    msg += `\n<b>Action:</b> EXIT`;

    if (data.reasons?.length) {
      msg += `\n\n<b>Reason:</b>`;
      for (const r of data.reasons.slice(0, 3)) {
        msg += `\n• ${this.esc(r)}`;
      }
    }

    return msg;
  }

  formatRiskAlert(data: any): string {
    const asset = data.asset || 'N/A';
    const riskType = data.riskType || 'ELEVATED';

    let msg = `<b>RISK ALERT | ${this.esc(asset)}</b>\n`;
    msg += `\n<b>Risk:</b> ${riskType}`;

    if (data.description) {
      msg += `\n\n${this.esc(data.description)}`;
    }

    if (data.effect) {
      msg += `\n\n<b>Potential effect:</b>\n• ${this.esc(data.effect)}`;
    }

    return msg;
  }

  formatBatchDigest(data: any): string {
    const opportunities = data.opportunities || [];
    const stateChanges = data.stateChanges || 0;
    const riskAlerts = data.riskAlerts || 0;

    let msg = `<b>30m Digest</b>\n`;

    if (opportunities.length > 0) {
      msg += `\n<b>Top Opportunities:</b>`;
      for (const o of opportunities.slice(0, 5)) {
        const edge = o.edge ? `+${(o.edge * 100).toFixed(0)}%` : '';
        msg += `\n${this.esc(o.asset || 'N/A')} — ${o.action || '?'} ${edge}`;
      }
    }

    if (stateChanges > 0) {
      msg += `\n\n<b>State Changes:</b> ${stateChanges} markets`;
    }

    if (riskAlerts > 0) {
      msg += `\n<b>Risk Alerts:</b> ${riskAlerts}`;
    }

    if (!opportunities.length && !stateChanges && !riskAlerts) {
      msg += `\nNo significant changes in the last 30 minutes.`;
    }

    return msg;
  }

  formatWeeklyDigest(data: any): string {
    const sys = data.systemState || 'STABLE';
    const stateEmoji = sys === 'IMPROVING' ? '↑' : sys === 'DEGRADING' ? '↓' : sys === 'UNSTABLE' ? '⚠' : '→';

    let msg = `<b>Weekly Prediction Report</b>\n`;
    msg += `\n<b>System:</b> ${sys} ${stateEmoji}\n`;

    // Metric deltas
    if (data.metricDeltas?.length) {
      for (const d of data.metricDeltas.slice(0, 5)) {
        if (d.direction === 'STABLE') continue;
        const arrow = d.direction === 'UP' ? '↑' : '↓';
        const sign = d.delta > 0 ? '+' : '';
        const flag = d.impact === 'HIGH' ? ' ❗' : '';
        msg += `\n${d.metric}: ${arrow} ${sign}${d.delta.toFixed(1)}%${flag}`;
      }
    }

    // Execution
    if (data.executionDeltas?.length) {
      msg += `\n\n<b>Execution:</b>`;
      for (const e of data.executionDeltas.slice(0, 3)) {
        const arrow = e.direction === 'UP' ? '↑' : e.direction === 'DOWN' ? '↓' : '→';
        msg += `\n${e.style.replace(/_/g, ' ')} ${arrow}`;
      }
    }

    // Lessons
    if (data.lessons?.length) {
      msg += `\n\n<b>Top Lesson:</b>\n${this.esc(data.lessons[0])}`;
    }

    // Biggest changes
    if (data.biggestImprovement) {
      msg += `\n\n<b>Best:</b> ${this.esc(data.biggestImprovement)}`;
    }
    if (data.biggestDegradation) {
      msg += `\n<b>Weak:</b> ${this.esc(data.biggestDegradation)}`;
    }

    return msg;
  }

  formatMetaAlert(data: any): string {
    const type = data.type || 'META_ALERT';
    const title = data.title || type;
    const assets = (data.assets || []).join(' / ');

    let msg = `<b>${this.esc(title)}</b>\n`;
    if (assets) msg += `\nMarkets: ${this.esc(assets)}`;
    msg += `\nPriority: ${data.priority || 'MEDIUM'}`;
    msg += `\nConfidence: ${((data.confidence || 0) * 100).toFixed(0)}%`;

    if (data.summary) {
      msg += `\n\n${this.esc(data.summary)}`;
    }

    if (data.keyDrivers?.length) {
      msg += `\n\n<b>Why:</b>`;
      for (const d of data.keyDrivers.slice(0, 3)) {
        msg += `\n• ${this.esc(d)}`;
      }
    }

    if (data.risks?.length) {
      msg += `\n\n<b>Risk:</b>`;
      for (const r of data.risks.slice(0, 2)) {
        msg += `\n• ${this.esc(r)}`;
      }
    }

    if (data.regimeShift?.detected) {
      msg += `\n\n<b>Regime:</b> ${data.regimeShift.direction}`;
    }

    return msg;
  }

  format(type: string, data: any): string {
    switch (type) {
      case 'ENTRY_ALERT': return this.formatEntryAlert(data);
      case 'EXIT_ALERT': return this.formatExitAlert(data);
      case 'RISK_ALERT': return this.formatRiskAlert(data);
      case 'BATCH_DIGEST': return this.formatBatchDigest(data);
      case 'WEEKLY_DIGEST': return this.formatWeeklyDigest(data);
      case 'META_ALERT': return this.formatMetaAlert(data);
      default: return `<b>${type}</b>\n\n${JSON.stringify(data).slice(0, 500)}`;
    }
  }

  private esc(s: string): string {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }
}

export const telegramFormatService = new TelegramFormatService();
