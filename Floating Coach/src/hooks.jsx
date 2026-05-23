// Shared React hooks + connection status indicator.
const { useState: useStateH, useEffect: useEffectH, useRef: useRefH, useCallback: useCallbackH } = React;

// ---- useSession ----
function useSession() {
  const [userId, setUserId] = useStateH(() => window.FC_SESSION.readUserId());
  useEffectH(() => window.FC_SESSION.subscribe(() => setUserId(window.FC_SESSION.readUserId())), []);
  return {
    userId,
    setUserId: (id) => window.FC_SESSION.writeUserId(id),
  };
}

// ---- useApiStatus - polls /health, exposes online/offline/checking ----
// status: 'checking' | 'online' | 'offline'
function useApiStatus() {
  const [status, setStatus] = useStateH('checking');
  const [baseUrl, setBaseUrlState] = useStateH(window.FC_API.getBaseUrl());

  const probe = useCallbackH(async () => {
    setStatus('checking');
    const ok = await window.FC_API.ping();
    setStatus(ok ? 'online' : 'offline');
  }, []);

  useEffectH(() => { probe(); }, [probe, baseUrl]);

  // Re-probe every 30s while open
  useEffectH(() => {
    const t = setInterval(probe, 30000);
    return () => clearInterval(t);
  }, [probe]);

  const setBaseUrl = (u) => {
    window.FC_API.setBaseUrl(u);
    setBaseUrlState(u);
  };

  return { status, baseUrl, setBaseUrl, probe };
}

// ---- useLiveData<T> ----
// Calls fetcher when (online && userId). For logged-in users, keeps last live data
// instead of silently falling back to demo data when the API flakes.
// Returns { data, loading, error, source, updatedAt, stale, refetch }.
function useLiveData(fetcher, fallback, deps, opts = {}) {
  const { online, userId, cacheKey, emptyData } = opts;
  const storageKey = cacheKey && userId ? `fc_live_${cacheKey}_${userId}` : null;
  const cached = storageKey ? readLiveCache(storageKey) : null;
  const userEmptyData = emptyData !== undefined ? emptyData : fallback;
  const [state, setState] = useStateH({
    data: userId ? (cached?.data ?? userEmptyData) : fallback,
    loading: false,
    error: null,
    source: userId ? (cached ? 'stale-live' : 'empty') : 'demo',
    updatedAt: cached?.updatedAt || null,
    stale: Boolean(userId && cached),
  });
  const reqId = useRefH(0);

  const refetch = useCallbackH(async () => {
    const latestCached = storageKey ? readLiveCache(storageKey) : null;
    if (!userId) {
      setState({ data: fallback, loading: false, error: null, source: 'demo', updatedAt: null, stale: false });
      return;
    }
    if (!online) {
      setState({
        data: latestCached?.data ?? userEmptyData,
        loading: false,
        error: null,
        source: latestCached ? 'stale-live' : 'empty',
        updatedAt: latestCached?.updatedAt || null,
        stale: Boolean(latestCached),
      });
      return;
    }
    const id = ++reqId.current;
    setState((s) => ({
      ...s,
      data: latestCached?.data ?? s.data ?? userEmptyData,
      loading: true,
      error: null,
      source: latestCached ? 'stale-live' : s.source,
      updatedAt: latestCached?.updatedAt || s.updatedAt,
      stale: Boolean(latestCached),
    }));
    try {
      const data = await fetcher(userId);
      if (id !== reqId.current) return;
      const updatedAt = new Date().toISOString();
      if (storageKey) writeLiveCache(storageKey, data, updatedAt);
      setState({ data, loading: false, error: null, source: 'live', updatedAt, stale: false });
    } catch (e) {
      if (id !== reqId.current) return;
      const fallbackCache = storageKey ? readLiveCache(storageKey) : null;
      setState({
        data: fallbackCache?.data ?? userEmptyData,
        loading: false,
        error: e.message || 'Onbekende fout',
        source: fallbackCache ? 'stale-live' : 'empty',
        updatedAt: fallbackCache?.updatedAt || null,
        stale: Boolean(fallbackCache),
      });
    }
  }, [online, userId, cacheKey, ...deps]);

  useEffectH(() => { refetch(); }, [refetch]);

  return { ...state, refetch };
}

function readLiveCache(key) {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(key) || 'null');
    if (parsed && parsed.data) return parsed;
  } catch (_) {}
  return null;
}

function writeLiveCache(key, data, updatedAt) {
  try {
    window.localStorage.setItem(key, JSON.stringify({ data, updatedAt }));
  } catch (_) {}
}

// ---- ConnectionPill - small status indicator ----
function ConnectionPill({ status, source, onClick }) {
  // status: API health; source: where the current data came from (live/demo)
  const isLive = status === 'online' && source === 'live';
  const isStale = source === 'stale-live';
  const isEmpty = source === 'empty';
  const isOffline = status === 'offline';
  const isDemo = !isLive && !isOffline;

  let bg, fg, label, dot;
  if (isLive) {
    bg = 'oklch(94% 0.06 145)'; fg = 'oklch(35% 0.10 145)';
    label = 'LIVE'; dot = 'var(--good)';
  } else if (isStale) {
    bg = 'oklch(96% 0.04 80)'; fg = 'oklch(42% 0.10 70)';
    label = 'STALE · LIVE'; dot = 'oklch(72% 0.16 70)';
  } else if (isEmpty) {
    bg = 'var(--bg-soft)'; fg = 'var(--ink-3)';
    label = 'GEEN DATA'; dot = 'var(--ink-4)';
  } else if (isOffline) {
    bg = 'oklch(96% 0.04 60)';  fg = 'oklch(40% 0.12 50)';
    label = 'OFFLINE · DEMO'; dot = 'oklch(72% 0.16 60)';
  } else {
    bg = 'var(--bg-soft)';      fg = 'var(--ink-3)';
    label = status === 'checking' ? 'CONNECTING…' : 'DEMO'; dot = 'var(--ink-4)';
  }

  return (
    <button type="button" onClick={onClick} title="Backend status" aria-label={`Backend status: ${label}`} style={{
      border: 'none', background: bg, color: fg, cursor: 'pointer',
      padding: '5px 10px', borderRadius: 999, minHeight: 44,
      fontFamily: "'JetBrains Mono', monospace", fontSize: 10,
      textTransform: 'uppercase', letterSpacing: '.14em', fontWeight: 600,
      display: 'inline-flex', alignItems: 'center', gap: 6,
    }}>
      <span style={{ width: 6, height: 6, borderRadius: 999, background: dot,
        animation: status === 'checking' ? 'pulse-dot 1.4s ease-in-out infinite' : 'none' }}></span>
      {label}
    </button>
  );
}

window.useSession = useSession;
window.useApiStatus = useApiStatus;
window.useLiveData = useLiveData;
window.ConnectionPill = ConnectionPill;
