/**
 * MarketCardExpanded — Vertical Narrative Flow
 * Colored text for value labels. No borders/backgrounds.
 */
import { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';

export default function MarketCardExpanded({ c }) {
  const [showTech, setShowTech] = useState(false);
  const { decision, picture, execution, project, tech } = c;

  return (
    <div className="px-6 pb-5 pt-1 ml-20 space-y-5">
      {/* DECISION */}
      <NBlock title="Decision">
        <div className="flex items-center gap-3 mb-2">
          <span className={`text-sm font-semibold ${c.statusColor}`}>{c.actionLabel}</span>
          <span className="text-xs text-gray-400 uppercase tracking-wider">{c.asset}</span>
        </div>
        {decision.whyNow.length > 0 && (
          <div className="mb-2">
            <Label>Why now</Label>
            {decision.whyNow.map((w, i) => <div key={i} className="text-sm text-emerald-600 leading-relaxed">+ {w}</div>)}
          </div>
        )}
        {decision.whyNot.length > 0 && (
          <div>
            <Label>Why not</Label>
            {decision.whyNot.map((w, i) => <div key={i} className="text-sm text-red-500 leading-relaxed">- {w}</div>)}
          </div>
        )}
      </NBlock>

      {/* PICTURE */}
      {(picture.bull.length > 0 || picture.bear.length > 0 || picture.marketGap.length > 0) && (
        <NBlock title="Picture">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {picture.bull.length > 0 && (
              <div>
                <div className="text-xs text-emerald-600 font-medium mb-0.5">Bull</div>
                {picture.bull.map((b, i) => <div key={i} className="text-sm text-gray-600 leading-relaxed">{b}</div>)}
              </div>
            )}
            {picture.bear.length > 0 && (
              <div>
                <div className="text-xs text-red-500 font-medium mb-0.5">Bear</div>
                {picture.bear.map((b, i) => <div key={i} className="text-sm text-gray-600 leading-relaxed">{b}</div>)}
              </div>
            )}
            {picture.marketGap.length > 0 && (
              <div>
                <div className="text-xs text-blue-600 font-medium mb-0.5">Market gap</div>
                {picture.marketGap.map((g, i) => <div key={i} className="text-sm text-gray-600 leading-relaxed">{g}</div>)}
              </div>
            )}
          </div>
        </NBlock>
      )}

      {/* EXECUTION */}
      <NBlock title="Execution">
        <div className="flex items-center gap-6 flex-wrap">
          {execution.entryType && (
            <Metric label="Entry type" value={execution.entryType} color="text-blue-600" />
          )}
          <Metric label="Quality" value={execution.qualityLabel.text} color={execution.qualityLabel.color} />
          <Metric label="Slippage" value={execution.slippageLabel.text} color={execution.slippageLabel.color} />
          {execution.scalingLabel && (
            <Metric label="Scaling" value={execution.scalingLabel.text} color={execution.scalingLabel.color} />
          )}
          {execution.grade && (
            <Metric label="Grade" value={execution.grade} color={execution.gradeColor} />
          )}
        </div>
        {execution.riskFlags.length > 0 && (
          <div className="mt-1.5 text-xs text-red-500">
            Risks: {execution.riskFlags.join(', ')}
          </div>
        )}
      </NBlock>

      {/* PROJECT */}
      {project && (
        <NBlock title="Project">
          <span className={`text-xs font-semibold ${project.verdict.color}`}>{project.verdict.text}</span>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-2">
            {project.bullCase.length > 0 && (
              <div>
                <div className="text-xs text-emerald-600 font-medium mb-0.5">Bull</div>
                {project.bullCase.map((b, i) => <div key={i} className="text-sm text-gray-600 leading-relaxed">{b}</div>)}
              </div>
            )}
            {project.bearCase.length > 0 && (
              <div>
                <div className="text-xs text-red-500 font-medium mb-0.5">Bear</div>
                {project.bearCase.map((b, i) => <div key={i} className="text-sm text-gray-600 leading-relaxed">{b}</div>)}
              </div>
            )}
            {project.keyRisks.length > 0 && (
              <div>
                <div className="text-xs text-red-500 font-medium mb-0.5">Risks</div>
                {project.keyRisks.map((r, i) => <div key={i} className="text-sm text-gray-600 leading-relaxed">{r}</div>)}
              </div>
            )}
          </div>
        </NBlock>
      )}

      {/* TECH LAYER */}
      <div className="pt-2">
        <button
          onClick={() => setShowTech(!showTech)}
          className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-600 transition-colors"
          data-testid={`tech-toggle-${c.id}`}
        >
          {showTech ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
          Technical data
        </button>
        {showTech && <TechLayer tech={tech} />}
      </div>
    </div>
  );
}

function NBlock({ title, children }) {
  return (
    <div>
      <div className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-2">{title}</div>
      {children}
    </div>
  );
}

function Label({ children }) {
  return <div className="text-xs text-gray-400 mb-0.5">{children}</div>;
}

function Metric({ label, value, color }) {
  return (
    <div>
      <div className="text-xs text-gray-400">{label}</div>
      <div className={`text-sm font-medium ${color || 'text-gray-900'}`}>{value}</div>
    </div>
  );
}

function TechLayer({ tech }) {
  if (!tech) return null;
  const pct = (v) => v != null ? `${(v * 100).toFixed(1)}%` : '--';
  return (
    <div className="mt-2 grid grid-cols-2 md:grid-cols-4 gap-4 text-xs text-gray-500" data-testid="tech-layer">
      <div className="space-y-0.5">
        <TH>Analysis</TH>
        <TR l="Fair Prob" v={pct(tech.fairProb)} /><TR l="Market Prob" v={pct(tech.marketProb)} />
        <TR l="Raw Edge" v={pct(tech.rawEdge)} /><TR l="Net Edge" v={pct(tech.netEdge)} />
        <TR l="Confidence" v={pct(tech.modelConfidence)} /><TR l="Alignment" v={pct(tech.alignmentScore)} />
        <TR l="Regime" v={tech.regime || '--'} />
      </div>
      <div className="space-y-0.5">
        <TH>Risk</TH>
        <TR l="Reversal" v={pct(tech.risk?.reversal_risk)} /><TR l="Breakdown" v={pct(tech.risk?.breakdown_risk)} />
        <TR l="Drawdown" v={pct(tech.risk?.drawdown_pressure)} /><TR l="Combined" v={pct(tech.risk?.combined_risk)} />
      </div>
      <div className="space-y-0.5">
        <TH>Repricing</TH>
        <TR l="State" v={tech.repricing?.repricing_state || '--'} /><TR l="Speed" v={pct(tech.repricing?.speed_score)} />
        <TR l="Acceleration" v={pct(tech.repricing?.acceleration)} /><TR l="Stress" v={pct(tech.repricing?.stress_signal)} />
      </div>
      <div className="space-y-0.5">
        <TH>Pricing</TH>
        <TR l="State" v={tech.pricing?.market_state || '--'} /><TR l="Spread" v={tech.pricing?.spread_quality || '--'} />
        <TR l="Volume" v={tech.pricing?.volume_profile || '--'} /><TR l="Liquidity" v={tech.pricing?.liquidity_depth || '--'} />
        <TR l="Expiry" v={tech.pricing?.days_to_expiry ? `${Math.round(tech.pricing.days_to_expiry)}d` : '--'} />
      </div>
    </div>
  );
}

function TH({ children }) { return <div className="text-gray-400 font-medium uppercase tracking-wider text-[10px]">{children}</div>; }
function TR({ l, v }) { return <div className="flex justify-between"><span className="text-gray-400">{l}</span><span className="font-mono text-gray-600">{v}</span></div>; }
