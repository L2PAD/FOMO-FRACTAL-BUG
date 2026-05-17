import React from "react";
import ReactDOM from "react-dom/client";
import "@/index.css";
import "@/chartStyles.css";
import App from "@/App";

// ──────────────────────────────────────────────────────────────────────────
// LOCALE SANITIZER — strip POSIX modifiers ("@posix") from BCP-47 language
// tags before they reach Intl.DateTimeFormat / Date.toLocaleString.
// lightweight-charts crashes with `RangeError: Invalid language tag: en-US@posix`
// when the browser/container reports a POSIX-style locale. We normalize once
// here so charts & date formatting work everywhere.
// ──────────────────────────────────────────────────────────────────────────
(function sanitizeLocales() {
  try {
    const sanitize = (tag) => {
      if (typeof tag !== "string") return tag;
      // Strip POSIX modifier "@..." and any "_" → "-" conversion
      return tag.replace(/@[^,;\s]+/g, "").replace(/_/g, "-");
    };

    const origToLocale = Date.prototype.toLocaleString;
    Date.prototype.toLocaleString = function (locales, options) {
      try {
        if (Array.isArray(locales)) locales = locales.map(sanitize);
        else if (locales) locales = sanitize(locales);
        return origToLocale.call(this, locales, options);
      } catch (_) {
        return origToLocale.call(this, "en-US", options);
      }
    };

    const origToLocaleDate = Date.prototype.toLocaleDateString;
    Date.prototype.toLocaleDateString = function (locales, options) {
      try {
        if (Array.isArray(locales)) locales = locales.map(sanitize);
        else if (locales) locales = sanitize(locales);
        return origToLocaleDate.call(this, locales, options);
      } catch (_) {
        return origToLocaleDate.call(this, "en-US", options);
      }
    };

    const origToLocaleTime = Date.prototype.toLocaleTimeString;
    Date.prototype.toLocaleTimeString = function (locales, options) {
      try {
        if (Array.isArray(locales)) locales = locales.map(sanitize);
        else if (locales) locales = sanitize(locales);
        return origToLocaleTime.call(this, locales, options);
      } catch (_) {
        return origToLocaleTime.call(this, "en-US", options);
      }
    };

    // Also patch Intl constructors (used by lightweight-charts internals)
    ["DateTimeFormat", "NumberFormat"].forEach((cls) => {
      if (window.Intl && window.Intl[cls]) {
        const Orig = window.Intl[cls];
        const Patched = function (locales, options) {
          if (Array.isArray(locales)) locales = locales.map(sanitize);
          else if (locales) locales = sanitize(locales);
          try {
            return new Orig(locales, options);
          } catch (_) {
            return new Orig("en-US", options);
          }
        };
        Patched.prototype = Orig.prototype;
        Patched.supportedLocalesOf = Orig.supportedLocalesOf?.bind(Orig);
        window.Intl[cls] = Patched;
      }
    });
  } catch (e) {
    // Best-effort; never break the app
    // eslint-disable-next-line no-console
    console.warn("[locale-sanitizer] init failed:", e);
  }
})();

// Suppress MetaMask errors until we implement Web3 integration
const originalError = console.error;
console.error = (...args) => {
  const errorMessage = args[0]?.toString() || '';
  
  // Ignore MetaMask-related errors (we'll implement this later)
  if (
    errorMessage.includes('MetaMask') ||
    errorMessage.includes('ethereum') && errorMessage.includes('connect')
  ) {
    return; // Silently ignore
  }
  
  originalError.apply(console, args);
};

// Global error handler for MetaMask runtime errors
window.addEventListener('error', (event) => {
  const msg = event.message || '';
  if (msg.includes('MetaMask') || msg.includes('Failed to connect')) {
    event.preventDefault();
    return true;
  }
});

window.addEventListener('unhandledrejection', (event) => {
  const reason = event.reason?.message || event.reason?.toString() || '';
  if (reason.includes('MetaMask') || reason.includes('Failed to connect')) {
    event.preventDefault();
    return true;
  }
});

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
