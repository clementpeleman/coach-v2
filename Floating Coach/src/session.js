// Session - user_id management, mirrors webapp/src/lib/session.ts.
(function () {
  const KEY = 'sportsHubUserId';

  function readUserId() {
    try {
      // 1. ?user_id= query param (used after Garmin OAuth callback)
      const q = new URLSearchParams(window.location.search).get('user_id');
      const qn = q ? Number(q) : NaN;
      if (Number.isInteger(qn) && qn > 0) {
        // persist it so refresh keeps the session
        window.localStorage.setItem(KEY, String(qn));
        return qn;
      }
    } catch (_) {}
    try {
      const raw = window.localStorage.getItem(KEY);
      const n = raw ? Number(raw) : NaN;
      return Number.isInteger(n) && n > 0 ? n : null;
    } catch (_) {
      return null;
    }
  }

  function writeUserId(id) {
    try {
      if (id == null) window.localStorage.removeItem(KEY);
      else window.localStorage.setItem(KEY, String(id));
    } catch (_) {}
  }

  // Tiny pub/sub so React components can re-render when user_id changes
  const listeners = new Set();
  function subscribe(fn) { listeners.add(fn); return () => listeners.delete(fn); }
  function notify() { listeners.forEach((fn) => { try { fn(); } catch (_) {} }); }

  window.FC_SESSION = {
    readUserId,
    writeUserId: (id) => { writeUserId(id); notify(); },
    subscribe,
    notify,
  };
})();
