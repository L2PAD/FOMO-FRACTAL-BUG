export function usePositionControl() {
  const call = async (url, body = null) => {
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: body ? JSON.stringify(body) : null,
      });
      return await response.json();
    } catch (err) {
      console.error("[usePositionControl] Error:", err);
      return { ok: false, error: String(err) };
    }
  };

  return {
    reduce: (symbol, percent) =>
      call(`/api/control/${symbol}/reduce`, { percent }),

    reverse: (symbol) =>
      call(`/api/control/${symbol}/reverse`),

    flattenAll: () =>
      call(`/api/control/flatten-all`),
  };
}
