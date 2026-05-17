/**
 * AnalysisTab — single dashboard "What is happening"
 * ===================================================
 *
 * Replaces 4 of the old 5 tabs (Research / Structure / Signals / Deep)
 * by stacking them as collapsible sections that all read from the SAME
 * unified state object.
 *
 *   ┌─ Section A: Geometry  (was: Structure)
 *   ├─ Section B: Evidence  (was: Signals — explanation only, NOT bias source)
 *   └─ Section C: Detail    (was: DeepDive — collapsed by default)
 *
 * Hard rule: every block reads `unified.bias` / `unified.confidence` and
 * never re-derives truth from raw indicators / patterns.
 */

import React, { useState } from 'react';
import styled from 'styled-components';
import { ChevronDown, ChevronRight, Layers, Activity, FileText, Target } from 'lucide-react';

import StructureTab from './StructureTab';
import OverviewTab from './OverviewTab';
import SignalsTab from './SignalsTab';
import DeepDiveTab from './DeepDiveTab';

const Container = styled.div`
  display: flex;
  flex-direction: column;
  gap: 12px;
`;

const Section = styled.div`
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  overflow: hidden;
`;

const SectionHead = styled.button`
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 18px;
  background: #ffffff;
  border: none;
  border-bottom: ${(p) => (p.$open ? '1px solid #eef1f5' : 'none')};
  cursor: pointer;
  transition: background 0.15s;

  &:hover { background: #f8fafc; }
`;

/* Explicit affordance for collapsible sections — replaces the lonely
   chevron with a clearly visible pill that says "Show" / "Hide".
   Architect feedback: "small arrow only is not obvious enough". */
const Disclosure = styled.span`
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.3px;
  text-transform: uppercase;
  color: ${(p) => (p.$open ? '#475569' : '#0f172a')};
  background: ${(p) => (p.$open ? '#f1f5f9' : '#0f172a')};
  border: 1px solid ${(p) => (p.$open ? 'rgba(15,23,42,0.10)' : '#0f172a')};
  border-radius: 999px;
  white-space: nowrap;

  /* When closed, invert: solid dark pill says "Show" — hard to miss */
  ${(p) => !p.$open && `
    color: #ffffff;
  `}
`;

const HeadLeft = styled.div`
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;

  .ico {
    width: 18px; height: 18px;
    display: flex; align-items: center; justify-content: center;
    color: #64748b;
    background: transparent;
  }
  .desc { font-size: 11px; font-weight: 500; color: #94a3b8; margin-left: 6px; }
`;

const SectionBody = styled.div`
  padding: 16px 18px;
`;

const InlineSummary = styled.div`
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  margin: 12px 0;
  background: transparent;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 12px;
  color: #334155;
`;

const Tag = styled.span`
  padding: 0;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.4px;
  text-transform: uppercase;
  background: transparent;
  color: ${(p) => p.$tone === 'bull' ? '#16a34a'
                : p.$tone === 'bear' ? '#dc2626'
                : '#475569'};
`;

const toneFor = (b) => (b === 'bullish' ? 'bull' : b === 'bearish' ? 'bear' : 'neutral');

/**
 * Decision-aware indicator summary banner.
 * Tells the user explicitly: "indicators support / dissent / neutral
 * — they are the EXPLANATION, decision.bias is the TRUTH."
 */
const IndicatorBanner = ({ unified }) => {
  const exp = unified?.indicatorExplanation;
  if (!exp || !exp.total) return null;

  const sup = exp.supporting.length;
  const dis = exp.dissenting.length;
  const neu = exp.neutral.length;

  return (
    <InlineSummary $bias={unified.bias}>
      <span style={{ fontWeight: 700, color: '#0f172a' }}>Indicator support:</span>
      <Tag $tone="bull">{sup} support</Tag>
      <Tag $tone="bear">{dis} dissent</Tag>
      <Tag $tone="neutral">{neu} neutral</Tag>
      <span style={{ marginLeft: 'auto', color: '#94a3b8', fontSize: 11 }}>
        decision is the truth · indicators explain it
      </span>
    </InlineSummary>
  );
};

const AnalysisTab = ({
  unified,
  // pass-through to legacy section components
  setupData,
  mtfContext,
  symbol,
  selectedTF,
  chartType,
  // structure section
  structureProps,
  // signals section
  signalsProps,
  // deep section
  deepProps,
  // overview section
  overviewProps,
}) => {
  const [openA, setOpenA] = useState(true);   // Geometry
  const [openB, setOpenB] = useState(true);   // Evidence
  const [openC, setOpenC] = useState(false);  // Detail (collapsed by default)

  if (!unified) return null;

  return (
    <Container data-testid="analysis-tab">
      {/* ── State summary (uses Overview block, but shorter) ── */}
      <Section>
        <SectionHead $open onClick={() => {}} as="div" style={{ cursor: 'default' }}>
          <HeadLeft>
            <div className="ico"><Target size={15} /></div>
            <span>State</span>
            <span className="desc">High-level interpretation</span>
          </HeadLeft>
        </SectionHead>
        <SectionBody>
          {/* OverviewTab already reads decision-aware fields */}
          <OverviewTab {...(overviewProps || {})} />
        </SectionBody>
      </Section>

      {/* ── Section A: Geometry (Structure) ── */}
      <Section>
        <SectionHead $open={openA} onClick={() => setOpenA((v) => !v)} data-testid="section-geometry">
          <HeadLeft>
            <div className="ico"><Layers size={15} /></div>
            <span>Geometry</span>
            <span className="desc">Patterns · structure · levels</span>
          </HeadLeft>
          <Disclosure $open={openA}>
            {openA ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
            {openA ? '\u2212 Hide details' : '\u002B Show details'}
          </Disclosure>
        </SectionHead>
        {openA && (
          <SectionBody>
            <StructureTab {...(structureProps || {})} />
          </SectionBody>
        )}
      </Section>

      {/* ── Section B: Evidence (Signals — explanation, NOT truth) ── */}
      <Section>
        <SectionHead $open={openB} onClick={() => setOpenB((v) => !v)} data-testid="section-evidence">
          <HeadLeft>
            <div className="ico"><Activity size={15} /></div>
            <span>Evidence</span>
            <span className="desc">Indicator support for the decision (explanation only)</span>
          </HeadLeft>
          <Disclosure $open={openB}>
            {openB ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
            {openB ? '\u2212 Hide details' : '\u002B Show details'}
          </Disclosure>
        </SectionHead>
        {openB && (
          <SectionBody>
            <IndicatorBanner unified={unified} />
            <SignalsTab {...(signalsProps || {})} unified={unified} />
          </SectionBody>
        )}
      </Section>

      {/* ── Section C: Detail (Deep — collapsed by default) ── */}
      <Section>
        <SectionHead $open={openC} onClick={() => setOpenC((v) => !v)} data-testid="section-detail">
          <HeadLeft>
            <div className="ico"><FileText size={15} /></div>
            <span>Detail</span>
            <span className="desc">Full breakdown · drivers · conflicts · raw</span>
          </HeadLeft>
          <Disclosure $open={openC}>
            {openC ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
            {openC ? '\u2212 Hide details' : '\u002B Show details'}
          </Disclosure>
        </SectionHead>
        {openC && (
          <SectionBody>
            <DeepDiveTab {...(deepProps || {})} />
          </SectionBody>
        )}
      </Section>
    </Container>
  );
};

export default AnalysisTab;
