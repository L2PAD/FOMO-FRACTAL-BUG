export function formatTs(ts) {
  if (!ts) return "—";
  const ms = ts > 1e12 ? ts : ts * 1000;
  return new Date(ms).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function eventTone(type = "") {
  const t = String(type).toUpperCase();

  if (t.includes("FAILED") || t.includes("REJECT")) {
    return "text-red-600";
  }
  if (t.includes("FILLED") || t.includes("SUCCESS") || t.includes("APPROVED")) {
    return "text-green-600";
  }
  if (t.includes("ORDER") || t.includes("SYNC")) {
    return "text-blue-600";
  }
  return "text-gray-600";
}

export function statusTone(status = "") {
  const s = String(status).toUpperCase();

  if (["FILLED", "SUCCESS", "OK", "ACTIVE"].includes(s)) return "text-green-600";
  if (["FAILED", "ERROR", "CANCELED", "REJECTED"].includes(s)) return "text-red-600";
  if (["PENDING", "OPEN", "PARTIALLY_FILLED", "WARNING"].includes(s)) return "text-amber-600";
  return "text-gray-700";
}
