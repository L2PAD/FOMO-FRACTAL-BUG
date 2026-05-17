const API = process.env.REACT_APP_BACKEND_URL || "";

export function useProtection() {
  const setTP = async (symbol, price) => {
    try {
      const response = await fetch(API + "/api/trading/paper/protection/" + symbol + "/tp", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ price }),
      });
      return await response.json();
    } catch (err) {
      console.error("[useProtection] setTP error:", err);
      return { ok: false, error: String(err) };
    }
  };

  const setSL = async (symbol, price) => {
    try {
      const response = await fetch(API + "/api/trading/paper/protection/" + symbol + "/sl", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ price }),
      });
      return await response.json();
    } catch (err) {
      console.error("[useProtection] setSL error:", err);
      return { ok: false, error: String(err) };
    }
  };

  return { setTP, setSL };
}
