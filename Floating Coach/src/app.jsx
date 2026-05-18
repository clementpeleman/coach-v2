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
  const [trainingProfile, setTrainingProfile] = useStateApp(null);
  const chatStorageKey = `fc_chat_messages_v1_${session.userId || 'demo'}`;
  const recoveryMetrics = recoverySnapshot?.metrics || window.FC_DATA.recovery;
  const recoveryScore = currentReadinessScore(
    recoverySnapshot?.score ?? DEFAULT_RECOVERY,
    recoveryMetrics,
    recoverySnapshot?.source === 'live',
  );
  const [chatMessages, setChatMessages] = useStateApp(() => readStoredChat(chatStorageKey));
  const [chatThinking, setChatThinking] = useStateApp(false);
  const [draftWorkout, setDraftWorkout] = useStateApp(() => (
    window.FC_WORKOUT_PLAN?.buildDraft({ recoveryScore: DEFAULT_RECOVERY, trainingProfile: null })
  ));
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

  // Shared training profile: personal targets, sport baselines, and learned workout patterns.
  useEffectApp(() => {
    setTrainingProfile(null);
    if (apiStatus.status !== 'online' || !session.userId) return;
    let cancelled = false;
    window.FC_API.fetchTrainingProfile(session.userId, 120, 7).then((profileData) => {
      if (!cancelled) setTrainingProfile(profileData);
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

  useEffectApp(() => {
    if (!window.FC_WORKOUT_PLAN) return;
    setDraftWorkout((current) => {
      const shouldRefreshAutoDraft = !current || (
        current.source === 'auto'
        && current.status !== 'approved'
        && (
          current.recoveryScore !== recoveryScore
          || (trainingProfile && !current.profileApplied)
        )
      );
      if (!shouldRefreshAutoDraft) return current;
      return {
        ...window.FC_WORKOUT_PLAN.buildDraft({ recoveryScore, trainingProfile }),
        recoveryScore,
        profileApplied: Boolean(trainingProfile),
      };
    });
  }, [recoveryScore, trainingProfile]);

  useEffectApp(() => {
    window.FC_SET_DRAFT_WORKOUT = (updater) => setDraftWorkout(updater);
    return () => {
      if (window.FC_SET_DRAFT_WORKOUT) delete window.FC_SET_DRAFT_WORKOUT;
    };
  }, []);

  useEffectApp(() => {
    const openCoachWithMessages = (messagesOrEvent) => {
      const incoming = Array.isArray(messagesOrEvent)
        ? messagesOrEvent
        : messagesOrEvent?.detail;
      if (!Array.isArray(incoming) || !incoming.length) {
        setScreen('chat');
        return;
      }
      setChatThinking(false);
      setChatMessages((current) => appendUniqueChatMessages(current || window.FC_DATA.chatSeed, incoming));
      setScreen('chat');
    };
    window.FC_OPEN_COACH_MESSAGES = openCoachWithMessages;
    window.addEventListener('fc-open-chat-messages', openCoachWithMessages);
    return () => {
      window.removeEventListener('fc-open-chat-messages', openCoachWithMessages);
      if (window.FC_OPEN_COACH_MESSAGES === openCoachWithMessages) delete window.FC_OPEN_COACH_MESSAGES;
    };
  }, []);

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
    trainingProfile,
    chatMessages,
    setChatMessages,
    chatThinking,
    setChatThinking,
    resetChat,
    draftWorkout,
    setDraftWorkout,
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
                          trainingProfile={trainingProfile}
                          draftWorkout={draftWorkout}
                          setDraftWorkout={setDraftWorkout}
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
      if (isLegacyDemoChat(parsed)) return window.FC_DATA.chatSeed;
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

function isLegacyDemoChat(messages) {
  const legacyUserText = 'Doe maar, maar liever 45 min, ik moet om 19u thuis zijn.';
  const legacyAssistantText = 'Top. <b>2× 12 min</b> op drempel met 4 min herstel tussendoor, plus warming-up en cooling-down. <i>Klaargezet in Garmin Connect.</i>';
  return messages.length === 3
    && messages[0]?.role === 'assistant'
    && messages[1]?.role === 'user'
    && messages[1]?.content === legacyUserText
    && messages[2]?.role === 'assistant'
    && messages[2]?.content === legacyAssistantText;
}

function currentReadinessScore(score, metrics, live) {
  if (!live || !metrics || score == null) return score;
  let adjusted = score;
  const currentBattery = metrics.bodyBatteryCurrent;
  const trainingPenalty = metrics.recentTrainingPenalty || 0;

  if (currentBattery != null) {
    if (currentBattery <= 15) adjusted = Math.min(adjusted, 2);
    else if (currentBattery <= 25) adjusted = Math.min(adjusted, 3);
    else if (currentBattery <= 35 && trainingPenalty >= 0.8) adjusted = Math.min(adjusted, 3);
  }
  if (trainingPenalty >= 1.1) adjusted = Math.min(adjusted, 3);
  if (trainingPenalty >= 1.1 && currentBattery != null && currentBattery <= 25) adjusted = Math.min(adjusted, 2);

  return adjusted;
}

function appendUniqueChatMessages(messages, additions) {
  const existingIds = new Set((messages || []).map((message) => message.id).filter(Boolean));
  const unique = additions.filter((message) => !message.id || !existingIds.has(message.id));
  return [...(messages || []), ...unique];
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
