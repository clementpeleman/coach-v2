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

// ---- useApiStatus — polls /health, exposes online/offline/checking ----
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
// Calls fetcher when (online && userId) — otherwise returns a fallback (demo data).
// Returns { data, loading, error, source: 'live' | 'demo', refetch }.
function useLiveData(fetcher, fallback, deps, opts = {}) {
  const { online, userId } = opts;
  const [state, setState] = useStateH({
    data: fallback,
    loading: false,
    error: null,
    source: 'demo',
  });
  const reqId = useRefH(0);

  const refetch = useCallbackH(async () => {
    if (!online || !userId) {
      setState((s) => ({ ...s, data: fallback, loading: false, error: null, source: 'demo' }));
      return;
    }
    const id = ++reqId.current;
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const data = await fetcher(userId);
      if (id !== reqId.current) return;
      setState({ data, loading: false, error: null, source: 'live' });
    } catch (e) {
      if (id !== reqId.current) return;
      // Fall back to demo data on error, but surface the error.
      setState({ data: fallback, loading: false, error: e.message || 'Onbekende fout', source: 'demo' });
    }
  }, [online, userId, ...deps]);

  useEffectH(() => { refetch(); }, [refetch]);

  return { ...state, refetch };
}

// ---- ConnectionPill — small status indicator ----
function ConnectionPill({ status, source, onClick }) {
  // status: API health; source: where the current data came from (live/demo)
  const isLive = status === 'online' && source === 'live';
  const isOffline = status === 'offline';
  const isDemo = !isLive && !isOffline;

  let bg, fg, label, dot;
  if (isLive) {
    bg = 'oklch(94% 0.06 145)'; fg = 'oklch(35% 0.10 145)';
    label = 'LIVE'; dot = 'var(--good)';
  } else if (isOffline) {
    bg = 'oklch(96% 0.04 60)';  fg = 'oklch(40% 0.12 50)';
    label = 'OFFLINE · DEMO'; dot = 'oklch(72% 0.16 60)';
  } else {
    bg = 'var(--bg-soft)';      fg = 'var(--ink-3)';
    label = status === 'checking' ? 'CONNECTING…' : 'DEMO'; dot = 'var(--ink-4)';
  }

  return (
    <button onClick={onClick} title="Backend status" style={{
      border: 'none', background: bg, color: fg, cursor: 'pointer',
      padding: '5px 10px', borderRadius: 999,
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
