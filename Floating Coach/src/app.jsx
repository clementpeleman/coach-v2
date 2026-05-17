// App shell — sidebar nav, screen router, floating orb.
const { useState: useStateApp, useEffect: useEffectApp } = React;

const ACCENT_OKLCH = 'oklch(92% 0.20 125)'; // acid lime
const ACCENT_INK   = '#0d0e0b';
const DEFAULT_RECOVERY = 4;

function App() {
  const session = window.useSession();
  const apiStatus = window.useApiStatus();
  const recoveryScore = DEFAULT_RECOVERY;

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
    onNavigate: setScreen,
    apiStatus: apiStatus.status,
    userId: session.userId,
    profile,
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
                          onNavigateChat={() => setScreen('chat')}
                          currentScreen={screen}
                          apiStatus={apiStatus.status}
                          userId={session.userId} />
      )}
    </>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
