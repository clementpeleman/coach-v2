// App shell — sidebar nav, screen router, floating orb.
const { useState: useStateApp, useEffect: useEffectApp } = React;

const ACCENT_OKLCH = 'oklch(92% 0.20 125)'; // acid lime
const ACCENT_INK   = '#0d0e0b';
const DEFAULT_RECOVERY = 4;

function App() {
  const session = window.useSession();
  const apiStatus = window.useApiStatus();
  const [recoverySnapshot, setRecoverySnapshot] = useStateApp(null);
  const [weather, setWeather] = useStateApp(null);
  const chatStorageKey = `fc_chat_messages_v1_${session.userId || 'demo'}`;
  const recoveryMetrics = recoverySnapshot?.metrics || window.FC_DATA.recovery;
  const recoveryScore = recoverySnapshot?.score ?? DEFAULT_RECOVERY;
  const [chatMessages, setChatMessages] = useStateApp(() => readStoredChat(chatStorageKey));
  const [chatThinking, setChatThinking] = useStateApp(false);
  const resetChat = () => {
    setChatMessages(window.FC_DATA.chatSeed);
    setChatThinking(false);
  };

  // Initial screen: OAuth paths like /dashboard?user_id=… or stored session → dashboard
  const [screen, setScreen] = useStateApp(() => {
    const path = (window.location.pathname || '/').replace(/\/$/, '') || '/';
    if (session.userId && (path === '/dashboard' || path === '/')) return 'dashboard';
    return session.userId ? 'dashboard' : 'onboarding';
  });

  // Live user profile from /web/auth/me (name, garmin_connected).
  const [profile, setProfile] = useStateApp(null);
  useEffectApp(() => {
    setProfile(null);
    if (apiStatus.status !== 'online' || !session.userId) return;
    let cancelled = false;
    window.FC_API.fetchWebUser(session.userId).then((p) => {
      if (!cancelled) setProfile(p);
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [apiStatus.status, session.userId]);

  // Shared chat memory for both the floating coach and full Coach tab.
  useEffectApp(() => {
    setChatMessages(readStoredChat(chatStorageKey));
    setChatThinking(false);
  }, [chatStorageKey]);

  useEffectApp(() => {
    try {
      window.localStorage.setItem(chatStorageKey, JSON.stringify(chatMessages.slice(-80)));
    } catch (_) {}
  }, [chatStorageKey, chatMessages]);

  // Live Garmin health snapshot for recovery, sleep, stress, HRV and body battery.
  useEffectApp(() => {
    setRecoverySnapshot(null);
    if (apiStatus.status !== 'online' || !session.userId) return;
    let cancelled = false;
    window.FC_API.fetchGarminRecovery(session.userId).then((snapshot) => {
      if (!cancelled && snapshot?.source === 'live') setRecoverySnapshot(snapshot);
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [apiStatus.status, session.userId]);

  // Browser location + live weather. If permission is denied, keep the UI honest.
  useEffectApp(() => {
    setWeather(null);
    if (apiStatus.status !== 'online' || !session.userId || !navigator.geolocation) return;
    let cancelled = false;
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        window.FC_API.fetchWeather(pos.coords.latitude, pos.coords.longitude).then((w) => {
          if (!cancelled) setWeather(w);
        }).catch(() => {});
      },
      () => {
        if (!cancelled) setWeather({ source: 'unavailable', condition: 'locatie onbekend' });
      },
      { enableHighAccuracy: false, timeout: 8000, maximumAge: 30 * 60 * 1000 },
    );
    return () => { cancelled = true; };
  }, [apiStatus.status, session.userId]);

  // Apply accent token once.
  useEffectApp(() => {
    document.documentElement.style.setProperty('--accent', ACCENT_OKLCH);
    document.documentElement.style.setProperty('--accent-ink', ACCENT_INK);
  }, []);

  // Garmin OAuth callback: ?user_id= & optional /dashboard path → normalize URL to /
  useEffectApp(() => {
    const params = new URLSearchParams(window.location.search);
    const hadUser = params.has('user_id');
    const hadGarmin = params.has('garmin_connected');
    if (hadUser) params.delete('user_id');
    if (hadGarmin) params.delete('garmin_connected');
    const onDashboardPath = window.location.pathname.replace(/\/$/, '') === '/dashboard';
    if (hadUser || hadGarmin || onDashboardPath) {
      if (session.userId) setScreen('dashboard');
      const q = params.toString();
      window.history.replaceState({}, '', '/' + (q ? `?${q}` : ''));
    }
  }, [session.userId]);

  const SCREENS = {
    dashboard:  { label: 'Dashboard',    ico: '◆', Comp: window.Dashboard },
    workout:    { label: 'Training',     ico: '▶', Comp: window.WorkoutScreen },
    activities: { label: 'Activiteiten', ico: '≡', Comp: window.ActivitiesScreen },
    recovery:   { label: 'Herstel',      ico: '◐', Comp: window.RecoveryScreen },
    chat:       { label: 'Coach',        ico: '◯', Comp: window.ChatScreen },
  };

  if (screen === 'onboarding') {
    return (
      <window.OnboardingScreen
        onComplete={() => setScreen('dashboard')}
        apiStatus={apiStatus.status} />
    );
  }

  const Active = SCREENS[screen]?.Comp;
  const screenProps = {
    recoveryScore,
    recoveryData: recoveryMetrics,
    recoverySnapshot,
    weather,
    onNavigate: setScreen,
    apiStatus: apiStatus.status,
    userId: session.userId,
    profile,
    chatMessages,
    setChatMessages,
    chatThinking,
    setChatThinking,
    resetChat,
  };

  const userName = profile?.display_name || profile?.email || window.FC_DATA.user.name;
  const userInitials = (profile?.display_name || profile?.email || 'CP')
    .replace(/[^a-zA-Z]/g, '').slice(0, 2).toUpperCase() || 'CP';
  const garminConnected = profile?.garmin_connected ?? false;
  const isLive = apiStatus.status === 'online';

  const logout = () => {
    if (session.userId && isLive) {
      window.FC_API.disconnectGarmin(session.userId).catch(() => {});
    }
    window.FC_SESSION.writeUserId(null);
    setScreen('onboarding');
  };

  return (
    <>
      <div className="app">
        {/* Sidebar */}
        <aside className="rail">
          <div className="brand">
            <div className="dot"></div>
            <div>
              <b>Floating Coach</b>
              <small>v2 · nl</small>
            </div>
          </div>

          {Object.entries(SCREENS).map(([k, s]) => (
            <div key={k}
              className={`rail-item ${screen === k ? 'active' : ''}`}
              onClick={() => setScreen(k)}>
              <span className="ico">{s.ico}</span>
              <span>{s.label}</span>
              {k === 'workout' && screen !== 'workout' && (
                <span style={{ marginLeft: 'auto' }} className="tag accent">NEW</span>
              )}
            </div>
          ))}

          <div className="spacer"></div>

          {/* Live status block */}
          <div style={{ padding: '10px 12px', marginBottom: 10,
                        background: 'var(--surface)', border: '1px solid var(--line)',
                        borderRadius: 10 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span className="label">Backend</span>
              <window.ConnectionPill status={apiStatus.status} source={isLive ? 'live' : 'demo'}
                                      onClick={apiStatus.probe} />
            </div>
            <div className="mono" style={{ fontSize: 10, color: 'var(--ink-4)', marginTop: 6,
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
              title={apiStatus.baseUrl}>
              {apiStatus.baseUrl.replace(/^https?:\/\//, '')}
            </div>
            {session.userId ? (
              <div className="mono" style={{ fontSize: 10, color: 'var(--ink-3)', marginTop: 6 }}>
                user_id <b style={{ color: 'var(--ink)' }}>{session.userId}</b>
                {garminConnected
                  ? <span style={{ color: 'var(--good)', marginLeft: 6 }}>● garmin</span>
                  : <span style={{ color: 'var(--warn)', marginLeft: 6 }}>○ niet verb.</span>}
              </div>
            ) : (
              <div className="mono" style={{ fontSize: 10, color: 'var(--ink-4)', marginTop: 6 }}>
                niet ingelogd
              </div>
            )}
          </div>

          <div className="rail-item" onClick={() => setScreen('onboarding')}>
            <span className="ico">↻</span>
            <span>{session.userId ? 'Opnieuw verbinden' : 'Login / verbind'}</span>
          </div>

          {session.userId && (
            <div className="rail-item" onClick={logout}>
              <span className="ico">⎋</span>
              <span>Logout</span>
            </div>
          )}

          <div className="footer">
            <div className="avatar">{userInitials}</div>
            <div style={{ flex: 1 }}>
              <div className="who">{userName}</div>
              <div className="stat">
                {isLive
                  ? (garminConnected ? 'Garmin · live' : (session.userId ? 'API · live' : 'Demo · login nodig'))
                  : 'Demo modus'}
              </div>
            </div>
          </div>
        </aside>

        {/* Main */}
        <main className="main">
          {Active && <Active {...screenProps} />}
        </main>
      </div>

      {/* Floating coach */}
      {screen !== 'chat' && (
        <window.CoachOrb recoveryScore={recoveryScore}
                          recoveryData={recoveryMetrics}
                          weather={weather}
                          onNavigateChat={() => setScreen('chat')}
                          currentScreen={screen}
                          apiStatus={apiStatus.status}
                          userId={session.userId}
                          messages={chatMessages}
                          setMessages={setChatMessages}
                          thinking={chatThinking}
                          setThinking={setChatThinking} />
      )}
    </>
  );
}

function readStoredChat(key) {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(key) || 'null');
    if (Array.isArray(parsed) && parsed.length) {
      return parsed
        .filter((m) => m && typeof m.role === 'string' && typeof m.content === 'string')
        .map((m) => ({
          role: m.role === 'user' ? 'user' : 'assistant',
          content: m.content,
          time: m.time || '',
          source: m.source,
        }));
    }
  } catch (_) {}
  return window.FC_DATA.chatSeed;
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
