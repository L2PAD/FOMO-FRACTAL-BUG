/**
 * AUTO-STUB — Memory snapshot writer (post-prediction audit log).
 * No-op: predictions still compute, just nothing persisted to memory store.
 */
export const memorySnapshotWriterService = {
  writeSnapshot: async (..._args: any[]) => ({ ok: true, stubbed: true }),
  write:         async (..._args: any[]) => ({ ok: true, stubbed: true }),
  flush:         async () => ({ ok: true }),
  start:         () => { /* noop */ },
  stop:          () => { /* noop */ },
};
export default memorySnapshotWriterService;
