/**
 * AUTO-STUB — Memory outcome resolver (TP/FP labelling of past predictions).
 * No-op: live predictions unaffected.
 */
export const outcomeResolverService = {
  resolveOutcomes: async (..._args: any[]) => ({ ok: true, resolved: 0, stubbed: true }),
  resolve:         async (..._args: any[]) => ({ ok: true, stubbed: true }),
  resolvePending:  async (..._args: any[]) => ({ ok: true, resolved: 0 }),
  start:           () => { /* noop */ },
  stop:            () => { /* noop */ },
};
export default outcomeResolverService;
